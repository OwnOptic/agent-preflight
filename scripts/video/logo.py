"""Agent Preflight identity.

The mark is the product's own argument: three agents, two hops, drawn so the path itself forms a
check. The last hop is orange because that is the one that reaches the irreversible action, and the
third node is the one nobody was looking at. It reads as "verified" at a glance and as "a path"
once you look, which is exactly the claim.

Hand-authored SVG, personal palette: orange #F26F21 on navy. No gradients in the mark itself, so it
survives being shrunk to a favicon or printed in one colour.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "logo"

ORANGE = "#F26F21"
NAVY = "#14243A"
NAVY_DEEP = "#0E1B2A"
MUTED = "#8FA6BF"
PAPER = "#F5F7FA"


def mark(size: int, bg: str | None, node: str, link: str, accent: str, ring: bool = True) -> str:
    """The logomark on its own. Coordinates are in a 512 grid, scaled by the caller."""
    r = size / 512
    def s(v: float) -> float:
        return round(v * r, 2)

    bgrect = (f"<rect width='{size}' height='{size}' rx='{s(116)}' fill='{bg}'/>" if bg else "")
    # A (top left) -> B (the vertex, bottom) -> C (top right): a path that is also a check.
    # Coordinates are set so the glyph's bounding box is centred in the 512 grid, ring or no ring.
    ax, ay, bx, by, cx, cy = 144, 204, 226, 338, 366, 176
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
  {bgrect}
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="M{s(ax)} {s(ay)} L{s(bx)} {s(by)}" stroke="{link}" stroke-width="{s(26)}"/>
    <path d="M{s(bx)} {s(by)} L{s(cx)} {s(cy)}" stroke="{accent}" stroke-width="{s(34)}"/>
  </g>
  <circle cx="{s(ax)}" cy="{s(ay)}" r="{s(30)}" fill="{bg or PAPER}" stroke="{node}" stroke-width="{s(18)}"/>
  <circle cx="{s(bx)}" cy="{s(by)}" r="{s(30)}" fill="{bg or PAPER}" stroke="{node}" stroke-width="{s(18)}"/>
  <circle cx="{s(cx)}" cy="{s(cy)}" r="{s(40)}" fill="{accent}"/>
</svg>"""


def lockup(w: int, h: int, bg: str, node: str, link: str, accent: str, word: str, sub: str) -> str:
    m = mark(int(h * 0.74), None, node, link, accent)
    m = m.replace('<svg xmlns="http://www.w3.org/2000/svg"', '<svg')
    inner = m[m.index(">") + 1:m.rindex("</svg>")]
    side = int(h * 0.13)
    box = int(h * 0.74)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <rect width="{w}" height="{h}" fill="{bg}"/>
  <svg x="{side}" y="{side}" width="{box}" height="{box}" viewBox="0 0 {box} {box}">{inner}</svg>
  <g font-family="Segoe UI, system-ui, sans-serif">
    <text x="{side + box + int(h * 0.20)}" y="{int(h * 0.50)}" font-size="{int(h * 0.30)}"
          font-weight="700" letter-spacing="-1.5" fill="{node}">Agent <tspan fill="{accent}">Preflight</tspan></text>
    <text x="{side + box + int(h * 0.20) + 4}" y="{int(h * 0.72)}" font-size="{int(h * 0.128)}"
          fill="{link}">{sub}</text>
  </g>
</svg>"""


FILES = {
    # Square icon, dark. The default.
    "mark-dark.svg": mark(1024, NAVY_DEEP, PAPER, MUTED, ORANGE),
    # Square icon, light, for a white page.
    "mark-light.svg": mark(1024, PAPER, "#33465E", "#9AAEC4", ORANGE),
    # Transparent mark, for placing on anything.
    "mark-bare.svg": mark(1024, None, PAPER, MUTED, ORANGE).replace(
        f"fill='{PAPER}' stroke", "fill='none' stroke"),
    "lockup-dark.svg": lockup(1680, 420, NAVY_DEEP, PAPER, MUTED, ORANGE,
                              "Agent Preflight", "Design-time governance for Microsoft agents"),
    "lockup-light.svg": lockup(1680, 420, PAPER, "#1B2C44", "#6E8399", ORANGE,
                               "Agent Preflight", "Design-time governance for Microsoft agents"),
}


COVER = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">
  <defs>
    <linearGradient id="apf-bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{NAVY_DEEP}"/><stop offset="1" stop-color="{NAVY}"/>
    </linearGradient>
  </defs>
  <rect width="1920" height="1080" fill="url(#apf-bg)"/>
  <rect x="0" y="0" width="1920" height="9" fill="{ORANGE}"/>
  <svg x="150" y="292" width="340" height="340" viewBox="0 0 340 340">
    {mark(340, None, PAPER, MUTED, ORANGE).split(">", 1)[1].rsplit("</svg>", 1)[0]}
  </svg>
  <g font-family="Segoe UI, system-ui, sans-serif" fill="{PAPER}">
    <text x="566" y="447" font-size="108" font-weight="700" letter-spacing="-2.5">Agent <tspan fill="{ORANGE}">Preflight</tspan></text>
    <text x="570" y="514" font-size="37" fill="{MUTED}">Design-time governance for Microsoft agents</text>
    <text x="570" y="596" font-size="31" fill="{PAPER}">Finds the attack path that crosses three agents and three platforms,</text>
    <text x="570" y="642" font-size="31" fill="{PAPER}">before any of them ships.</text>
    <text x="570" y="722" font-size="26" fill="{MUTED}">No traffic &#183; no tokens &#183; nothing deployed &#183; runs before registration</text>
  </g>
</svg>"""

FILES["cover.svg"] = COVER


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, body in FILES.items():
        (OUT / name).write_text(body, encoding="utf-8")
        print(f"  {name}")


if __name__ == "__main__":
    main()
