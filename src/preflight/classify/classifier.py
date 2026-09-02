"""Tool classification.

Everything downstream depends on one question: for a given tool, is it an **untrusted input**,
an **irreversible action**, both, or neither.

Four tiers, strongest first. Never a model: a gate has to give the same answer twice, and a
model-classified tool makes a finding non-reproducible.

    0  policy override      the organisation said so
    1  first-party registry curated table of Microsoft built-ins
    2  protocol             MCP ToolAnnotations, HTTP method, connector metadata
    3  fail closed          unknown, so assume both

Two details in tier 2 carry the argument, and both come from the MCP specification rather than
from us:

* The spec says clients MUST treat tool annotations as untrusted unless they come from a trusted
  server. So annotations from an untrusted server may only ever *worsen* a classification. A
  hostile server cannot annotate its way past the gate.
* ``readOnlyHint`` defaults to ``false``. An unannotated tool is already presumed to modify its
  environment by the protocol's own default, so tier 3 is the spec's position, not ours.
"""

from __future__ import annotations

from preflight.bom.models import Classification, Tool
from preflight.classify.registry import FIRST_PARTY
from preflight.policy import Policy

__all__ = ["classify", "FAIL_CLOSED"]

#: Methods that change state. Anything not here is treated as a read.
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
#: Methods whose effect cannot be assumed recoverable.
_IRREVERSIBLE = {"DELETE"}

FAIL_CLOSED = Classification(
    untrustedInput=True,
    irreversibleAction=True,
    source="failclosed",
    confidence="low",
    rationale="Unclassified tool. Assumed to be both an untrusted input and an irreversible action.",
)


def classify(tool: Tool, policy: Policy) -> Classification:
    """Classify one tool. Pure, total, and never raises."""
    return (
        _from_policy(tool, policy)
        or _from_registry(tool)
        or _from_protocol(tool, policy)
        or FAIL_CLOSED
    )


# --- tier 0 ------------------------------------------------------------------------------


def _from_policy(tool: Tool, policy: Policy) -> Classification | None:
    override = policy.tool_overrides.get(tool.id) or policy.tool_overrides.get(tool.name)
    if override is None:
        return None
    return Classification(
        untrustedInput=override.untrusted_input,
        irreversibleAction=override.irreversible_action,
        source="policy",
        confidence="high",
        rationale=f"Policy override in {policy.origin}.",
    )


# --- tier 1 ------------------------------------------------------------------------------


def _from_registry(tool: Tool) -> Classification | None:
    entry = FIRST_PARTY.get(tool.source.builtinId or "")
    if entry is None:
        return None
    return Classification(
        untrustedInput=entry.untrusted_input,
        irreversibleAction=entry.irreversible_action,
        source="registry",
        confidence="high",
        rationale=entry.rationale,
    )


# --- tier 2 ------------------------------------------------------------------------------


def _from_protocol(tool: Tool, policy: Policy) -> Classification | None:
    if tool.kind == "mcp":
        return _from_mcp(tool, policy)
    if tool.kind in ("openapi", "connector"):
        return _from_http(tool)
    return None


def _from_mcp(tool: Tool, policy: Policy) -> Classification | None:
    ann = tool.annotations
    if ann is None:
        # No annotations at all. Tier 3 handles it, and SC-05 reports the server.
        return None

    server = tool.source.server or ""
    trusted = tool.source.trusted or server in policy.trusted_mcp_servers

    if not trusted:
        # MCP spec: annotations from an untrusted server MUST NOT be relied on. They are kept
        # on the tool for the report, but they may only worsen a classification, never improve
        # it, so the fail-closed position stands.
        return Classification(
            untrustedInput=True,
            irreversibleAction=True,
            source="failclosed",
            confidence="low",
            rationale=(
                f"Annotations present but server {server!r} is not on the trusted list, "
                "so they cannot be relied on (MCP spec). Assumed worst case."
            ),
        )

    # readOnlyHint defaults to false: absent means assumed mutating.
    read_only = bool(ann.readOnlyHint)
    destructive = bool(ann.destructiveHint)
    open_world = bool(ann.openWorldHint)

    irreversible = destructive or not read_only
    if irreversible and ann.idempotentHint:
        # Idempotent lowers the blast radius. It does not clear the classification, it is
        # consumed later when ranking path severity.
        pass

    return Classification(
        untrustedInput=open_world,
        irreversibleAction=irreversible,
        source="protocol",
        confidence="high",
        rationale=(
            f"MCP annotations from trusted server {server!r}: "
            f"readOnlyHint={ann.readOnlyHint}, destructiveHint={ann.destructiveHint}, "
            f"openWorldHint={ann.openWorldHint}."
        ),
    )


def _from_http(tool: Tool) -> Classification | None:
    method = (tool.source.httpMethod or "").upper()
    if not method:
        return None
    mutating = method in _MUTATING
    return Classification(
        # A response body from an external host is attacker-influenced content, whatever the
        # method. Only a tool reaching a host inside the estate escapes this, and that is a
        # policy override rather than something the method can tell us.
        untrustedInput=True,
        irreversibleAction=method in _IRREVERSIBLE or mutating,
        source="protocol",
        confidence="high" if method in _IRREVERSIBLE else "medium",
        rationale=f"HTTP {method}: {'state-changing' if mutating else 'read'} operation.",
    )
