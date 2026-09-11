"""Effective privilege closure.

An agent's real privilege is not what it declares. It is everything it can reach: its own
irreversible tools, plus those of every agent it can delegate to, transitively, across platform
boundaries. When the effective set is larger than the declared one, the agent can cause effects no
reviewer of its own definition ever saw. That is ID-08.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from preflight.bom.models import AgentBOM

#: (agent id, tool id, tool name)
Capability = tuple[str, str, str]


@dataclass
class Privilege:
    own: set[Capability] = field(default_factory=set)
    effective: set[Capability] = field(default_factory=set)
    reached: list[str] = field(default_factory=list)

    @property
    def gained(self) -> set[Capability]:
        return self.effective - self.own


def closure(boms: list[AgentBOM]) -> dict[str, Privilege]:
    by_id = {b.agent.id: b for b in boms}
    edge_ids = {b.agent.id: {e.tool for e in b.edges if e.tool} for b in boms}

    def own(b: AgentBOM) -> set[Capability]:
        return {
            (b.agent.id, t.id, t.name)
            for t in b.tools
            if t.id not in edge_ids[b.agent.id]
            and t.classification
            and t.classification.irreversibleAction
        }

    result: dict[str, Privilege] = {}
    for b in boms:
        seen, stack, reached = {b.agent.id}, [b.agent.id], []
        while stack:
            aid = stack.pop()
            a = by_id[aid]
            for e in a.edges:
                carrier = next((t for t in a.tools if t.id == e.tool), None)
                if carrier is not None and carrier.approval is True:
                    continue
                if e.to in by_id and e.to not in seen:
                    seen.add(e.to)
                    stack.append(e.to)
                    reached.append(e.to)
        mine = own(b)
        eff = set(mine)
        for r in reached:
            eff |= own(by_id[r])
        result[b.agent.id] = Privilege(own=mine, effective=eff, reached=sorted(reached))
    return result
