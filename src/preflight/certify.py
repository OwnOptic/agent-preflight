"""Continuous certification.

A certification names exactly what was reviewed: the composition hash of every agent at the moment
of sign-off. Any change to an agent's composition voids its certification automatically, so an
approval from March cannot silently cover an agent rebuilt in September.
"""

from __future__ import annotations

from datetime import datetime, timezone

from preflight.bom.canonical import composition_hash
from preflight.bom.models import AgentBOM


def certify(boms: list[AgentBOM], by: str) -> dict:
    return {
        "version": 1,
        "certifiedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "by": by,
        "agents": [
            {"id": b.agent.id, "platform": b.agent.platform, "name": b.agent.name,
             "compositionHash": composition_hash(b)}
            for b in sorted(boms, key=lambda x: (x.agent.platform, x.agent.id))
        ],
    }


def status(boms: list[AgentBOM], record: dict) -> dict[str, str]:
    """Per agent: ``valid``, ``void`` (changed since sign-off) or ``uncertified``."""
    signed = {a["id"]: a["compositionHash"] for a in record.get("agents", [])}
    out = {}
    for b in boms:
        if b.agent.id not in signed:
            out[b.agent.id] = "uncertified"
        else:
            out[b.agent.id] = "valid" if signed[b.agent.id] == composition_hash(b) else "void"
    return out
