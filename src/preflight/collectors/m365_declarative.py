"""Microsoft 365 declarative agents collector.

Reads: ``declarativeAgent.json`` (schema 1.8) plus every API plugin manifest it references and each
plugin's OpenAPI document.

Access: files on disk. No licence, no tenant, no network. That is why this is the first collector:
the whole pipeline runs end to end on day one without touching Azure.

What it does not do: classify tools, or resolve where an outbound URL points. Both need the whole
estate and run afterwards. This collector records the OpenAPI server URL verbatim so
``preflight.resolve`` can match it against the rest of the estate later.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from preflight.bom.models import (
    Agent,
    AgentBOM,
    Generator,
    Guards,
    Identity,
    Instructions,
    Tool,
    ToolAuth,
    ToolSource,
)
from preflight.collectors.base import AgentRef, Scope

#: Declarative-agent capability name -> first-party registry id. The registry decides what each
#: means; this map only translates the manifest's vocabulary into ours.
CAPABILITY_IDS = {
    "WebSearch": "web_search",
    "OneDriveAndSharePoint": "sharepoint",
    "GraphConnectors": "graph_connectors",
    "Email": "email",
    "TeamsMessages": "teams_messages",
    "People": "people",
    "Dataverse": "dataverse",
    "CodeInterpreter": "code_interpreter",
    "GraphicArt": "image_generation",
}

_AUTH_MODES = {"none": "none", "apikeyplugumvault": "key", "oauthplugumvault": "obo"}


class M365DeclarativeCollector:
    platform = "m365-declarative"
    version = "m365_declarative@0.1.0"

    def available(self) -> tuple[bool, str]:
        return True, "reads files on disk"

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        root = Path(scope.path or ".")
        for da in sorted(root.rglob("declarativeAgent.json")):
            try:
                doc = json.loads(da.read_text(encoding="utf-8"))
            except Exception:
                continue
            yield AgentRef(
                id=str(da.parent.name),
                platform=self.platform,
                name=doc.get("name"),
                scope=Scope(path=str(da.parent)),
            )

    def collect(self, ref: AgentRef) -> AgentBOM:
        base = Path(ref.scope.path if ref.scope and ref.scope.path else ".")
        doc = json.loads((base / "declarativeAgent.json").read_text(encoding="utf-8"))

        instructions = doc.get("instructions") or ""
        tools: list[Tool] = []
        tools.extend(self._capability_tools(doc))
        tools.extend(self._action_tools(base, doc))

        overrides = doc.get("behavior_overrides") or {}
        guards = Guards(
            # A declarative agent has no content filter of its own; it inherits the tenant's.
            contentFilter="unknown",
            promptShields=None,
            # No approval mechanism exists in the manifest, so this is absent rather than false.
            humanInTheLoop=None,
            historySummarisation=None,
        )

        return AgentBOM(
            generated=datetime.now(timezone.utc),
            generator=Generator(collector=self.version),
            agent=Agent(
                id=doc.get("id") or ref.id,
                platform=self.platform,
                name=doc.get("name"),
                environment=str(base),
                identity=Identity(kind="none", mode="obo"),
                instructions=Instructions(
                    hash="sha256:" + hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
                    tokens=_approx_tokens(instructions),
                    capChars=8000,
                ),
            ),
            tools=tools,
            guards=guards,
            tags={
                "disclaimer": (doc.get("disclaimer") or {}).get("text"),
                "discourageModelKnowledge": _s(
                    (overrides.get("special_instructions") or {}).get(
                        "discourage_model_knowledge"
                    )
                ),
                "actionCount": str(len(doc.get("actions") or [])),
            },
        )

    # -- capabilities -------------------------------------------------------------------

    def _capability_tools(self, doc: dict[str, Any]) -> list[Tool]:
        out = []
        for cap in doc.get("capabilities") or []:
            name = cap.get("name") if isinstance(cap, dict) else str(cap)
            if not name:
                continue
            out.append(
                Tool(
                    id=f"cap:{name}",
                    kind="builtin",
                    name=name,
                    source=ToolSource(builtinId=CAPABILITY_IDS.get(name)),
                    auth=ToolAuth(mode="obo"),
                )
            )
        return out

    # -- actions ------------------------------------------------------------------------

    def _action_tools(self, base: Path, doc: dict[str, Any]) -> list[Tool]:
        out: list[Tool] = []
        for action in doc.get("actions") or []:
            pfile = base / (action.get("file") or "")
            if not pfile.is_file():
                # An action pointing at a manifest we cannot read is itself worth recording.
                out.append(
                    Tool(
                        id=f"action:{action.get('id', '?')}",
                        kind="openapi",
                        name=str(action.get("id") or "unknown"),
                        source=ToolSource(server=None),
                    )
                )
                continue
            out.extend(self._plugin_tools(pfile, action.get("id") or pfile.stem))
        return out

    def _plugin_tools(self, pfile: Path, action_id: str) -> list[Tool]:
        plugin = json.loads(pfile.read_text(encoding="utf-8"))
        descriptions = {
            f.get("name"): f.get("description", "") for f in plugin.get("functions") or []
        }
        manifest_hash = "sha256:" + hashlib.sha256(pfile.read_bytes()).hexdigest()

        out: list[Tool] = []
        for runtime in plugin.get("runtimes") or []:
            if runtime.get("type") != "OpenApi":
                continue
            auth = _AUTH_MODES.get(str((runtime.get("auth") or {}).get("type", "")).lower(), "unknown")
            spec_ref = (runtime.get("spec") or {}).get("url") or ""
            spec_path = (pfile.parent / spec_ref) if spec_ref and "://" not in spec_ref else None
            if spec_path is None or not spec_path.is_file():
                out.append(
                    Tool(
                        id=f"action:{action_id}",
                        kind="openapi",
                        name=action_id,
                        source=ToolSource(server=spec_ref or None, manifestHash=manifest_hash),
                        auth=ToolAuth(mode=auth),
                    )
                )
                continue
            out.extend(
                self._openapi_tools(
                    spec_path,
                    action_id,
                    auth,
                    manifest_hash,
                    runtime.get("run_for_functions") or [],
                    descriptions,
                )
            )
        return out

    def _openapi_tools(
        self,
        spec_path: Path,
        action_id: str,
        auth: str,
        manifest_hash: str,
        run_for: list[str],
        descriptions: dict[str, str],
    ) -> list[Tool]:
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
        servers = [s.get("url") for s in spec.get("servers") or [] if s.get("url")]
        server = servers[0] if servers else None

        out: list[Tool] = []
        for path, item in (spec.get("paths") or {}).items():
            if not isinstance(item, dict):
                continue
            for method, op in item.items():
                if method.upper() not in {"GET", "PUT", "POST", "DELETE", "PATCH", "HEAD", "OPTIONS"}:
                    continue
                op_id = (op or {}).get("operationId") or f"{method}{path}"
                if run_for and op_id not in run_for:
                    continue
                desc = descriptions.get(op_id) or (op or {}).get("summary") or ""
                out.append(
                    Tool(
                        id=f"op:{action_id}/{op_id}",
                        kind="openapi",
                        name=op_id,
                        descriptionTokens=_approx_tokens(desc),
                        source=ToolSource(
                            # The full outbound URL. resolve/ matches this against the estate.
                            server=(server.rstrip("/") + path) if server else None,
                            manifestHash=manifest_hash,
                            httpMethod=method.upper(),
                        ),
                        auth=ToolAuth(mode=auth),
                    )
                )
        return out


def _approx_tokens(text: str) -> int:
    """Rough token count. Deterministic, which matters more here than being exact."""
    return max(1, round(len(text or "") / 4))


def _s(v: Any) -> str | None:
    return None if v is None else str(v)
