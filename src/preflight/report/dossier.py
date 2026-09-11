"""Governance dossier, template v1.0.

Every field traces to a BOM field or a rule result. Anything that cannot be derived prints
*requires human input* rather than being invented, so the dossier never manufactures a control
claim it cannot evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone

from preflight.bom.canonical import composition_hash
from preflight.bom.models import AgentBOM
from preflight.rules.catalog import RULES

REQ = "*requires human input*"


def _v(x) -> str:
    return REQ if x in (None, "", []) else str(x)


def _flag(b: bool | None) -> str:
    return "yes" if b else ("no" if b is False else "unknown")


def render_agent(b: AgentBOM, result, *, version: str) -> str:
    aid = b.agent.id
    pv = result.privilege[aid]
    findings = [f for f in result.findings if f.agent == aid]
    edge_ids = {e.tool for e in b.edges}
    names = {x.agent.id: (x.agent.name or x.agent.id) for x in result.boms}
    inbound = [(o, e) for o in result.boms for e in o.edges if e.to == aid]
    involved = [g for g in result.groups
                if g.sink_agent == aid or any(h.agent_id == aid for p in g.paths for h in p.hops)]
    cert = result.certification.get(aid, "uncertified") if result.certification else "uncertified"
    L: list[str] = []
    w = L.append

    w(f"# Governance dossier: {b.agent.name or aid}")
    w("")
    w(f"Template: Agent Governance Dossier v1.0 · Agent Preflight {version} · "
      f"{datetime.now(timezone.utc).date().isoformat()}")
    w("")
    w("> Every field is derived from the AgentBOM or a rule result. Fields that cannot be derived say "
      "*requires human input* rather than guess.")
    w("")

    w("## 1. Identification")
    w("")
    w("| Field | Value |")
    w("|---|---|")
    for k, v in [
        ("Agent id", f"`{aid}`"), ("Platform", b.agent.platform), ("Name", _v(b.agent.name)),
        ("Environment", _v(b.agent.environment)), ("Owner", _v(b.agent.identity.owner)),
        ("Sponsor", _v(b.agent.identity.sponsor)), ("Composition hash", f"`{composition_hash(b)}`"),
        ("Serial", f"`{b.serialNumber}`"), ("Certification", cert), ("Collector", b.generator.collector),
    ]:
        w(f"| {k} | {v} |")
    w("")

    w("## 2. Purpose and intended use")
    w("")
    w(_v(b.agent.description))
    w("")
    w("## 3. Out of scope and prohibited uses")
    w("")
    w(REQ + (f" Declared residency in policy: {result.policy.residency}." if result.policy.residency else ""))
    w("")

    w("## 4. Architecture and trust graph")
    w("")
    w("**Calls**")
    w("")
    if b.edges:
        for e in b.edges:
            w(f"- {names.get(e.to, e.to)} via `{e.tool}` ({e.via}), {e.confidence} by {e.signal}, auth {e.auth}"
              + (", crosses platform" if e.crossPlatform else ""))
    else:
        w("- none in the scanned estate")
    w("")
    w("**Called by**")
    w("")
    if inbound:
        for o, e in inbound:
            w(f"- {o.agent.name or o.agent.id} ({o.agent.platform}), {e.confidence} by {e.signal}, auth {e.auth}")
    else:
        w("- none in the scanned estate")
    w("")

    w("## 5. Composition inventory")
    w("")
    w("| Tool | Kind | Untrusted input | Irreversible | Classified by | Auth |")
    w("|---|---|---|---|---|---|")
    for t in b.tools:
        c = t.classification
        role = " (edge)" if t.id in edge_ids else ""
        w(f"| `{t.name}`{role} | {t.kind} | {_flag(c.untrustedInput if c else None)} | "
          f"{_flag(c.irreversibleAction if c else None)} | {c.source if c else '-'} ({c.confidence if c else '-'}) | "
          f"{t.auth.mode} |")
    if b.models:
        w("")
        w("| Model deployment | Region | Status |")
        w("|---|---|---|")
        for m in b.models:
            w(f"| `{m.deployment}` | {_v(m.region)} | {m.status} |")
    w("")

    w("## 6. Identity and permissions")
    w("")
    w(f"- Identity: {b.agent.identity.kind}, mode {b.agent.identity.mode}")
    w(f"- Inbound authentication: {b.agent.inboundAuth}")
    w(f"- Declared irreversible actions: {len(pv.own)}")
    w(f"- Effective irreversible actions through delegation: {len(pv.effective)}")
    for a, _, n in sorted(pv.gained):
        w(f"  - reaches `{n}` on {names.get(a, a)}, not declared here")
    w("")

    w("## 7. Data, residency and retention")
    w("")
    w(f"- Regions observed: {', '.join(b.residency.observed) or REQ}")
    if b.knowledge:
        for k in b.knowledge:
            w(f"- Knowledge `{k.id}` ({k.kind}), citations required: {_flag(k.citationsRequired)}")
    w(f"- Storage and retention: {'; '.join(f'{s.kind} {s.retentionDays} days' for s in b.storage) or REQ}")
    w("")

    w("## 8. Attack surface analysis")
    w("")
    w(f"- Untrusted inputs: {', '.join(t.name for t in b.tools if t.classification and t.classification.untrustedInput and t.id not in edge_ids) or 'none'}")
    w(f"- Irreversible actions: {', '.join(t.name for t in b.tools if t.classification and t.classification.irreversibleAction and t.id not in edge_ids) or 'none'}")
    w("")
    for g in involved:
        p = g.best
        w(f"**{p.severity.upper()}**: {p.source_label} reaches `{p.sink_tool}`")
        w("")
        w("```")
        w("\n".join(p.chain_lines()))
        w("```")
        w("")

    w("## 9. Responsible AI")
    w("")
    gd = b.guards
    w("| Guard | Value |")
    w("|---|---|")
    for k, v in [("Content filter", gd.contentFilter), ("Prompt shields", _flag(gd.promptShields)),
                 ("Human in the loop", _flag(gd.humanInTheLoop)), ("Token cap", gd.tokenCap if gd.tokenCap is not None else "none"),
                 ("Max turns", gd.maxTurns if gd.maxTurns is not None else "none")]:
        w(f"| {k} | {v} |")
    w("")
    w(f"Known limitations: {REQ}")
    w("")

    w("## 10. Cost and capacity")
    w("")
    e = b.economics
    w(f"- Per turn: {e.instructionTokens} instruction + {e.toolDescriptionTokens} tool-description + "
      f"{e.groundingTokensPerTurn} grounding tokens")
    if not (e.instructionTokens or e.toolDescriptionTokens or e.groundingTokensPerTurn):
        fan = f"unknown, the definition carries nothing to price ({REQ})"
    elif e.fanoutFactor is None:
        fan = "unbounded (delegation cycle)"
    else:
        fan = f"x{e.fanoutFactor}"
    w(f"- Fan-out through delegation: {fan}")
    w(f"- Estimated cost per interaction: "
      f"{f'{e.estimatedCostPerInteraction.value} {e.estimatedCostPerInteraction.currency}' if e.estimatedCostPerInteraction else REQ + ' (no price in policy)'}")
    w("")

    w("## 11. Findings and remediation")
    w("")
    if findings:
        w("| Severity | Rule | Finding | Control |")
        w("|---|---|---|---|")
        for f in findings:
            w(f"| {f.severity} | {f.rule} | {f.message.replace('|', '/')}{' (accepted)' if f.baselined else ''} | {f.control} |")
        w("")
        w(f"Remediation owner and dates: {REQ}")
    else:
        w("No findings.")
    w("")

    w("## 12. Change log and certification")
    w("")
    w(f"- Composition hash: `{composition_hash(b)}`")
    w(f"- Certification: {cert}" + (" (the composition changed after sign-off)" if cert == "void" else ""))
    w(f"- Sign-off: {REQ}")
    w("")

    w("## Appendix A. Control mapping")
    w("")
    w("| Rule | Control | Checks |")
    w("|---|---|---|")
    for r in RULES.values():
        w(f"| {r.id} | {r.control} | {r.title} |")
    w("")

    w("## Appendix B. Full rule results")
    w("")
    fired = {f.rule for f in findings}
    w("| Rule | Result |")
    w("|---|---|")
    for r in RULES.values():
        n = sum(1 for f in findings if f.rule == r.id)
        w(f"| {r.id} | {'fail (' + str(n) + ')' if r.id in fired else 'pass'} |")
    w("")
    return "\n".join(L)
