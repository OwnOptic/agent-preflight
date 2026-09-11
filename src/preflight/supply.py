"""Supply chain integrity: MCP rug-pull detection.

A remote MCP server can rewrite what its tools claim to do after an agent has been reviewed, and
nothing notices. ``preflight pin`` records a hash of each server's tool manifest at approval time;
``preflight scan --lock`` compares, and a changed manifest is SC-01.
"""

from __future__ import annotations

import json
from pathlib import Path

from preflight.bom.models import AgentBOM


def pin(boms: list[AgentBOM]) -> dict:
    servers: dict[str, str] = {}
    for b in boms:
        for t in b.tools:
            if t.kind == "mcp" and t.source.server and t.source.manifestHash:
                servers[t.source.server] = t.source.manifestHash
    return {"version": 1, "servers": dict(sorted(servers.items()))}


def load_lock(path: str | Path) -> dict[str, str]:
    return json.loads(Path(path).read_text(encoding="utf-8")).get("servers", {})
