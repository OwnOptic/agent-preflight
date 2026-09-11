"""Copilot Studio collector.

Reads: topics, knowledge sources, actions, published channels, authentication mode.

Access: an exported solution on disk. Prefer the export over live Dataverse: it is offline,
versionable, and needs no environment open mid-demo.

Format note. ``fixtures/02-contract-router`` is a hand-authored stand-in carrying the fields this
collector needs (``bot.json``). A genuine unmanaged solution export stores the same facts across
``botcomponents``; when one is available, parsing it into the same BOM is the next step, and the
fixture should resolve to an identical composition.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

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

_INBOUND = {
    "noauthentication": "none",
    "authenticatewithmicrosoft": "obo",
    "authenticatemanually": "obo",
}
_KNOWLEDGE_KINDS = {"ai-search", "sharepoint", "files", "fabric", "bing", "web"}


class CopilotStudioCollector:
    platform = "copilot-studio"
    version = "copilot_studio@0.1.0"

    def available(self) -> tuple[bool, str]:
        return True, "reads exported solutions on disk"

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        root = Path(scope.path or ".")
        for f in sorted(root.rglob("bot.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not d.get("schemaName"):
                continue
            yield AgentRef(id=d["schemaName"], platform=self.platform, name=d.get("displayName"),
                           scope=Scope(path=str(f)))

    def collect(self, ref: AgentRef) -> AgentBOM:
        f = Path(ref.scope.path)
        d = json.loads(f.read_text(encoding="utf-8"))
        auth = str((d.get("authentication") or {}).get("mode", "")).lower()
        gen = d.get("generativeAnswers") or {}

        tools = []
        for a in d.get("actions") or []:
            a_auth = a.get("auth") or {}
            tools.append(
                Tool(
                    id=f"action:{a['name']}",
                    kind="connector",
                    name=a["name"],
                    approval=a.get("humanApproval"),
                    source=ToolSource(server=a.get("url"), httpMethod=(a.get("method") or "").upper() or None),
                    auth=ToolAuth(mode=a_auth.get("mode", "unknown"), secretRef=a_auth.get("secretRef")),
                )
            )

        knowledge = [
            Knowledge(
                id=k["id"],
                kind=k.get("kind") if k.get("kind") in _KNOWLEDGE_KINDS else "other",
                citationsRequired=gen.get("citationsRequired") if gen.get("enabled") else None,
            )
            for k in d.get("knowledgeSources") or []
        ]

        return AgentBOM(
            generated=datetime.now(timezone.utc),
            generator=Generator(collector=self.version),
            agent=Agent(
                id=d["schemaName"],
                platform=self.platform,
                name=d.get("displayName"),
                description=d.get("description"),
                environment=d.get("environmentId"),
                endpoints=[c["endpoint"] for c in d.get("publishedChannels") or [] if c.get("endpoint")],
                inboundAuth=_INBOUND.get(auth, "unknown"),
                sourceFile=str(f),
                identity=Identity(kind="unknown"),
                instructions=Instructions(),
            ),
            tools=tools,
            knowledge=knowledge,
            guards=Guards(),
            residency=Residency(observed=[d["region"]] if d.get("region") else []),
            tags={"allowGeneralKnowledge": str(gen.get("allowGeneralKnowledge"))},
        )
