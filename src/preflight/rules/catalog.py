"""The rule engine.

Deterministic, so the gate answers the same twice. Every rule carries an id, a default severity and
a named control, so a finding is audit evidence rather than an opinion. Rule ids match the catalog
in docs/capabilities.md section 4.

Only an explicit bad value is a finding. ``None`` means the definition does not say, and a rule that
fired on silence would drown the real findings in noise.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit

from preflight.analyze.paths import PathGroup
from preflight.certify import tokens_per_interaction
from preflight.analyze.privilege import Privilege
from preflight.bom.models import AgentBOM
from preflight.findings import SEVERITY_ORDER, Finding
from preflight.policy import Policy


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: str
    control: str


RULES: dict[str, Rule] = {
    r.id: r
    for r in [
        Rule("AP-01", "Untrusted input reaches an irreversible action with no human gate", "critical", "ZT: communication governance"),
        Rule("AP-02", "Attack path crosses a platform boundary with no human gate", "critical", "ZT: communication governance"),
        Rule("ID-01", "Unauthenticated call or published endpoint", "critical", "ZT: agent identity and RBAC"),
        Rule("ID-03", "Secret held inline rather than as a Key Vault reference", "critical", "ZT: agent identity and RBAC"),
        Rule("ID-08", "Effective privilege exceeds declared privilege through delegation", "high", "ZT: agent identity and RBAC"),
        Rule("TS-01", "MCP endpoint attached without a tool allowlist", "high", "ZT: communication governance"),
        Rule("TS-06", "Capability granted but never referenced in the instructions", "medium", "ZT: agent identity and RBAC"),
        Rule("MA-08", "Cross-platform edge authenticated by key rather than a shared Entra identity", "high", "ZT: agent identity and RBAC"),
        Rule("RA-01", "Content filter absent", "critical", "CAF: prepare environment"),
        Rule("RA-03", "Prompt shields disabled", "critical", "CAF: prepare environment"),
        Rule("RA-04", "Grounding configured with no citation requirement", "medium", "CAF: data privacy"),
        Rule("RA-07", "Declarative agent with no disclaimer", "low", "CAF: prepare environment"),
        Rule("SC-01", "Remote MCP tool manifest changed since it was pinned", "critical", "ZT: communication governance"),
        Rule("SC-05", "MCP tools fall to the fail-closed tier", "medium", "ZT: communication governance"),
        Rule("CO-03", "No token cap and no max-turn limit", "high", "CAF: track and allocate costs"),
        Rule("AP-04", "Reachable irreversible action with no confirmation declared", "high", "ZT: communication governance"),
        Rule("ID-02", "Shared credential across agents", "critical", "ZT: agent identity and RBAC"),
        Rule("TS-04", "Toolbox floating on default rather than pinned", "high", "CAF: standardise protocols"),
        Rule("TS-05", "Duplicate or shadowed tool names", "low", "CAF: standardise protocols"),
        Rule("TS-08", "Mutating operation leaves the estate with no human gate", "high", "ZT: communication governance"),
        Rule("MA-02", "Recursive or cyclic delegation path", "high", "ZT: communication governance"),
        Rule("MA-04", "Delegation crosses a residency boundary", "high", "CAF: data residency"),
        Rule("MA-07", "Outbound endpoint unresolvable, target unknown", "medium", "ZT: agent inventory and discovery"),
        Rule("DR-01", "Region outside the declared residency policy", "critical", "CAF: data residency"),
        Rule("DR-05", "Memory or vector store with no sanitisation", "high", "ZT: memory and retrieval hygiene"),
        Rule("RA-05", "No human in the loop declared for an irreversible action", "high", "ZT: communication governance"),
        Rule("RA-08", "Model knowledge left enabled on a grounded agent", "low", "CAF: prepare environment"),
        Rule("SC-06", "Annotations accepted from a server that is not trusted", "medium", "ZT: communication governance"),
        Rule("CO-01", "Cost per interaction exceeds the declared budget", "high", "CAF: track and allocate costs"),
        Rule("CO-06", "Instructions near the character cap and unpriced", "low", "CAF: track and allocate costs"),
        Rule("CO-07", "Tool surface costs more per turn than the instructions", "medium", "CAF: track and allocate costs"),
        Rule("CO-09", "No conversation history summarisation", "low", "CAF: systematize cost optimization"),
        Rule("AP-03", "Attack path crosses a residency or tenant boundary", "critical", "CAF: data residency"),
        Rule("ID-04", "Key authentication where the policy requires a stronger mode", "high", "ZT: agent identity and RBAC"),
        Rule("MA-01", "A2A endpoint attached without an allowlist", "critical", "ZT: communication governance"),
        Rule("MA-03", "Delegation crosses a tenant boundary", "high", "CAF: data residency"),
        Rule("ML-01", "Model deployment deprecated or retired", "high", "CAF: govern AI models"),
        Rule("ML-03", "Model not on the permitted list", "high", "CAF: govern AI models"),
        Rule("ML-05", "No recertification within the policy window", "medium", "ZT: lifecycle management"),
        Rule("CO-02", "Cost per interaction regressed beyond the allowed delta", "high", "CAF: track and allocate costs"),
        Rule("CO-08", "No cost centre recorded for the agent", "medium", "CAF: track and allocate costs"),
        Rule("SC-02", "Injection payload in a tool description", "critical", "ZT: memory and retrieval hygiene"),
        Rule("TS-02", "Tool surface far beyond what the instructions reference", "medium", "ZT: agent identity and RBAC"),
        Rule("ID-07", "No accountable owner or sponsor in the registry", "medium", "CAF: accountability"),
        Rule("MA-05", "Delegation to an agent absent from the registry", "medium", "ZT: agent inventory and discovery"),
    ]
}

#: HTTP verbs that change something on the callee.
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
#: Tool kinds whose call can leave this agent for somewhere else.
_OUTBOUND = ("openapi", "connector", "a2a")


@dataclass
class Context:
    boms: list[AgentBOM]
    groups: list[PathGroup]
    privilege: dict[str, Privilege]
    policy: Policy
    lock: dict[str, str] | None = None
    #: The certification record, when one was supplied. Two rules compare today against sign-off:
    #: CO-02 (cost regression) and ML-05 (review expiry).
    cert: dict | None = None
    by_id: dict[str, AgentBOM] = field(init=False)

    def __post_init__(self) -> None:
        self.by_id = {b.agent.id: b for b in self.boms}


def _mk(rid: str, bom: AgentBOM, message: str, *, subject: str, severity: str | None = None,
        chain: list[str] | None = None) -> Finding:
    r = RULES[rid]
    return Finding(
        rule=rid,
        severity=severity or r.severity,
        title=r.title,
        message=message,
        agent=bom.agent.id,
        agent_name=bom.agent.name,
        platform=bom.agent.platform,
        control=r.control,
        location=bom.agent.sourceFile,
        subject=subject,
        chain=chain or [],
    )


def _host(url: str | None) -> str:
    return urlsplit(url).netloc if url else ""


def _name(ctx: Context, agent_id: str) -> str:
    b = ctx.by_id.get(agent_id)
    return (b.agent.name if b else None) or agent_id


# --- attack paths ------------------------------------------------------------------------


def ap(bom: AgentBOM, ctx: Context) -> list[Finding]:
    out = []
    for g in ctx.groups:
        if g.sink_agent != bom.agent.id:
            continue
        p = g.best
        rid = "AP-02" if p.cross_platform else "AP-01"
        possible = p.severity != "critical"
        n = len(set(p.platforms))
        msg = (
            f"{'Possible path: ' if possible else ''}{p.source_label} reaches `{p.sink_tool}` "
            f"({p.sink_desc})"
            + (f" across {n} platforms" if p.cross_platform else "")
            + f", with no human gate anywhere on the path. {len(g.sources)} source(s) reach this sink."
        )
        if possible:
            msg += " Reported one level lower because the sink's irreversibility is assumed, not declared."
        out.append(_mk(rid, bom, msg, subject=f"sink:{p.sink_tool_id}", severity=p.severity,
                       chain=p.chain_lines()))
    return out


# --- identity ----------------------------------------------------------------------------


def id_01(bom: AgentBOM, ctx: Context) -> list[Finding]:
    out = []
    for t in bom.tools:
        if t.kind in ("openapi", "connector", "mcp", "a2a") and t.auth.mode == "none":
            out.append(_mk("ID-01", bom, f"`{t.name}` calls {_host(t.source.server) or 'its target'} with no authentication.",
                           subject=t.id))
    if bom.agent.inboundAuth == "none" and bom.agent.endpoints:
        # Fires before publication too: catching this at design time is the point.
        text = (f"Configured for unauthenticated callers; once published, {bom.agent.endpoints[0]} accepts anyone."
                if bom.tags.get("published") == "False" else
                f"Published endpoint accepts unauthenticated callers: {bom.agent.endpoints[0]}")
        out.append(_mk("ID-01", bom, text, subject="inbound"))
    return out


def id_03(bom: AgentBOM, ctx: Context) -> list[Finding]:
    out, seen = [], set()
    for t in bom.tools:
        if (t.auth.secretRef or "").lower() != "inline":
            continue
        key = t.source.server or t.id
        if key in seen:
            continue
        seen.add(key)
        target = _host(t.source.server) or t.name
        out.append(_mk("ID-03", bom, f"Credential for {target} is stored inline in the definition, not as a Key Vault reference.",
                       subject=key))
    return out


def id_08(bom: AgentBOM, ctx: Context) -> list[Finding]:
    p = ctx.privilege.get(bom.agent.id)
    if not p or not p.gained:
        return []
    gained = sorted(f"{_name(ctx, a)}/{n}" for a, _, n in p.gained)
    shown = ", ".join(gained[:4]) + (f" and {len(gained) - 4} more" if len(gained) > 4 else "")
    return [_mk("ID-08", bom,
                f"Declares {len(p.own)} irreversible action(s) but can reach {len(p.effective)} through delegation, "
                f"including {shown}. None of those appear in this agent's own definition.",
                subject="closure")]


# --- tool surface ------------------------------------------------------------------------


def ts_01(bom: AgentBOM, ctx: Context) -> list[Finding]:
    by_server: dict[str, list[str]] = defaultdict(list)
    for t in bom.tools:
        if t.kind == "mcp" and t.source.allowlist is False:
            by_server[t.source.server or t.id].append(t.name)
    return [
        _mk("TS-01", bom, f"MCP server {_host(s) or s} is attached with no tool allowlist, exposing all {len(n)} of its tools: {', '.join(sorted(n))}.",
            subject=s)
        for s, n in sorted(by_server.items())
    ]


def ts_06(bom: AgentBOM, ctx: Context) -> list[Finding]:
    if bom.agent.platform != "m365-declarative":
        return []
    return [
        _mk("TS-06", bom, f"Capability `{t.name}` is granted but the instructions never call for it.", subject=t.id)
        for t in bom.tools
        if t.kind == "builtin" and t.referencedInInstructions is False
    ]


# --- multi-agent -------------------------------------------------------------------------


def ma_08(bom: AgentBOM, ctx: Context) -> list[Finding]:
    return [
        _mk("MA-08", bom,
            f"Calls {_name(ctx, e.to)} on another platform using a key, so the callee cannot tell which agent is calling or on whose behalf.",
            subject=f"edge:{e.to}")
        for e in bom.edges
        if e.crossPlatform and e.auth == "key"
    ]


# --- responsible AI ----------------------------------------------------------------------


def ra_01(bom: AgentBOM, ctx: Context) -> list[Finding]:
    return [_mk("RA-01", bom, "No content filter is configured.", subject="contentFilter")] \
        if bom.guards.contentFilter == "none" else []


def ra_03(bom: AgentBOM, ctx: Context) -> list[Finding]:
    return [_mk("RA-03", bom, "Prompt shields are disabled, so jailbreak and indirect injection attempts are not screened.",
                subject="promptShields")] if bom.guards.promptShields is False else []


def ra_04(bom: AgentBOM, ctx: Context) -> list[Finding]:
    return [
        _mk("RA-04", bom, f"Knowledge source `{k.id}` grounds answers with no citation requirement.", subject=k.id)
        for k in bom.knowledge
        if k.citationsRequired is False
    ]


def ra_07(bom: AgentBOM, ctx: Context) -> list[Finding]:
    if bom.agent.platform != "m365-declarative" or bom.tags.get("disclaimer") is not None:
        return []
    return [_mk("RA-07", bom, "No disclaimer is shown to users.", subject="disclaimer")]


# --- supply chain ------------------------------------------------------------------------


def sc_01(bom: AgentBOM, ctx: Context) -> list[Finding]:
    if not ctx.lock:
        return []
    out, seen = [], set()
    for t in bom.tools:
        s = t.source.server
        if t.kind != "mcp" or not s or s in seen or s not in ctx.lock:
            continue
        seen.add(s)
        if t.source.manifestHash and t.source.manifestHash != ctx.lock[s]:
            out.append(_mk("SC-01", bom,
                           f"The tool manifest served by {_host(s)} no longer matches the one pinned at approval. "
                           "Descriptions, schemas or the tool list changed after review.",
                           subject=s))
    return out


def sc_05(bom: AgentBOM, ctx: Context) -> list[Finding]:
    by_server: dict[str, list] = defaultdict(list)
    for t in bom.tools:
        if t.kind == "mcp" and t.classification and t.classification.source == "failclosed":
            by_server[t.source.server or t.id].append(t)
    out = []
    for s, ts in sorted(by_server.items()):
        unannotated = [t for t in ts if t.annotations is None]
        why = ("carry no annotations" if len(unannotated) == len(ts)
               else "come from a server that is not on the trusted list, so their read-only claims cannot be relied on")
        out.append(_mk("SC-05", bom, f"{len(ts)} tool(s) from {_host(s) or s} fall back to the worst case because they {why}: "
                       f"{', '.join(sorted(t.name for t in ts))}.", subject=s))
    return out


# --- cost --------------------------------------------------------------------------------


def co_03(bom: AgentBOM, ctx: Context) -> list[Finding]:
    if bom.agent.platform != "foundry":
        return []
    g = bom.guards
    if g.tokenCap is None and g.maxTurns is None and "guards" in (bom.tags.get("declared") or ""):
        return [_mk("CO-03", bom, "No token cap and no max-turn limit, so a runaway loop has no ceiling.", subject="guards")]
    return []


# --- rules added after the first cut ------------------------------------------------------
#
# Every one of these fires on an explicit value only. Where a platform does not expose a field, the
# rule stays silent rather than reading unknown as bad. Two deliberate exclusions, so the noisy
# obvious version of a rule does not drown the real ones:
#
#   * A call that resolves to another governed agent is a delegation, not an external mutation. The
#     path rules already follow it, so TS-08 ignores it.
#   * AP-04 covers irreversible actions that no untrusted path reaches. Anything reachable from
#     untrusted input is an AP-01 or AP-02 finding already.


def _edge_tool_ids(bom: AgentBOM) -> set[str]:
    return {e.tool for e in bom.edges if e.tool}


def ap_04(bom: AgentBOM, ctx: Context) -> list[Finding]:
    if bom.guards.humanInTheLoop is True:
        return []
    reported = {g.sink_tool_id for g in ctx.groups if g.sink_agent == bom.agent.id}
    edges = _edge_tool_ids(bom)
    out = []
    for t in bom.tools:
        c = t.classification
        if not c or not c.irreversibleAction or t.id in reported or t.approval is True:
            continue
        # A call that resolves to another governed agent is a delegation, not a terminal side
        # effect. paths.py follows it; reporting it here as well would double-count the same hop.
        if t.id in edges:
            continue
        out.append(_mk("AP-04", bom,
                       f"`{t.name}` is irreversible ({c.source}) and no confirmation step is declared before it runs. "
                       "No untrusted source reaches it today, so a change upstream is all it would take.",
                       subject=t.id))
    return out


def id_02(bom: AgentBOM, ctx: Context) -> list[Finding]:
    app = (bom.agent.identity.appId or "").lower()
    if not app:
        return []
    others = sorted(b.agent.name or b.agent.id for b in ctx.boms
                    if b.agent.id != bom.agent.id and (b.agent.identity.appId or "").lower() == app)
    if not others:
        return []
    return [_mk("ID-02", bom, f"Runs as the same application identity as {', '.join(others)}, so the callee cannot "
                              "tell these agents apart and permissions cannot be scoped per agent.",
                subject=f"appId:{app}")]


def ts_04(bom: AgentBOM, ctx: Context) -> list[Finding]:
    floating = sorted({t.source.toolbox or t.name for t in bom.tools if t.source.pinned is False})
    return [_mk("TS-04", bom, f"Toolbox `{n}` floats on its default version, so its tool set can change without any "
                              "change to this agent.", subject=f"toolbox:{n}")
            for n in floating]


def ts_05(bom: AgentBOM, ctx: Context) -> list[Finding]:
    by_name: dict[str, set[str]] = defaultdict(set)
    for t in bom.tools:
        by_name[t.name].add(t.source.server or t.source.toolbox or t.kind)
    return [_mk("TS-05", bom, f"`{n}` is offered by {len(s)} different sources ({', '.join(sorted(_host(x) or x for x in s))}), "
                              "so which one the model calls is not determined by the definition.", subject=f"dup:{n}")
            for n, s in sorted(by_name.items()) if len(s) > 1]


def ts_08(bom: AgentBOM, ctx: Context) -> list[Finding]:
    if bom.guards.humanInTheLoop is True:
        return []
    edges = _edge_tool_ids(bom)
    return [
        _mk("TS-08", bom, f"`{t.name}` is a {t.source.httpMethod} to {_host(t.source.server) or 'an external host'} "
                          "outside the governed estate, with no confirmation step declared.", subject=t.id)
        for t in bom.tools
        if t.kind in _OUTBOUND and t.id not in edges and t.approval is not True
        and (t.source.httpMethod or "").upper() in _MUTATING
    ]


def ma_02(bom: AgentBOM, ctx: Context) -> list[Finding]:
    """A cycle reachable from this agent, reported on the agent where it closes."""
    graph = {b.agent.id: [e.to for e in b.edges] for b in ctx.boms}
    stack = [(bom.agent.id, [bom.agent.id])]
    seen_cycles: set[tuple[str, ...]] = set()
    out = []
    while stack:
        node, trail = stack.pop()
        for nxt in graph.get(node, []):
            if nxt in trail:
                cycle = tuple(trail[trail.index(nxt):] + [nxt])
                if cycle in seen_cycles or cycle[0] != bom.agent.id:
                    continue
                seen_cycles.add(cycle)
                out.append(_mk("MA-02", bom, "Delegation loops back on itself: "
                               + " -> ".join(_name(ctx, a) for a in cycle)
                               + ". Each hop looks finite; the loop is not.",
                               subject="cycle:" + ">".join(cycle)))
                continue
            if len(trail) < 12:
                stack.append((nxt, trail + [nxt]))
    return out


def ma_04(bom: AgentBOM, ctx: Context) -> list[Finding]:
    return [_mk("MA-04", bom, f"Delegates to {_name(ctx, e.to)} in a different data boundary, so the data in the "
                              "request leaves this agent's region.", subject=f"region-edge:{e.to}")
            for e in bom.edges if e.crossRegion]


def ma_07(bom: AgentBOM, ctx: Context) -> list[Finding]:
    edges = _edge_tool_ids(bom)
    unresolved: dict[str, list[str]] = defaultdict(list)
    for t in bom.tools:
        if t.kind in _OUTBOUND and t.id not in edges and t.source.server:
            unresolved[_host(t.source.server) or t.source.server].append(t.name)
    return [_mk("MA-07", bom, f"Calls {h}, which matches no agent in the estate, so what is on the other side is "
                              f"outside this review: {', '.join(sorted(n))}.", subject=f"unresolved:{h}")
            for h, n in sorted(unresolved.items())]


def dr_01(bom: AgentBOM, ctx: Context) -> list[Finding]:
    allowed = {r.lower() for r in ctx.policy.allowed_regions}
    if not allowed:
        return []
    seen: list[tuple[str, str]] = []
    seen += [(m.region, f"model deployment `{m.deployment}`") for m in bom.models if m.region]
    seen += [(k.region, f"knowledge source `{k.id}`") for k in bom.knowledge if k.region]
    seen += [(s.region, f"{s.kind} storage") for s in bom.storage if s.region]
    seen += [(r, "the agent itself") for r in bom.residency.observed]
    out, reported = [], set()
    for region, what in seen:
        if region.lower() in allowed or region in reported:
            continue
        reported.add(region)
        out.append(_mk("DR-01", bom, f"{what} runs in `{region}`, which the policy ({ctx.policy.origin}) does not allow.",
                       subject=f"region:{region}"))
    return out


def dr_05(bom: AgentBOM, ctx: Context) -> list[Finding]:
    return [_mk("DR-05", bom, f"{s.kind} store `{s.resource or s.kind}` declares no sanitisation, so anything written "
                              "into it is read back as trusted context later.", subject=f"store:{s.resource or s.kind}")
            for s in bom.storage if s.sanitised is False]


def ra_05(bom: AgentBOM, ctx: Context) -> list[Finding]:
    if bom.guards.humanInTheLoop is not False:
        return []
    irreversible = [t.name for t in bom.tools if t.classification and t.classification.irreversibleAction]
    if not irreversible:
        return []
    return [_mk("RA-05", bom, f"Human in the loop is switched off while {len(irreversible)} irreversible action(s) are "
                              f"attached: {', '.join(sorted(irreversible))}.", subject="humanInTheLoop")]


def ra_08(bom: AgentBOM, ctx: Context) -> list[Finding]:
    """Only for platforms whose manifest carries the flag: leaving it unset there is a choice."""
    if bom.agent.platform != "m365-declarative" or bom.tags.get("discourageModelKnowledge") is not None:
        return []
    grounded = [t.name for t in bom.tools if t.kind == "builtin"]
    if not grounded:
        return []
    return [_mk("RA-08", bom, "Grounding capabilities are attached but `discourage_model_knowledge` is unset, so the "
                              "model may answer from training data and present it like grounded content.",
                subject="discourageModelKnowledge")]


def sc_06(bom: AgentBOM, ctx: Context) -> list[Finding]:
    trusted = {s.lower() for s in ctx.policy.trusted_mcp_servers}
    by_server: dict[str, list[str]] = defaultdict(list)
    for t in bom.tools:
        s = t.source.server or ""
        if (t.kind == "mcp" and t.annotations is not None and t.classification
                and t.classification.source == "protocol" and _host(s).lower() not in trusted):
            by_server[s].append(t.name)
    return [_mk("SC-06", bom, f"The classification of {', '.join(sorted(n))} rests on annotations from {_host(s) or s}, "
                              "which is not on the trusted list. They were accepted only because they make the "
                              "classification worse.", subject=f"annotations:{s}")
            for s, n in sorted(by_server.items())]


def co_01(bom: AgentBOM, ctx: Context) -> list[Finding]:
    budget = ctx.policy.budget_per_interaction
    cost = bom.economics.estimatedCostPerInteraction
    if budget is None or cost is None or cost.value <= budget:
        return []
    return [_mk("CO-01", bom, f"Costs {cost.value:.4f} {cost.currency} per interaction against a declared budget of "
                              f"{budget:.4f}.", subject="budget")]


def co_06(bom: AgentBOM, ctx: Context) -> list[Finding]:
    i = bom.agent.instructions
    if not i.capChars or not i.tokens or ctx.policy.prices:
        return []
    used = i.tokens * 4
    if used < i.capChars * 0.9:
        return []
    return [_mk("CO-06", bom, f"Instructions use roughly {used} of the {i.capChars} character cap, and the policy "
                              "carries no prices, so nobody can see what that costs per turn.", subject="instructions")]


def co_07(bom: AgentBOM, ctx: Context) -> list[Finding]:
    e = bom.economics
    if not e.instructionTokens or not e.toolDescriptionTokens:
        return []
    if e.toolDescriptionTokens <= e.instructionTokens:
        return []
    return [_mk("CO-07", bom, f"Tool descriptions cost {e.toolDescriptionTokens} tokens every turn against "
                              f"{e.instructionTokens} for the instructions, so most of the prompt is the tool surface.",
                subject="toolsurface")]


def co_09(bom: AgentBOM, ctx: Context) -> list[Finding]:
    return [_mk("CO-09", bom, "Conversation history is never summarised, so every turn re-sends the whole thread.",
                subject="historySummarisation")] if bom.guards.historySummarisation is False else []


# --- third cut: boundaries, model lifecycle, and what a description can carry ---------------


def _geo(region: str | None) -> str | None:
    from preflight.resolve.edges import geo
    return geo(region)


def ap_03(bom: AgentBOM, ctx: Context) -> list[Finding]:
    """A path that leaves the data boundary it started in. Reported on the sink, like AP-01/02."""
    out = []
    for g in ctx.groups:
        if g.sink_agent != bom.agent.id:
            continue
        p = g.best
        geos: list[tuple[str, str]] = []
        for h in p.hops:
            b = ctx.by_id.get(h.agent_id)
            for r in (b.residency.observed if b else []):
                gg = _geo(r)
                if gg:
                    geos.append((h.agent_name or h.agent_id, gg))
        distinct = {g2 for _, g2 in geos}
        crosses_tenant = any(e.crossTenant for b in ctx.boms for e in b.edges)
        if len(distinct) < 2 and not crosses_tenant:
            continue
        where = ", ".join(f"{n} in {g2}" for n, g2 in dict.fromkeys(geos))
        out.append(_mk("AP-03", bom,
                       f"The path to `{p.sink_tool}` crosses a data boundary: {where}. "
                       "Whatever the untrusted source injects travels with it.",
                       subject=f"boundary:{p.sink_tool_id}", chain=p.chain_lines()))
    return out


def id_04(bom: AgentBOM, ctx: Context) -> list[Finding]:
    """Key auth where the policy requires a stronger mode.

    Only keys: an unauthenticated call is ID-01's, and reporting it twice helps nobody. Grouped by
    target, because one key on one connection is one decision however many tools ride on it.
    """
    required = {m.lower() for m in ctx.policy.required_auth_modes}
    if not required or "key" in required:
        return []
    by_target: dict[str, list[str]] = defaultdict(list)
    for t in bom.tools:
        if t.auth.mode == "key":
            by_target[_host(t.source.server) or t.source.server or t.id].append(t.name)
    return [
        _mk("ID-04", bom, f"Authenticates to {target} with a key, where the policy ({ctx.policy.origin}) allows only "
                          f"{', '.join(sorted(required))}. Affects {len(names)} tool(s).", subject=f"auth:{target}")
        for target, names in sorted(by_target.items())
    ]


def ma_01(bom: AgentBOM, ctx: Context) -> list[Finding]:
    return [
        _mk("MA-01", bom, f"Agent-to-agent endpoint `{t.name}` is attached with no allowlist, so which agents it "
                          "may reach is not constrained by the definition.", subject=t.id)
        for t in bom.tools
        if t.kind == "a2a" and t.source.allowlist is False
    ]


def ma_03(bom: AgentBOM, ctx: Context) -> list[Finding]:
    return [
        _mk("MA-03", bom, f"Delegates to {_name(ctx, e.to)} in another tenant, so this estate's controls stop at "
                          "the boundary.", subject=f"tenant-edge:{e.to}")
        for e in bom.edges if e.crossTenant
    ]


def ml_01(bom: AgentBOM, ctx: Context) -> list[Finding]:
    retired = {m.lower() for m in ctx.policy.deprecated_models}
    out = []
    for m in bom.models:
        why = None
        if m.status in ("deprecated", "retired"):
            why = f"the platform reports it as {m.status}"
        elif m.model.lower() in retired or m.deployment.lower() in retired:
            why = f"the policy ({ctx.policy.origin}) lists it as deprecated"
        if why:
            out.append(_mk("ML-01", bom, f"Deployment `{m.deployment}` runs `{m.model}` and {why}. The agent stops "
                                         "working when it goes, and nothing in the definition says when that is.",
                           subject=f"model:{m.deployment}"))
    return out


def ml_03(bom: AgentBOM, ctx: Context) -> list[Finding]:
    allowed = {m.lower() for m in ctx.policy.allowed_models}
    if not allowed:
        return []
    return [
        _mk("ML-03", bom, f"`{m.model}` is not on the permitted model list in {ctx.policy.origin}.",
            subject=f"model-allowed:{m.deployment}")
        for m in bom.models if m.model.lower() not in allowed
    ]


def _cert_entry(ctx: Context, agent_id: str) -> dict | None:
    for a in (ctx.cert or {}).get("agents", []):
        if a.get("id") == agent_id:
            return a
    return None


def ml_05(bom: AgentBOM, ctx: Context) -> list[Finding]:
    days = ctx.policy.recertify_days
    entry = _cert_entry(ctx, bom.agent.id)
    when = (ctx.cert or {}).get("certifiedAt")
    if not days or entry is None or not when:
        return []
    try:
        signed = datetime.fromisoformat(when)
    except ValueError:
        return []
    if signed.tzinfo is None:
        signed = signed.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - signed).days
    if age <= days:
        return []
    return [_mk("ML-05", bom, f"Last certified {age} days ago, and the policy ({ctx.policy.origin}) requires review "
                              f"every {days}.", subject="recertification")]


def co_02(bom: AgentBOM, ctx: Context) -> list[Finding]:
    delta = ctx.policy.max_cost_delta_pct
    entry = _cert_entry(ctx, bom.agent.id)
    if delta is None or entry is None:
        return []
    now_cost = bom.economics.estimatedCostPerInteraction
    was_cost = entry.get("costPerInteraction")
    if now_cost and was_cost and was_cost.get("value"):
        before, after, unit = float(was_cost["value"]), now_cost.value, now_cost.currency
    else:
        before, after, unit = entry.get("tokensPerInteraction"), tokens_per_interaction(bom), "tokens"
        if not before or not after:
            return []
    grew = (after - before) / before * 100
    if grew <= delta:
        return []
    return [_mk("CO-02", bom, f"Costs {after} {unit} per interaction against {before} at sign-off, {grew:.0f}% more, "
                              f"where the policy allows {delta:.0f}%.", subject="cost-delta")]


def co_08(bom: AgentBOM, ctx: Context) -> list[Finding]:
    if not ctx.policy.require_cost_centre:
        return []
    tag = ctx.policy.cost_centre_tag
    if (bom.tags.get(tag) or "").strip():
        return []
    return [_mk("CO-08", bom, f"No `{tag}` tag, so this agent's spend cannot be attributed to anyone.",
                subject="costcentre")]


#: Phrases in a tool description that address the model rather than describe the tool. A description
#: is prompt text: whoever writes it is writing instructions the agent will read every turn.
_INJECTION = [
    (re.compile(r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+instructions", re.I), "overrides the agent's instructions"),
    (re.compile(r"disregard\s+(the\s+)?(previous|prior|above|system)", re.I), "overrides the agent's instructions"),
    (re.compile(r"do\s+not\s+(tell|inform|mention\s+to|reveal\s+to)\s+the\s+user", re.I), "tells the agent to hide something from the user"),
    (re.compile(r"without\s+(asking|confirming|telling|notifying)\s+(the\s+)?(user|anyone)", re.I), "tells the agent to skip confirmation"),
    (re.compile(r"(reveal|print|output|send)\s+(the\s+)?(system\s+prompt|instructions|api[_\- ]?key|secret|token)", re.I), "asks the agent to disclose secrets or its prompt"),
    (re.compile(r"you\s+(must|should|will)\s+always\s+call", re.I), "compels the agent to call it"),
    (re.compile(r"[​-‏‪-‮⁦-⁩]"), "contains hidden bidirectional or zero-width characters"),
    (re.compile(r"[A-Za-z0-9+/]{160,}={0,2}"), "contains a long encoded blob"),
]


def sc_02(bom: AgentBOM, ctx: Context) -> list[Finding]:
    out = []
    for t in bom.tools:
        text = t.description or ""
        if not text:
            continue
        for pattern, why in _INJECTION:
            m = pattern.search(text)
            if not m:
                continue
            snippet = re.sub(r"\s+", " ", m.group(0))[:60]
            out.append(_mk("SC-02", bom, f"The description of `{t.name}` {why}: \"{snippet}\". A tool description is "
                                         "prompt text, read every turn, and nothing here was reviewed as prompt.",
                           subject=f"description:{t.id}"))
            break
    return out


def ts_02(bom: AgentBOM, ctx: Context) -> list[Finding]:
    unreferenced = sorted(t.name for t in bom.tools if t.referencedInInstructions is False)
    if len(unreferenced) < 3:
        return []
    return [_mk("TS-02", bom, f"{len(unreferenced)} of {len(bom.tools)} tools are never called for in the "
                              f"instructions: {', '.join(unreferenced)}. Every one of them is in the context window "
                              "on every turn, and reachable on every turn.", subject="toolsurface-count")]


# --- what the registry knows and a definition cannot ---------------------------------------
#
# Both stay silent unless an Agent 365 registry was actually read. Without it, absence of an agent
# from the registry is absence of evidence, not evidence of absence.


def _registry(ctx: Context) -> list[AgentBOM]:
    return [b for b in ctx.boms if b.tags.get("registry") == "agent365"]


def id_07(bom: AgentBOM, ctx: Context) -> list[Finding]:
    if bom.tags.get("registry") != "agent365":
        return []
    if (bom.tags.get("owner") or "").strip():
        return []
    return [_mk("ID-07", bom, "Registered with no owner and no sponsor, so nobody is accountable for what it does "
                              "or for retiring it.", subject="accountability")]


def ma_05(bom: AgentBOM, ctx: Context) -> list[Finding]:
    reg = _registry(ctx)
    if not reg:
        return []
    known = {b.agent.id.lower() for b in reg} | {
        (b.agent.identity.appId or "").lower() for b in reg if b.agent.identity.appId
    }
    out = []
    for e in bom.edges:
        target = ctx.by_id.get(e.to)
        if target is None or target.tags.get("registry") == "agent365":
            continue
        ids = {target.agent.id.lower()} | ({target.agent.identity.appId.lower()} if target.agent.identity.appId else set())
        if ids & known:
            continue
        out.append(_mk("MA-05", bom, f"Delegates to {_name(ctx, e.to)}, which is not in the agent registry, so the "
                                     "control plane does not know it exists.", subject=f"unregistered:{e.to}"))
    return out


RULE_FUNCS = [ap, ap_03, ap_04, id_01, id_02, id_03, id_04, id_07, id_08, ma_05, ts_01, ts_02, ts_04, ts_05, ts_06, ts_08,
              ma_01, ma_02, ma_03, ma_04, ma_07, ma_08, dr_01, dr_05, ml_01, ml_03, ml_05, ra_01, ra_03,
              ra_04, ra_05, ra_07, ra_08, sc_01, sc_02, sc_05, sc_06, co_01, co_02, co_03, co_06, co_07,
              co_09]


def evaluate(ctx: Context) -> list[Finding]:
    out: list[Finding] = []
    for b in ctx.boms:
        for fn in RULE_FUNCS:
            out.extend(fn(b, ctx))
    out.sort(key=lambda f: (-SEVERITY_ORDER[f.severity], f.rule, f.agent, f.subject))
    return out
