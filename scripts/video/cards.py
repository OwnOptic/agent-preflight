"""The only frames in the cut that are not a live recording: an opening title, a closing card, and
three frames that present artefacts the tool itself produced.

The two portal frames wrap real captures of the live tenant. The dossier frame carries the actual
SVG Preflight writes, not a redrawing of it. Every caption says where its evidence came from, so a
viewer can tell a recording from a still without being told.
"""
import base64
import io
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("C:/Users/Public/agent-preflight")
CAPS = REPO / "dist" / "captures"
OUT = HERE / "cards"


def png(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def text(p: Path) -> str:
    return io.open(p, encoding="utf-8", errors="replace").read()


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: 1920px; height: 1080px; overflow: hidden; background: #0E1B2A;
       font-family: "Segoe UI", system-ui, sans-serif; color: #F7F9FB; }
.page { position: absolute; inset: 0; padding: 90px 110px; display: flex;
        flex-direction: column; }
h1 { font-size: 104px; letter-spacing: -2px; line-height: 1.02; }
h2 { font-size: 46px; font-weight: 700; letter-spacing: -0.5px; }
.sub { font-size: 34px; color: #9FB3C8; font-weight: 400; line-height: 1.42; }
.accent { color: #F26F21; }
.rule { width: 150px; height: 9px; background: #F26F21; border-radius: 5px; }
.spacer { flex: 1; }
.foot { font-size: 25px; color: #6E8399; letter-spacing: .3px; }

/* A real capture, presented as a capture. */
.shotwrap { flex: 1; display: flex; gap: 42px; align-items: center; min-height: 0; }
.shot { border-radius: 16px; border: 1px solid #223a55; max-height: 100%;
        box-shadow: 0 26px 70px rgba(0,0,0,.55); }
.side { width: 560px; display: flex; flex-direction: column; gap: 22px; }
.side h2 { font-size: 42px; }
.side p { font-size: 27px; color: #9FB3C8; line-height: 1.45; }
.tag { display: inline-block; align-self: flex-start; font-size: 20px; letter-spacing: 1.4px;
       text-transform: uppercase; color: #0E1B2A; background: #58D68D; font-weight: 700;
       padding: 7px 15px; border-radius: 7px; }
.tag.warn { background: #F26F21; color: #0E1B2A; }
.graph { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; }
.graph svg { width: 100%; height: 100%; border-radius: 14px; }

/* Lower third over a live recording. Transparent page, so ffmpeg can overlay it. */
body.strip { background: none; height: 132px; }
.strip .bar { position: absolute; inset: 0; display: flex; align-items: center; gap: 26px;
              padding: 0 74px; background: #0A1420;
              border-top: 4px solid #F26F21; }
.strip .live { font-size: 19px; letter-spacing: 1.6px; text-transform: uppercase;
               font-weight: 700; color: #0E1B2A; background: #F26F21; padding: 7px 14px;
               border-radius: 7px; white-space: nowrap; }
.strip .txt { font-size: 31px; color: #F7F9FB; }
.cards { display: flex; gap: 26px; }
.card { flex: 1; background: #132234; border: 1px solid #223a55; border-radius: 18px;
        padding: 26px 28px; }
.card h3 { font-size: 30px; margin-bottom: 10px; }
.card p { font-size: 23px; color: #9FB3C8; line-height: 1.42; }
"""


def page(body: str) -> str:
    return (f"<!doctype html><meta charset='utf-8'><style>{CSS}</style>"
            f"<div class='page'>{body}</div>")


TITLE = page("""
  <div class='spacer'></div>
  <div class='rule'></div>
  <h1 style='margin-top:34px'>Agent<span class='accent'>&nbsp;Preflight</span></h1>
  <p class='sub' style='margin-top:30px;max-width:1360px'>
    Three agents. Three platforms. Each one reviewed and approved on its own, and every platform
    reports its own agent clean.<br>
    <span style='color:#F7F9FB'>None of them can see what the three of them do together.</span>
  </p>
  <div class='spacer'></div>
  <p class='foot'>Everything after this card is a live screen recording.</p>
""")

CLOSE = page("""
  <div class='rule'></div>
  <h2 style='margin-top:30px'>It runs <span class='accent'>before</span> the agent exists.</h2>
  <p class='sub' style='margin-top:22px;max-width:1500px'>
    No traffic, no tokens, nothing registered. A reviewer gets the finding while it is still
    a pull request, not after an incident.
  </p>
  <div class='spacer'></div>
  <div class='cards'>
    <div class='card'><h3>Five platforms</h3><p>Foundry, Copilot Studio, M365 declarative,
      Agent Framework, Agent 365.</p></div>
    <div class='card'><h3>45 of 62 rules</h3><p>The other 17 are documented with the evidence
      each one would need.</p></div>
    <div class='card'><h3>Standards, not a silo</h3><p>SARIF 2.1.0 and CycloneDX 1.6, both
      validated in CI.</p></div>
    <div class='card'><h3>Feeds the control plane</h3><p>The composition metadata is what
      Agent 365 needs at registration.</p></div>
  </div>
  <div class='spacer'></div>
  <p class='foot'>github.com/OwnOptic/agent-preflight &nbsp;&middot;&nbsp; Elliot Margot</p>
""")


def portal(shot: Path, tag: str, head: str, body: str, foot: str) -> str:
    return page(f"""
  <div class='rule'></div>
  <h2 style='margin-top:24px'>{head}</h2>
  <div class='shotwrap' style='margin-top:30px'>
    <img class='shot' src='{png(shot)}'>
    <div class='side'>
      <span class='tag'>{tag}</span>
      <p>{body}</p>
    </div>
  </div>
  <p class='foot' style='margin-top:26px'>{foot}</p>
""")


P_M365 = portal(
    CAPS / "fixture-01-copilot-agent-card.png", "reports clean",
    "The platform's own view, one",
    "Inbox triage, live in the Microsoft 365 Copilot agent store. Nothing here is wrong. "
    "Everything it can see about this agent is fine.",
    "Real capture, Microsoft 365 Copilot, demo tenant, 14 September 2026.")

P_CS = portal(
    CAPS / "fixture-02-copilot-studio-agent.png", "reports clean",
    "The platform's own view, two",
    "Contract router, published in Copilot Studio and answering. Also fine, on its own terms. "
    "It cannot see the agent it hands work to.",
    "Real capture, Copilot Studio, demo tenant, published 14 September 2026.")


def dossier_card() -> str:
    svg = text(REPO / "dossier" / "m365-declarative--01-inbox-triage.svg")
    svg = re.sub(r"<svg ", "<svg preserveAspectRatio='xMidYMid meet' ", svg, count=1)
    return page(f"""
  <div class='rule'></div>
  <h2 style='margin-top:24px'>What the reviewer actually signs</h2>
  <p class='sub' style='margin-top:14px;font-size:29px'>
    The dossier draws the trust graph from the bill of materials, and the certification voids on any
    change to the composition hash.</p>
  <div class='graph' style='margin-top:18px'>{svg}</div>
  <p class='foot'>Written by <span style='color:#F26F21'>preflight scan --dossier</span>.
     This is the file, not a redrawing of it.</p>
""")


def strip(label: str, txt: str) -> str:
    return (f"<!doctype html><meta charset='utf-8'><style>{CSS}</style>"
            f"<body class='strip'><div class='bar'>"
            f"<span class='live'>{label}</span><span class='txt'>{txt}</span></div>")


# One per live-recorded segment, so a viewer always knows which screen they are looking at.
STRIPS = {
    "cap-scan": strip("live capture", "<b>preflight scan</b> reads the three definitions. "
                                      "No traffic, no tokens, nothing deployed."),
    "cap-whatif": strip("live capture", "<b>preflight whatif</b>: what one approval gate would "
                                        "actually change, before anyone builds it."),
    "cap-gate": strip("live capture", "The same scan in CI, on the branch where an approved server "
                                      "rewrote one tool description."),
    "cap-run": strip("live capture", "The real workflow run on the public repository. "
                                     "Failure, 28 seconds, no model in the loop."),
    "cap-diff": strip("live capture", "The diff a reviewer would approve. One line of prose, "
                                      "and it instructs the model."),
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, html_ in [("title", TITLE), ("portal-m365", P_M365), ("portal-cs", P_CS),
                        ("dossier", dossier_card()), ("close", CLOSE), *STRIPS.items()]:
        p = OUT / f"{name}.html"
        p.write_text(html_, encoding="utf-8")
        print(f"  {p.name}  {len(html_) // 1024} KB")


if __name__ == "__main__":
    main()
