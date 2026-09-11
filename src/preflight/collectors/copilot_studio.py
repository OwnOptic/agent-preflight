"""Copilot Studio collector.

Reads: authentication mode, instructions, topics and the HTTP requests they make, generative
settings, knowledge components, and where the agent is reachable.

Access: an unmanaged solution export, unzipped or still a ``.zip``. Prefer the export over live
Dataverse: it is offline, versionable, and needs no environment open mid-demo. The layout read is
the one Dataverse writes:

    bots/<schema>/bot.xml                         name, authenticationmode
    bots/<schema>/configuration.json              generative settings, default instructions
    botcomponents/<component>/botcomponent.xml    componenttype, parent bot
    botcomponents/<component>/data                the component's YAML

A solution export does not record which environment it came from or where the agent is reachable.
Those facts come from ``environment.json`` beside the export, written when it was taken. Without it
the agent has no endpoints and no region, and the analysis reports them as unknown.

Two things this collector deliberately does not claim. Copilot Studio has no setting that forces
citations, so ``citationsRequired`` stays unknown. And a yes/no question before an HTTP request is
recorded as approval, which shows a human is asked, not that the answer is checked.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import yaml

from preflight.bom.models import (
    Agent,
    AgentBOM,
    Generator,
    Guards,
    Identity,
    Instructions,
    Knowledge,
    Residency,
    Tool,
    ToolAuth,
    ToolSource,
)
from preflight.collectors.base import AgentRef, Scope

#: bot.authenticationmode: 0 Unspecified, 1 None, 2 Integrated (Entra), 3 Custom Entra ID, 4 OAuth2.
_INBOUND = {0: "unknown", 1: "none", 2: "obo", 3: "obo", 4: "obo"}
_TOPIC, _GPT, _KNOWLEDGE = 9, 15, 16
_KEY_HEADERS = {"api-key", "x-api-key", "ocp-apim-subscription-key", "x-functions-key", "authorization"}


class _Export:
    """Read access to a solution export, whether unzipped or still a zip."""

    def __init__(self, root: Path):
        self.root = root
        self._zip = zipfile.ZipFile(root) if root.is_file() else None

    def names(self) -> list[str]:
        if self._zip:
            return self._zip.namelist()
        return [p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()]

    def read(self, name: str) -> str:
        if self._zip:
            return self._zip.read(name).decode("utf-8-sig")
        return (self.root / name).read_text(encoding="utf-8-sig")


def _exports(root: Path) -> Iterator[Path]:
    for f in sorted(root.rglob("solution.xml")):
        if (f.parent / "bots").is_dir():
            yield f.parent
    for z in sorted(root.rglob("*.zip")):
        try:
            names = zipfile.ZipFile(z).namelist()
        except zipfile.BadZipFile:
            continue
        if "solution.xml" in names and any(n.startswith("bots/") for n in names):
            yield z


def _bots(ex: _Export) -> Iterator[tuple[str, str | None]]:
    for n in ex.names():
        parts = n.split("/")
        if len(parts) == 3 and parts[0] == "bots" and parts[2] == "bot.xml":
            yield parts[1], ET.fromstring(ex.read(n)).findtext("name")


#: A key whose value is a Power Fx expression, e.g. ``content: ={ enquiry: System.Activity.Text }``.
_FX = re.compile(r"^(\s*(?:- )?[\w.@-]+:[ \t]+)(=.*?)\s*$")


def _load_yaml(text: str) -> dict | None:
    """Copilot Studio writes Power Fx values unquoted, which strict YAML rejects when the
    expression contains ``: ``. Quote every ``=`` value first; the expression text is kept verbatim."""
    fixed = "\n".join(
        (m.group(1) + "'" + m.group(2).replace("'", "''") + "'") if (m := _FX.match(line)) else line
        for line in text.splitlines()
    )
    try:
        data = yaml.safe_load(fixed)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _components(ex: _Export, schema: str) -> Iterator[tuple[int, str, dict | None]]:
    """(componenttype, schemaname, parsed YAML) for every component whose parent is ``schema``.
    The YAML is ``None`` when it cannot be parsed, so the caller can say so instead of skipping it."""
    names = set(ex.names())
    for n in sorted(names):
        parts = n.split("/")
        if len(parts) != 3 or parts[0] != "botcomponents" or parts[2] != "botcomponent.xml":
            continue
        meta = ET.fromstring(ex.read(n))
        if meta.findtext("parentbotid/schemaname") != schema:
            continue
        data_name = f"botcomponents/{parts[1]}/data"
        data = _load_yaml(ex.read(data_name)) if data_name in names else {}
        yield int(meta.findtext("componenttype") or -1), meta.get("schemaname") or parts[1], data


def _http_actions(node, confirmed: bool = False) -> Iterator[tuple[dict, bool]]:
    """Every HttpRequestAction, and whether a yes/no question precedes it on the same branch."""
    if isinstance(node, list):
        seen = confirmed
        for item in node:
            yield from _http_actions(item, seen)
            if isinstance(item, dict) and item.get("kind") == "Question" and "Boolean" in str(item.get("entity", "")):
                seen = True
    elif isinstance(node, dict):
        if node.get("kind") == "HttpRequestAction":
            yield node, confirmed
        for v in node.values():
            if isinstance(v, (list, dict)):
                yield from _http_actions(v, confirmed)


def _server(url: str) -> str | None:
    """A literal URL as written, or the literal URL inside a Power Fx expression, or nothing."""
    if not url:
        return None
    if not url.startswith("="):
        return url
    m = re.search(r'"(https?://[^"]+)"', url)
    return m.group(1) if m else None


def _auth(headers: dict | None) -> ToolAuth:
    for k, v in (headers or {}).items():
        if str(k).lower() not in _KEY_HEADERS:
            continue
        v = str(v)
        if not v.startswith("="):
            return ToolAuth(mode="key", secretRef="inline")
        return ToolAuth(mode="key" if str(k).lower() != "authorization" else "unknown",
                        secretRef="env" if "Env." in v else "variable")
    return ToolAuth(mode="none")


def _environment(export: Path) -> dict:
    for d in (export if export.is_dir() else export.parent, export.parent):
        f = d / "environment.json"
        if f.is_file():
            return json.loads(f.read_text(encoding="utf-8"))
    return {}


def _knowledge_kind(data: dict) -> str:
    text = json.dumps(data).lower()
    if "sharepoint" in text:
        return "sharepoint"
    if "publicsite" in text or "website" in text:
        return "web"
    return "other"


class CopilotStudioCollector:
    platform = "copilot-studio"
    version = "copilot_studio@0.2.0"

    def available(self) -> tuple[bool, str]:
        return True, "reads exported solutions on disk"

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        for export in _exports(Path(scope.path or ".")):
            for schema, name in _bots(_Export(export)):
                yield AgentRef(id=schema, platform=self.platform, name=name, scope=Scope(path=str(export)))

    def collect(self, ref: AgentRef) -> AgentBOM:
        root = Path(ref.scope.path)
        ex = _Export(root)
        schema = ref.id
        bot = ET.fromstring(ex.read(f"bots/{schema}/bot.xml"))
        cfg_name = f"bots/{schema}/configuration.json"
        cfg = json.loads(ex.read(cfg_name)) if cfg_name in ex.names() else {}
        env = _environment(root)
        parsed = list(_components(ex, schema))
        unparsed = sorted(s for _, s, d in parsed if d is None)
        comps = [(t, s, d) for t, s, d in parsed if d is not None]

        default_gpt = (cfg.get("gPTSettings") or {}).get("defaultSchemaName")
        gpts = [d for t, s, d in comps if t == _GPT and (default_gpt is None or s == default_gpt)]
        instructions = str((gpts[0] if gpts else {}).get("instructions") or "")

        tools: list[Tool] = []
        for t, _, data in comps:
            if t != _TOPIC:
                continue
            for node, confirmed in _http_actions(data):
                tools.append(
                    Tool(
                        id=f"action:{node.get('id')}",
                        kind="connector",
                        name=str(node.get("id")),
                        approval=confirmed,
                        source=ToolSource(server=_server(str(node.get("url") or "")),
                                          httpMethod=str(node.get("method") or "Get").upper()),
                        auth=_auth(node.get("headers")),
                    )
                )

        knowledge = [Knowledge(id=s, kind=_knowledge_kind(d)) for t, s, d in comps if t == _KNOWLEDGE]
        ai = cfg.get("aISettings") or {}
        source = root / "bots" / schema / "bot.xml" if root.is_dir() else root

        return AgentBOM(
            generated=datetime.now(timezone.utc),
            generator=Generator(collector=self.version),
            agent=Agent(
                id=schema,
                platform=self.platform,
                name=bot.findtext("name"),
                environment=env.get("environmentId"),
                endpoints=list(env.get("endpoints") or []),
                inboundAuth=_INBOUND.get(int(bot.findtext("authenticationmode") or 0), "unknown"),
                sourceFile=str(source),
                identity=Identity(kind="unknown"),
                instructions=Instructions(
                    hash="sha256:" + hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
                    tokens=(len(instructions) + 3) // 4,
                ) if instructions else Instructions(),
            ),
            tools=tools,
            knowledge=knowledge,
            guards=Guards(),
            residency=Residency(observed=[env["region"]] if env.get("region") else []),
            tags={
                "allowGeneralKnowledge": str(ai.get("useModelKnowledge")),
                "generativeOrchestration": str((cfg.get("settings") or {}).get("GenerativeActionsEnabled")),
                "published": str(env.get("published")),
                # Components whose YAML could not be read. Not an empty agent: an unread one.
                "unparsedComponents": ",".join(unparsed) or "none",
            },
        )
