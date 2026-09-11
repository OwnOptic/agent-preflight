"""Cost analysis, priced from the definition before a token is spent.

Every driver here is readable from the BOM, so the estimate needs no traffic:

* prompt tax        instructions are charged on every turn
* tool surface tax  every tool description sits in the context window on every turn
* grounding         retrieved chunks per turn times chunk size
* fan-out           a delegated agent runs its own turn, with its own prompt and tools

A delegation cycle has no bound, so its fan-out is reported as unknown rather than a number.
Money only appears when the policy carries a price for the model; otherwise the result stays in
tokens, which is still enough to see a regression.
"""

from __future__ import annotations

from preflight.bom.models import AgentBOM, Cost
from preflight.policy import Policy


def per_turn(b: AgentBOM) -> tuple[int, int, int]:
    instructions = b.agent.instructions.tokens or 0
    tool_surface = sum(t.descriptionTokens or 0 for t in b.tools)
    grounding = sum((k.chunkTokens or 0) * (k.chunksPerTurn or 0) for k in b.knowledge)
    return instructions, tool_surface, grounding


def compute(boms: list[AgentBOM], policy: Policy) -> list[AgentBOM]:
    by_id = {b.agent.id: b for b in boms}

    def interaction(aid: str, path: frozenset[str]) -> int | None:
        if aid in path:
            return None
        b = by_id[aid]
        total = sum(per_turn(b))
        for e in b.edges:
            if e.to not in by_id:
                continue
            sub = interaction(e.to, path | {aid})
            if sub is None:
                return None
            total += sub
        return total

    for b in boms:
        i, t, g = per_turn(b)
        base = i + t + g
        inter = interaction(b.agent.id, frozenset())
        e = b.economics
        e.instructionTokens = i
        e.toolDescriptionTokens = t
        e.groundingTokensPerTurn = g
        # A ratio against a zero per-turn cost means nothing, so it is left unknown rather than
        # reported as a huge multiplier. Readers tell "unknown" from "cycle" by the zero token count.
        e.fanoutFactor = None if (inter is None or base == 0) else round(inter / base, 2)
        price = next(
            (policy.prices[k] for m in b.models for k in (m.model, m.deployment) if k in policy.prices),
            None,
        )
        e.estimatedCostPerInteraction = (
            Cost(value=round(inter / 1_000_000 * price, 6), currency=policy.currency)
            if price is not None and inter is not None
            else None
        )
    return boms
