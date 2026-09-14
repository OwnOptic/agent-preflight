"""CycloneDX 1.6 export.

An AgentBOM is not a CycloneDX BOM and should not pretend to be one: CycloneDX describes what a
piece of software is made of, while an AgentBOM describes what an agent can reach and how far that
reach goes. What they share is the part a supply-chain tool already knows how to ingest, so that is
what this exporter emits, and nothing more.

The mapping, against the published 1.6 schema:

    agent                -> metadata.component, type application
    model deployment     -> component, type machine-learning-model
    local tool           -> component, type application
    tool with a server   -> service, with endpoints, authenticated and x-trust-boundary
    delegation edge      -> service, plus a dependency from the agent to it
    classification, auth -> properties, namespaced ``preflight:``

Deliberately not exported: findings. CycloneDX carries vulnerabilities and VEX statements, which is
a different claim from "this composition has a reachable irreversible action", and squeezing one
into the other would produce a document that reads as a CVE. Findings stay in SARIF, which is built
for exactly that.

``preflight scan --cyclonedx DIR`` writes one document per agent. The serial number is the agent's
own, so a CycloneDX consumer and Preflight agree on which composition they are discussing.
"""

from __future__ import annotations

from datetime import UTC, datetime

from preflight.bom.models import AgentBOM, Tool

SPEC_VERSION = "1.6"
NS = "preflight:"


def _props(pairs: dict[str, object]) -> list[dict[str, str]]:
    return [{"name": NS + k, "value": str(v)} for k, v in sorted(pairs.items()) if v is not None]


def _clean(d: dict) -> dict:
    """Drop keys with no value. CycloneDX types a description as a string; ``null`` is not one, and
    an absent field says the same thing without lying about the type."""
    return {k: v for k, v in d.items() if v is not None}


def _tool_props(t: Tool) -> dict[str, object]:
    c = t.classification
    return {
        "tool.kind": t.kind,
        "tool.auth.mode": t.auth.mode,
        "tool.auth.secretRef": t.auth.secretRef,
        "tool.approval": t.approval,
        "classification.untrustedInput": c.untrustedInput if c else None,
        "classification.irreversibleAction": c.irreversibleAction if c else None,
        "classification.source": c.source if c else None,
        "classification.confidence": c.confidence if c else None,
    }


def to_cyclonedx(b: AgentBOM, *, version: str) -> dict:
    """One CycloneDX 1.6 document for one agent."""
    services: list[dict] = []
    components: list[dict] = []
    depends_on: list[str] = []

    for m in b.models:
        ref = f"model:{m.deployment}"
        components.append({
            "type": "machine-learning-model",
            "bom-ref": ref,
            "name": m.model,
            "version": m.version or "unknown",
            "properties": _props({"model.deployment": m.deployment, "model.region": m.region,
                                  "model.status": m.status}),
        })
        depends_on.append(ref)

    edge_targets = {e.tool: e.to for e in b.edges if e.tool}
    for t in b.tools:
        ref = f"tool:{t.id}"
        depends_on.append(ref)
        props = _tool_props(t)
        if t.id in edge_targets:
            props["edge.to"] = edge_targets[t.id]
        if t.source.server:
            services.append(_clean({
                "bom-ref": ref,
                "name": t.name,
                "description": t.description,
                "endpoints": [t.source.server],
                # A service is authenticated when the definition says how. Unknown is not yes.
                "authenticated": t.auth.mode not in ("none", "unknown"),
                # The call leaves this agent's control, which is what a trust boundary means here.
                "x-trust-boundary": True,
                "properties": _props(props),
            }))
        else:
            components.append(_clean({
                "type": "application",
                "bom-ref": ref,
                "name": t.name,
                "description": t.description,
                "properties": _props(props),
            }))

    agent_ref = f"agent:{b.agent.id}"
    doc = {
        "bomFormat": "CycloneDX",
        "specVersion": SPEC_VERSION,
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "tools": {"components": [{"type": "application", "name": "agent-preflight", "version": version}]},
            "component": _clean({
                "type": "application",
                "bom-ref": agent_ref,
                "name": b.agent.name or b.agent.id,
                "description": b.agent.description,
                "properties": _props({
                    "agent.id": b.agent.id,
                    "agent.platform": b.agent.platform,
                    "agent.inboundAuth": b.agent.inboundAuth,
                    "agent.environment": b.agent.environment,
                    "residency.observed": ",".join(b.residency.observed) or None,
                    "economics.tokensPerTurn": (b.economics.instructionTokens or 0)
                    + (b.economics.toolDescriptionTokens or 0)
                    + (b.economics.groundingTokensPerTurn or 0),
                }),
            }),
        },
        "components": components,
        "services": services,
        "dependencies": [{"ref": agent_ref, "dependsOn": sorted(depends_on)}],
    }
    if b.serialNumber:
        doc["serialNumber"] = b.serialNumber
    return doc
