"""The rule engine.

Deterministic, so the gate answers the same twice. Every rule carries an id, a default severity and
a named control, so a finding is audit evidence rather than an opinion. Rule ids match the catalog
in docs/capabilities.md section 4.

Only an explicit bad value is a finding. ``None`` means the definition does not say, and a rule that
fired on silence would drown the real findings in noise.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from preflight.analyze.paths import PathGroup
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
    ]
}


@dataclass
class Context:
    boms: list[AgentBOM]
    groups: list[PathGroup]
    privilege: dict[str, Privilege]
    policy: Policy
    lock: dict[str, str] | None = None
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


RULE_FUNCS = [ap, id_01, id_03, id_08, ts_01, ts_06, ma_08, ra_01, ra_03, ra_04, ra_07, sc_01, sc_05, co_03]


def evaluate(ctx: Context) -> list[Finding]:
    out: list[Finding] = []
    for b in ctx.boms:
        for fn in RULE_FUNCS:
            out.extend(fn(b, ctx))
    out.sort(key=lambda f: (-SEVERITY_ORDER[f.severity], f.rule, f.agent, f.subject))
    return out
