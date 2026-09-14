"""Gallery images for the hackathon project page.

A gallery image is read without narration and often without the description, so each one has to
carry its own claim and say where its evidence came from. Everything inside the frames is real:
console output from the tool, pages on github.com, the tenant's own portals, and the SVG the
dossier writes.

Same palette and type as the video, so the page reads as one piece of work.
"""
import base64
import io
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("C:/Users/Public/agent-preflight")
CAPS = REPO / "dist" / "captures"
SHOTS = HERE / "shots"
OUT = HERE / "gallery"


def png(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def text(p: Path) -> str:
    return io.open(p, encoding="utf-8", errors="replace").read()


def svg(p: Path) -> str:
    return re.sub(r"<svg ", "<svg preserveAspectRatio='xMidYMid meet' ", text(p), count=1)


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: 1920px; height: 1080px; overflow: hidden; background: #0E1B2A;
       font-family: "Segoe UI", system-ui, sans-serif; color: #F7F9FB; }
.page { position: absolute; inset: 0; padding: 62px 78px 54px; display: flex;
        flex-direction: column; }
.rule { width: 132px; height: 8px; background: #F26F21; border-radius: 4px; }
h2 { font-size: 52px; font-weight: 700; letter-spacing: -0.6px; margin-top: 22px; }
.lede { font-size: 29px; color: #9FB3C8; margin-top: 12px; line-height: 1.38; max-width: 1560px; }
.accent { color: #F26F21; }
.frame { flex: 1; min-height: 0; margin-top: 26px; border-radius: 16px; overflow: hidden;
         border: 1px solid #223a55; background: #0A1420; display: flex;
         align-items: center; justify-content: center; }
.frame img { width: 100%; height: 100%; object-fit: contain; object-position: top left; }
.frame.pad { padding: 22px; background: #ffffff; }
.frame.pad svg { width: 100%; height: 100%; }
.frame.contain img { object-position: center; }
.foot { font-size: 23px; color: #6E8399; margin-top: 20px; }
.pair { flex: 1; min-height: 0; margin-top: 26px; display: flex; gap: 26px; }
.pair figure { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.pair img { width: 100%; border-radius: 14px; border: 1px solid #223a55; }
.pair figcaption { font-size: 24px; color: #9FB3C8; margin-top: 14px; }
.tag { display: inline-block; font-size: 18px; letter-spacing: 1.3px; text-transform: uppercase;
       font-weight: 700; color: #0E1B2A; background: #58D68D; padding: 6px 13px;
       border-radius: 6px; margin-bottom: 10px; align-self: flex-start; }
"""


def page(body: str) -> str:
    return f"<!doctype html><meta charset='utf-8'><style>{CSS}</style><div class='page'>{body}</div>"


def shot(head, lede, img, foot, cls="frame"):
    return page(f"""
      <div class='rule'></div><h2>{head}</h2><p class='lede'>{lede}</p>
      <div class='{cls}'><img src='{png(img)}'></div>
      <p class='foot'>{foot}</p>""")


PAGES = {
    "01-critical-path": shot(
        "One critical path, across three platforms",
        "Three agents, each reviewed and approved on its own. Preflight reads their definitions and "
        "finds the chain none of the three platforms can see. No traffic, no tokens, nothing deployed.",
        SHOTS / "scan.png",
        "Real console output. <span class='accent'>preflight scan fixtures --policy policy.example.yaml</span>"),

    "02-platforms-clean": page(f"""
      <div class='rule'></div><h2>Every platform reports its own agent clean</h2>
      <p class='lede'>Neither view is wrong. Each one sees a single hop, and a single hop is fine.
        The defect exists only in the composition.</p>
      <div class='pair'>
        <figure><span class='tag'>reports clean</span>
          <img src='{png(CAPS / "fixture-01-copilot-agent-card.png")}'>
          <figcaption>Inbox triage, live in the Microsoft 365 Copilot agent store.</figcaption></figure>
        <figure><span class='tag'>reports clean</span>
          <img src='{png(CAPS / "fixture-02-copilot-studio-agent.png")}'>
          <figcaption>Contract router, published in Copilot Studio and answering.</figcaption></figure>
      </div>
      <p class='foot'>Real captures of the demo tenant, 14 September 2026.</p>"""),

    "03-ci-gate": shot(
        "The build fails, in a branch that looks routine",
        "An approved MCP server rewrote one tool description. Same tools, same model, same allow "
        "list. Two independent rules fire, and neither needs the agent to run.",
        SHOTS / "gate.png",
        "Real console output, exit code 1, on the <span class='accent'>demo/rug-pull</span> branch"),

    "04-injected-line": shot(
        "The line a reviewer would approve",
        "Prose, in a routine diff, that instructs the model to delete records and hide it. The tool "
        "is still annotated <span class='accent'>readOnlyHint: true</span>.",
        SHOTS / "ghdiff.png",
        "github.com/OwnOptic/agent-preflight pull request #1, public, read signed out",
        cls="frame contain"),

    "05-ci-run": shot(
        "Failing in CI on a public repository",
        "The finding lands where the work is: a pull request check, 28 seconds, no model in the "
        "loop. The engineer shipping the agent finds out here, and so does the reviewer.",
        SHOTS / "ghrun.png",
        "Real GitHub Actions run, public, read signed out"),

    "06-trust-graph": page(f"""
      <div class='rule'></div><h2>What the reviewer actually signs</h2>
      <p class='lede'>The dossier draws the trust graph from the bill of materials, names each edge's
        evidence, and the certification voids on any change to the composition hash.</p>
      <div class='frame pad'>{svg(REPO / "dossier" / "m365-declarative--01-inbox-triage.svg")}</div>
      <p class='foot'>Written by <span class='accent'>preflight scan --dossier</span>. This is the
        file, not a redrawing of it.</p>"""),

    "07-architecture": page(f"""
      <div class='rule'></div><h2>How it works</h2>
      <p class='lede'>Collectors resolve each agent into an AgentBOM, the analyzer reasons over the
        composition, and the output is standards-based: SARIF for code scanning, CycloneDX 1.6 for
        the bill of materials.</p>
      <div class='frame pad'>{svg(REPO / "docs" / "architecture.svg")}</div>
      <p class='foot'>45 of 62 catalogued rules implemented. Italic items are roadmap, and are
        marked as such.</p>"""),
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, html in PAGES.items():
        (OUT / f"{name}.html").write_text(html, encoding="utf-8")
        print(f"  {name}.html  {len(html) // 1024} KB")


if __name__ == "__main__":
    main()
