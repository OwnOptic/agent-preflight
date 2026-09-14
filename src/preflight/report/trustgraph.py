"""The trust graph, drawn.

The dossier already states the chain in words. A reviewer approving an agent needs to see the shape
of it: who calls whom, how well that call is evidenced, and where the irreversible ends are. This
draws exactly what the BOM says and nothing else, so the picture cannot drift from the finding.

Deterministic: same estate, same bytes. Agents are laid out in call order, edges are labelled with
how the edge was learned, and a dashed edge means the evidence was weaker than a match.
"""

from __future__ import annotations

from html import escape

from preflight.bom.models import AgentBOM

NAVY = "#2A3B4E"
ORANGE = "#F26F21"
MUTED = "#8A96A3"
LINE = "#C9D1D9"
CARD_W, CARD_H, GAP_X, GAP_Y = 220, 62, 76, 34
PAD = 18


def _order(boms: list[AgentBOM]) -> list[AgentBOM]:
    """Callers before callees, then by id. A cycle keeps its first-seen order rather than hanging."""
    by_id = {b.agent.id: b for b in boms}
    incoming = {b.agent.id: 0 for b in boms}
    for b in boms:
        for e in b.edges:
            if e.to in incoming:
                incoming[e.to] += 1
    ordered: list[AgentBOM] = []
    seen: set[str] = set()
    queue = sorted((b for b in boms if incoming[b.agent.id] == 0), key=lambda x: x.agent.id)
    while queue:
        b = queue.pop(0)
        if b.agent.id in seen:
            continue
        seen.add(b.agent.id)
        ordered.append(b)
        for e in sorted(b.edges, key=lambda x: x.to):
            nxt = by_id.get(e.to)
            if nxt is not None and nxt.agent.id not in seen:
                queue.append(nxt)
    ordered += [b for b in sorted(boms, key=lambda x: x.agent.id) if b.agent.id not in seen]
    return ordered


def _sinks(b: AgentBOM) -> list[str]:
    edge_tools = {e.tool for e in b.edges if e.tool}
    return sorted(
        t.name for t in b.tools
        if t.id not in edge_tools and t.classification and t.classification.irreversibleAction
    )


def to_svg(boms: list[AgentBOM], *, focus: str | None = None) -> str:
    ordered = _order(boms)
    rows = {b.agent.id: i for i, b in enumerate(ordered)}
    width = PAD * 2 + CARD_W + GAP_X + 260
    height = PAD * 2 + len(ordered) * (CARD_H + GAP_Y)

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Segoe UI, system-ui, sans-serif">',
        '<defs>',
        f'<marker id="tg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>',
        '</defs>',
        f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>',
    ]

    def y_of(aid: str) -> int:
        return PAD + rows[aid] * (CARD_H + GAP_Y)

    # Edges first, so cards sit on top of the lines.
    for b in ordered:
        for e in b.edges:
            if e.to not in rows:
                continue
            y1, y2 = y_of(b.agent.id) + CARD_H, y_of(e.to)
            x = PAD + CARD_W // 2
            dash = ' stroke-dasharray="4 3"' if e.confidence not in ("proven", "matched") else ""
            out.append(
                f'<path d="M{x},{y1} C{x},{y1 + 18} {x},{y2 - 18} {x},{y2}" fill="none" '
                f'stroke="{MUTED}" stroke-width="1.4"{dash} marker-end="url(#tg-arrow)"/>'
            )
            label = f"{e.via}, {e.confidence}, auth {e.auth}"
            out.append(f'<text x="{x + 10}" y="{(y1 + y2) // 2 + 4}" font-size="10" fill="{MUTED}">{escape(label)}</text>')

    for b in ordered:
        y = y_of(b.agent.id)
        focused = focus is not None and b.agent.id == focus
        stroke = ORANGE if focused else LINE
        out.append(
            f'<rect x="{PAD}" y="{y}" width="{CARD_W}" height="{CARD_H}" rx="8" fill="#FFFFFF" '
            f'stroke="{stroke}" stroke-width="{2 if focused else 1}"/>'
        )
        name = escape((b.agent.name or b.agent.id)[:30])
        out.append(f'<text x="{PAD + 14}" y="{y + 24}" font-size="12.5" font-weight="700" fill="{NAVY}">{name}</text>')
        out.append(f'<text x="{PAD + 14}" y="{y + 42}" font-size="10" fill="{MUTED}">'
                   f'{escape(b.agent.platform)} · inbound {escape(b.agent.inboundAuth)}</text>')
        sinks = _sinks(b)
        if sinks:
            shown = ", ".join(sinks[:3]) + (f" +{len(sinks) - 3}" if len(sinks) > 3 else "")
            out.append(f'<text x="{PAD + CARD_W + 16}" y="{y + 26}" font-size="10.5" fill="{ORANGE}" '
                       f'font-weight="700">irreversible: {escape(shown)}</text>')
            out.append(f'<text x="{PAD + CARD_W + 16}" y="{y + 41}" font-size="9.5" fill="{MUTED}">'
                       f'no human gate declared</text>' if b.guards.humanInTheLoop is not True else "")
    out.append("</svg>")
    return "\n".join(x for x in out if x)
