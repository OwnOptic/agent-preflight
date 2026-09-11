"""Canonical serialisation.

The BOM is evidence, so identical inputs must produce an identical document. That means sorted
keys, a fixed separator set, and excluding the fields that change on every run.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from preflight.bom.models import AgentBOM

#: Top-level fields excluded from the composition hash. ``generated``, ``serialNumber`` and
#: ``signature`` differ per run by design. ``economics`` is derived from the composition plus a
#: price table in policy, and a price change is not a change to the agent.
VOLATILE = {"generated", "serialNumber", "signature", "economics"}

#: Agent fields that depend on where the definition sits on disk, not on what it says.
VOLATILE_AGENT = {"sourceFile"}


def to_dict(bom: AgentBOM, *, stable: bool = False) -> dict[str, Any]:
    d = bom.model_dump(mode="json", by_alias=True, exclude_none=False)
    if stable:
        for k in VOLATILE:
            d.pop(k, None)
        for k in VOLATILE_AGENT:
            d.get("agent", {}).pop(k, None)
    return d


def canonical_json(bom: AgentBOM, *, stable: bool = False) -> str:
    return json.dumps(to_dict(bom, stable=stable), sort_keys=True, ensure_ascii=False, indent=2)


def composition_hash(bom: AgentBOM) -> str:
    """sha256 over the composition only. This is what a certification certifies."""
    payload = json.dumps(
        to_dict(bom, stable=True), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stamp(bom: AgentBOM) -> AgentBOM:
    """Give the document an identity derived from its composition.

    Deliberately not random. Two runs over the same agent produce the same serial, so the document
    is byte-identical apart from ``generated``. Call this after classification and edge resolution,
    because both are part of the composition.
    """
    bom.serialNumber = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, composition_hash(bom)))
    return bom
