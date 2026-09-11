"""Attack path analysis, the headline.

A path runs from an **untrusted input** to an **irreversible action** with no human gate in between.
It is followed through the tool graph inside an agent, and through edges between agents, including
edges that cross platforms. That last part is the one nothing else can see: each platform's own
tooling looks at one hop and reports it clean.

Two modelling decisions, both deliberate:

* Inside one agent, the model mediates every tool. Content any tool returns can steer the model into
  calling any other tool, so an untrusted source and an irreversible sink in the same agent connect.
* A tool whose call resolves to another agent in the estate is an **edge**, not a sink. Delegating to
  a governed agent is followed transitively rather than reported as a terminal side effect. Only an
  irreversible tool that acts outside the estate is a sink.

Severity is gated on evidence. A path is Critical only when every edge on it was proven or matched
and the sink's irreversibility was declared rather than assumed. Anything weaker is reported one
level lower as a possible path. The tool never claims certainty it has not earned.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from preflight.bom.models import AgentBOM, Tool
from preflight.findings import SEVERITY_ORDER

#: Built-ins that pull open-world content. They rank first as sources, because "web content" is the
#: clearest possible way to say untrusted.
OPEN_WORLD = {
    "web_search", "bing_grounding", "bing_custom_search", "browser_automation",
    "computer_use", "deep_research",
}
MESSAGE_SOURCES = {"email", "teams_messages"}
UNTRUSTED_KNOWLEDGE = {"sharepoint", "files", "bing", "web", "ai-search", "other"}


@dataclass
class Hop:
    agent_id: str
    agent_name: str | None
    platform: str
    via_tool: str | None = None
    via_method: str | None = None
    confidence: str | None = None
    auth: str | None = None


@dataclass
class AttackPath:
    source_agent: str
    source_label: str
    source_rank: int
    hops: list[Hop]
    sink_agent: str
    sink_tool: str
    sink_tool_id: str
    sink_desc: str
    sink_confidence: str
    edge_confidences: list[str] = field(default_factory=list)

    @property
    def platforms(self) -> list[str]:
        return [h.platform for h in self.hops]

    @property
    def cross_platform(self) -> bool:
        return len(set(self.platforms)) > 1

    @property
    def severity(self) -> str:
        edges_proven = all(c in ("proven", "matched") for c in self.edge_confidences)
        return "critical" if edges_proven and self.sink_confidence == "high" else "high"

    def chain_lines(self) -> list[str]:
        first = self.hops[0]
        lines = [f"{self.source_label}  [{first.agent_name or first.agent_id}, {first.platform}]"]
        for h in self.hops[1:]:
            call = " ".join(x for x in (h.via_method, h.via_tool) if x)
            lines.append(
                f"  -> {call} ({h.confidence}, auth {h.auth})"
                f"  -> [{h.agent_name or h.agent_id}, {h.platform}]"
            )
        lines.append(f"  -> {self.sink_tool}  IRREVERSIBLE ({self.sink_desc})")
        return lines


@dataclass
class PathGroup:
    """All paths ending at one sink. Reported once, with the strongest path as the evidence."""

    sink_agent: str
    sink_tool_id: str
    paths: list[AttackPath]

    @property
    def best(self) -> AttackPath:
        return sorted(
            self.paths,
            key=lambda p: (
                -SEVERITY_ORDER[p.severity],
                -len(set(p.platforms)),
                p.source_rank,
                -len(p.hops),
                p.source_label,
            ),
        )[0]

    @property
    def sources(self) -> list[str]:
        return sorted({f"{p.hops[0].agent_name or p.source_agent}: {p.source_label}" for p in self.paths})


def _sink_desc(t: Tool) -> str:
    c = t.classification
    if t.kind == "mcp":
        if t.annotations and t.annotations.destructiveHint:
            return "MCP, destructiveHint: true"
        if c and c.source == "failclosed":
            return "MCP, assumed: server not trusted"
        return "MCP"
    if t.source.httpMethod:
        return f"HTTP {t.source.httpMethod}"
    return c.source if c else "unclassified"


def _sources(b: AgentBOM, edge_ids: set[str]) -> list[tuple[str, int, str]]:
    out = []
    for t in b.tools:
        if t.id in edge_ids:
            continue
        c = t.classification
        if not c or not c.untrustedInput:
            continue
        bid = t.source.builtinId or ""
        if bid in OPEN_WORLD:
            label, rank = f"web content via {t.name}", 0
        elif bid in MESSAGE_SOURCES:
            label, rank = f"inbound messages via {t.name}", 1
        elif t.kind == "mcp":
            label, rank = f"output of {t.name}", 3
        else:
            label, rank = f"content via {t.name}", 2
        out.append((label, rank, t.id))
    for k in b.knowledge:
        if k.kind in UNTRUSTED_KNOWLEDGE:
            out.append((f"knowledge source {k.id}", 2, f"knowledge:{k.id}"))
    return out


def find_paths(boms: list[AgentBOM]) -> list[AttackPath]:
    by_id = {b.agent.id: b for b in boms}
    edge_ids = {b.agent.id: {e.tool for e in b.edges if e.tool} for b in boms}
    tools = {b.agent.id: {t.id: t for t in b.tools} for b in boms}

    paths: list[AttackPath] = []
    for b in boms:
        for label, rank, src_id in _sources(b, edge_ids[b.agent.id]):
            start = Hop(b.agent.id, b.agent.name, b.agent.platform)
            stack = [(b.agent.id, [start], [], {b.agent.id})]
            while stack:
                aid, hops, confs, seen = stack.pop()
                a = by_id[aid]
                if a.guards.humanInTheLoop is True:
                    continue
                for t in a.tools:
                    if t.id in edge_ids[aid] or t.approval is True:
                        continue
                    if aid == b.agent.id and t.id == src_id:
                        continue
                    c = t.classification
                    if not c or not c.irreversibleAction:
                        continue
                    paths.append(
                        AttackPath(
                            source_agent=b.agent.id,
                            source_label=label,
                            source_rank=rank,
                            hops=list(hops),
                            sink_agent=aid,
                            sink_tool=t.name,
                            sink_tool_id=t.id,
                            sink_desc=_sink_desc(t),
                            sink_confidence=c.confidence,
                            edge_confidences=list(confs),
                        )
                    )
                for e in a.edges:
                    if e.to in seen or e.to not in by_id:
                        continue
                    et = tools[aid].get(e.tool or "")
                    if et is not None and et.approval is True:
                        continue
                    tgt = by_id[e.to]
                    stack.append(
                        (
                            e.to,
                            hops
                            + [
                                Hop(
                                    tgt.agent.id,
                                    tgt.agent.name,
                                    tgt.agent.platform,
                                    via_tool=et.name if et else e.via,
                                    via_method=et.source.httpMethod if et else None,
                                    confidence=e.confidence,
                                    auth=e.auth,
                                )
                            ],
                            confs + [e.confidence],
                            seen | {e.to},
                        )
                    )
    return paths


def group(paths: list[AttackPath]) -> list[PathGroup]:
    buckets: dict[tuple[str, str], list[AttackPath]] = {}
    for p in paths:
        buckets.setdefault((p.sink_agent, p.sink_tool_id), []).append(p)
    groups = [PathGroup(a, t, ps) for (a, t), ps in buckets.items()]
    return sorted(
        groups,
        key=lambda g: (-SEVERITY_ORDER[g.best.severity], -len(set(g.best.platforms)), g.best.sink_tool),
    )
