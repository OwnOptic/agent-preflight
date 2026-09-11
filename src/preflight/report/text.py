"""The terminal report. The headline path first, because that is the finding nobody else can produce."""

from __future__ import annotations

from collections import Counter

from preflight.findings import SEVERITIES


def _name(result, agent_id: str) -> str:
    b = next((x for x in result.boms if x.agent.id == agent_id), None)
    return ((b.agent.name if b else None) or agent_id)[:22]


def render(result, *, version: str) -> str:
    L: list[str] = []
    platforms = sorted({b.agent.platform for b in result.boms})
    ntools = sum(len(b.tools) for b in result.boms)
    L.append(f"Agent Preflight {version}   {len(result.boms)} agents on {len(platforms)} platforms, "
             f"{ntools} tools   read-only, no traffic, no tokens")
    for platform, why in result.skipped:
        L.append(f"  skipped {platform}: {why}")
    L.append("")

    critical = [g for g in result.groups if g.best.severity == "critical"]
    head = critical[0] if critical else (result.groups[0] if result.groups else None)
    if head:
        p = head.best
        rid = "AP-02" if p.cross_platform else "AP-01"
        across = f" across {len(set(p.platforms))} platforms" if p.cross_platform else ""
        L.append(f"{p.severity.upper():9} {rid}  Untrusted input reaches an irreversible action{across}, no human gate")
        for line in p.chain_lines():
            L.append("    " + line)
        if p.cross_platform:
            L.append("    Each hop was reviewed on its own platform. The defect exists only in the composition.")
        L.append("")

    counts = Counter(f.severity for f in result.findings)
    accepted = sum(1 for f in result.findings if f.baselined)
    L.append("FINDINGS   " + "  ".join(f"{s} {counts.get(s, 0)}" for s in SEVERITIES)
             + (f"   ({accepted} accepted in baseline)" if accepted else ""))
    for f in result.findings:
        msg = f.message if len(f.message) <= 96 else f.message[:93] + "..."
        L.append(f"  {f.severity:9} {f.rule:6} {_name(result, f.agent):22} {msg}"
                 + ("  [baseline]" if f.baselined else ""))
    L.append("")

    L.append("PRIVILEGE   declared irreversible actions, and what delegation actually reaches")
    for b in result.boms:
        pv = result.privilege[b.agent.id]
        L.append(f"  {_name(result, b.agent.id):22} declares {len(pv.own)}, reaches {len(pv.effective)}")
    L.append("")

    L.append("COST   tokens per turn: instructions + tool descriptions + grounding, then fan-out")
    for b in result.boms:
        e = b.economics
        if not (e.instructionTokens or e.toolDescriptionTokens or e.groundingTokensPerTurn):
            fan = "unknown, the definition carries nothing to price"
        elif e.fanoutFactor is None:
            fan = "unbounded (cycle)"
        else:
            fan = f"x{e.fanoutFactor}"
        money = (f"   ~{e.estimatedCostPerInteraction.value} {e.estimatedCostPerInteraction.currency}"
                 if e.estimatedCostPerInteraction else "")
        L.append(f"  {_name(result, b.agent.id):22} {e.instructionTokens} + {e.toolDescriptionTokens} + "
                 f"{e.groundingTokensPerTurn} tokens, fan-out {fan}{money}")

    if result.certification:
        L.append("")
        L.append("CERTIFICATION")
        for b in result.boms:
            L.append(f"  {_name(result, b.agent.id):22} {result.certification.get(b.agent.id, 'uncertified')}")
    return "\n".join(L)
