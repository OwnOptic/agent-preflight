"""Foundry Agent Service collector.

Reads: prompt agents, their tools, MCP connections and the tool manifests behind them, connected
agents, model deployment, and the guards the definition declares.

Two access modes, one BOM:

* ``FoundryCollector`` reads exported agent definitions (``agent.json``) from disk. Offline, which
  is what CI and the fixtures use.
* ``FoundryLiveCollector`` reads the live project over the data plane with an az token. Read-only.

MCP tool manifests. An agent definition names an MCP server, not its tools. The tools, and their
annotations, come from the server's ``tools/list``. Calling it would be traffic, so the collectors
read captured manifests (``*mcp*manifest*.json``) instead: the manifest sitting next to the agent,
plus any directory passed with ``--mcp-manifests``. Without one, the connection is recorded as a
single unannotated tool and the classifier fails closed on it, which is the honest reading.

Token trap on this machine: the az default context can point at an unrelated subscription, and a
token minted there comes back from the data plane as a 401 that looks like a Foundry fault. The live
collector therefore always passes ``--subscription`` when one is given.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from preflight.bom.models import (
    Agent,
    AgentBOM,
    Annotations,
    Generator,
    Guards,
    Identity,
    Instructions,
    Model,
    Residency,
    Tool,
    ToolAuth,
    ToolSource,
)
from preflight.collectors.base import AgentRef, Scope
from preflight.resolve.edges import normalise

#: Foundry built-in tool type -> first-party registry id.
_BUILTINS = {
    "bing_grounding": "bing_grounding",
    "bing_custom_search": "bing_custom_search",
    "browser_automation": "browser_automation",
    "computer_use_preview": "computer_use",
    "deep_research": "deep_research",
    "file_search": "file_search",
    "sharepoint_grounding": "sharepoint",
    "fabric_dataagent": "fabric",
    "image_generation": "image_generation",
    "azure_function": "azure_function",
}


def _tokens(text: str | None) -> int:
    return max(1, round(len(text or "") / 4))


def load_manifests(dirs: Iterable[Path]) -> dict[str, dict]:
    """Captured MCP ``tools/list`` results, keyed by normalised server URL."""
    out: dict[str, dict] = {}
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for f in sorted(set(d.glob("*mcp*manifest*.json")) | set(d.glob("*/*mcp*manifest*.json"))):
            try:
                m = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if m.get("server_url") and isinstance(m.get("tools"), list):
                out[normalise(m["server_url"])] = m
    return out


def _mcp_tools(spec: dict[str, Any], manifests: dict[str, dict]) -> list[Tool]:
    server = spec.get("server_url")
    label = spec.get("server_label") or normalise(server) or "mcp"
    allowed = spec.get("allowed_tools")
    auth = spec.get("auth") or {}
    tool_auth = ToolAuth(mode=auth.get("mode", "unknown"), secretRef=auth.get("secretRef"))
    manifest = manifests.get(normalise(server))

    if manifest is None:
        return [
            Tool(
                id=f"mcp:{label}",
                kind="mcp",
                name=label,
                source=ToolSource(server=server, allowlist=allowed is not None),
                auth=tool_auth,
            )
        ]

    listed = manifest["tools"]
    exposed = [t for t in listed if t.get("name") in allowed] if allowed else listed
    mhash = "sha256:" + hashlib.sha256(
        json.dumps(listed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return [
        Tool(
            id=f"mcp:{label}/{t['name']}",
            kind="mcp",
            name=t["name"],
            descriptionTokens=_tokens(t.get("description")),
            source=ToolSource(server=server, manifestHash=mhash, allowlist=allowed is not None),
            auth=tool_auth,
            annotations=Annotations(**t["annotations"]) if t.get("annotations") is not None else None,
        )
        for t in exposed
    ]


def build_bom(d: dict[str, Any], *, collector: str, manifests: dict[str, dict],
              source_file: str | None = None, project: str | None = None,
              region: str | None = None) -> AgentBOM:
    project = project or d.get("project")
    region = region or d.get("region")
    instructions = d.get("instructions") or ""

    tools: list[Tool] = []
    for spec in d.get("tools") or []:
        typ = spec.get("type")
        if typ == "mcp":
            tools.extend(_mcp_tools(spec, manifests))
        elif typ == "connected_agent":
            ca = spec.get("connected_agent") or {}
            tools.append(
                Tool(
                    id=f"a2a:{ca.get('name') or ca.get('id')}",
                    kind="a2a",
                    name=ca.get("name") or ca.get("id") or "connected-agent",
                    source=ToolSource(server=f"{project}/assistants/{ca['id']}" if project and ca.get("id") else None),
                    auth=ToolAuth(mode="obo"),
                )
            )
        elif typ == "code_interpreter":
            tools.append(Tool(id="builtin:code_interpreter", kind="code-interpreter", name="code_interpreter",
                              source=ToolSource(builtinId="code_interpreter")))
        elif typ in _BUILTINS:
            tools.append(Tool(id=f"builtin:{typ}", kind="builtin", name=typ, source=ToolSource(builtinId=_BUILTINS[typ])))
        elif typ == "function":
            fn = spec.get("function") or {}
            tools.append(Tool(id=f"fn:{fn.get('name')}", kind="function", name=fn.get("name") or "function",
                              descriptionTokens=_tokens(fn.get("description"))))
        elif typ == "openapi":
            oa = spec.get("openapi") or {}
            tools.append(Tool(id=f"openapi:{oa.get('name')}", kind="openapi", name=oa.get("name") or "openapi",
                              source=ToolSource(server=(oa.get("spec") or {}).get("servers", [{}])[0].get("url"))))

    g = d.get("guards")
    guards = Guards(**g) if isinstance(g, dict) else Guards()
    agent_id = d.get("id") or "unknown"

    return AgentBOM(
        generated=datetime.now(timezone.utc),
        generator=Generator(collector=collector),
        agent=Agent(
            id=agent_id,
            platform="foundry",
            name=d.get("name"),
            description=d.get("description"),
            environment=project,
            endpoints=[f"{project}/assistants/{agent_id}"] if project and d.get("id") else [],
            sourceFile=source_file,
            identity=Identity(kind="unknown"),
            instructions=Instructions(
                hash="sha256:" + hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
                tokens=_tokens(instructions),
            ),
        ),
        models=[Model(deployment=d["model"], model=d["model"], region=region)] if d.get("model") else [],
        tools=tools,
        guards=guards,
        residency=Residency(observed=[region] if region else []),
        # CO-03 only fires on definitions that declare guards: silence from an API that does not
        # expose them is not evidence of absence.
        tags={"declared": "guards" if isinstance(g, dict) else None},
    )


class FoundryCollector:
    """Exported agent definitions on disk."""

    platform = "foundry"
    version = "foundry@0.1.0"

    def __init__(self, manifest_dirs: Iterable[str | Path] | None = None) -> None:
        self.manifest_dirs = [Path(p) for p in (manifest_dirs or [])]

    def available(self) -> tuple[bool, str]:
        return True, "reads exported agent definitions on disk"

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        root = Path(scope.path or ".")
        for f in sorted(root.rglob("agent.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if d.get("object") != "assistant":
                continue
            yield AgentRef(id=d.get("id") or f.parent.name, platform=self.platform, name=d.get("name"),
                           scope=Scope(path=str(f)))

    def collect(self, ref: AgentRef) -> AgentBOM:
        f = Path(ref.scope.path)
        d = json.loads(f.read_text(encoding="utf-8"))
        return build_bom(d, collector=self.version, manifests=load_manifests([f.parent, *self.manifest_dirs]),
                         source_file=str(f))


class FoundryLiveCollector:
    """The live project, over the data plane. Read-only: GET requests only."""

    platform = "foundry"
    version = "foundry-live@0.1.0"

    def __init__(self, endpoint: str, *, subscription: str | None = None, region: str | None = None,
                 manifest_dirs: Iterable[str | Path] | None = None) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.subscription = subscription
        self.region = region
        self.manifest_dirs = [Path(p) for p in (manifest_dirs or [])]
        self._token: str | None = None

    def _get_token(self) -> str | None:
        if self._token:
            return self._token
        az = shutil.which("az") or shutil.which("az.cmd")
        if not az:
            return None
        cmd = [az, "account", "get-access-token", "--resource", "https://ai.azure.com",
               "--query", "accessToken", "-o", "tsv"]
        if self.subscription:
            cmd += ["--subscription", self.subscription]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=(os.name == "nt"))
        except Exception:
            return None
        self._token = r.stdout.strip() or None
        return self._token

    def _get(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(self.endpoint + path, headers={"Authorization": f"Bearer {self._get_token()}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def available(self) -> tuple[bool, str]:
        return (True, "az token acquired") if self._get_token() else (False, "no az token; run az login")

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        for a in self._get("/assistants?api-version=v1&limit=100").get("data", []):
            yield AgentRef(id=a["id"], platform=self.platform, name=a.get("name"), scope=Scope(project=self.endpoint))

    def collect(self, ref: AgentRef) -> AgentBOM:
        a = self._get(f"/assistants/{ref.id}?api-version=v1")
        return build_bom(a, collector=self.version, manifests=load_manifests(self.manifest_dirs),
                         project=self.endpoint, region=self.region)
