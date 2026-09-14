"""Render the governance dossier as the document it is, so it can be looked at.

The dossier is what Preflight writes for a reviewer to sign. It is markdown on disk; this renders
it on paper so the structure, the evidence column and the honest "requires human input" fields are
visible at a glance. Only the subset of markdown the dossier actually uses is handled, and anything
unrecognised is passed through escaped rather than silently dropped.
"""
import html
import io
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("C:/Users/Public/agent-preflight")
SRC = REPO / "docs" / "example-output" / "dossier"
OUT = HERE / "dossier-render"

CSS = """
* { box-sizing: border-box; }
body { margin: 0; background: #E7EBF0; font-family: "Segoe UI", system-ui, sans-serif;
       color: #1B2C44; }
.paper { width: 1240px; margin: 0 auto; background: #fff; padding: 74px 86px 90px;
         box-shadow: 0 2px 26px rgba(0,0,0,.12); }
h1 { font-size: 40px; letter-spacing: -0.8px; margin: 0 0 10px; }
h2 { font-size: 26px; margin: 40px 0 14px; padding-bottom: 9px;
     border-bottom: 2px solid #F26F21; }
h3 { font-size: 20px; margin: 26px 0 10px; }
p  { font-size: 16.5px; line-height: 1.62; margin: 10px 0; }
blockquote { margin: 18px 0; padding: 14px 20px; background: #FDF3EC;
             border-left: 4px solid #F26F21; font-size: 16px; color: #4A3B32; }
table { border-collapse: collapse; width: 100%; margin: 14px 0 20px; font-size: 15px; }
th { text-align: left; background: #F2F5F8; color: #33465E; font-weight: 700;
     padding: 9px 12px; border-bottom: 2px solid #D5DEE8; }
td { padding: 9px 12px; border-bottom: 1px solid #E6ECF2; vertical-align: top; }
tr:last-child td { border-bottom: none; }
code { font-family: "Cascadia Mono", Consolas, monospace; font-size: 13.5px;
       background: #F2F5F8; padding: 2px 6px; border-radius: 4px; color: #1B2C44; }
em { color: #8A6A55; font-style: italic; }
ul { margin: 10px 0 10px 22px; } li { font-size: 16.5px; line-height: 1.6; margin: 5px 0; }
.meta { font-size: 14.5px; color: #6E8399; margin-bottom: 4px; }
hr { border: none; border-top: 1px solid #E6ECF2; margin: 30px 0; }
"""


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def convert(md: str, assets: Path) -> str:
    """assets is the directory the dossier's own image references resolve against."""
    out, rows, in_list = [], [], False

    def flush_table():
        nonlocal rows
        if not rows:
            return
        head, body = rows[0], [r for r in rows[1:] if not re.fullmatch(r"[\s|:-]+", "|".join(r))]
        out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>")
        for r in body:
            out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
        out.append("</table>")
        rows = []

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for line in md.replace("\r", "").split("\n"):
        if line.startswith("|"):
            flush_list()
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
            continue
        flush_table()
        if not line.strip():
            flush_list()
            continue
        # The dossier references its own trust graph. Draw it where it is referenced, rather than
        # printing the markdown source of the reference.
        if m := re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip()):
            flush_list()
            asset = assets / m.group(2)
            if asset.suffix == ".svg" and asset.exists():
                svg = io.open(asset, encoding="utf-8").read()
                out.append(re.sub(r"<svg ", "<svg style='width:100%;height:auto;"
                                  "border:1px solid #E6ECF2;border-radius:10px' ", svg, count=1))
            else:
                out.append(f"<p><em>missing asset: {html.escape(m.group(2))}</em></p>")
            continue
        if m := re.match(r"^(#{1,3})\s+(.*)", line):
            flush_list()
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif line.startswith(">"):
            flush_list()
            out.append(f"<blockquote>{inline(line.lstrip('> ').strip())}</blockquote>")
        elif re.match(r"^\s*[-*]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"^\s*[-*]\s+", "", line)
            out.append(f"<li>{inline(item)}</li>")
        elif line.strip() == "---":
            flush_list()
            out.append("<hr>")
        else:
            flush_list()
            out.append(f"<p>{inline(line)}</p>")
    flush_table()
    flush_list()
    return "\n".join(out)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for md_path in sorted(SRC.glob("*.md")):
        md = io.open(md_path, encoding="utf-8").read()
        doc = (f"<!doctype html><meta charset='utf-8'><style>{CSS}</style>"
               f"<div class='paper'>{convert(md, SRC)}</div>")
        p = OUT / (md_path.stem + ".html")
        p.write_text(doc, encoding="utf-8")
        print(f"  {p.name}")


if __name__ == "__main__":
    main()
