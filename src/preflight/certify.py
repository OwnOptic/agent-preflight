"""Continuous certification.

A certification names exactly what was reviewed: the composition hash of every agent at the moment
of sign-off. Any change to an agent's composition voids its certification automatically, so an
approval from March cannot silently cover an agent rebuilt in September.

The record also carries what each agent cost per interaction when it was signed off, and when it
was signed off, so a later scan can see a cost regression (CO-02) and an expired review (ML-05)
without keeping a separate history.
"""

from __future__ import annotations

from datetime import datetime, timezone

from preflight.bom.models import AgentBOM
from preflight.bom.canonical import composition_hash


def tokens_per_interaction(b: AgentBOM) -> int | None:
    """Per-turn tokens including fan-out through delegation, or ``None`` when unknowable."""
    e = b.economics
    base = (e.instructionTokens or 0) + (e.toolDescriptionTokens or 0) + (e.groundingTokensPerTurn or 0)
    if base == 0:
        return None
    return round(base * (e.fanoutFactor or 1.0))


def certify(boms: list[AgentBOM], by: str) -> dict:
    return {
        "version": 2,
        "certifiedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "by": by,
        "agents": [
            {
                "id": b.agent.id,
                "platform": b.agent.platform,
                "name": b.agent.name,
                "compositionHash": composition_hash(b),
                "tokensPerInteraction": tokens_per_interaction(b),
                "costPerInteraction": (
                    {"value": b.economics.estimatedCostPerInteraction.value,
                     "currency": b.economics.estimatedCostPerInteraction.currency}
                    if b.economics.estimatedCostPerInteraction else None
                ),
            }
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
