"""Build a sideloadable app package for fixture 01 (inbox triage) into dist/.

The fixture files stay untouched, so the analyzer baseline does not move. The package copy adds
the two icons Teams requires and replaces the placeholder developer URLs.
"""
import json
import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "fixtures" / "01-inbox-triage"
OUT = ROOT / "dist" / "fixture-01"
REPO = "https://github.com/OwnOptic/agent-preflight"


def icons(dest: Path) -> None:
    color = Image.new("RGBA", (192, 192), "#2A3B4E")
    d = ImageDraw.Draw(color)
    d.rounded_rectangle((40, 56, 152, 136), radius=14, outline="#F26F21", width=10)
    d.line((44, 62, 96, 102, 148, 62), fill="#F26F21", width=10, joint="curve")
    color.save(dest / "color.png")
    outline = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(outline)
    d.rectangle((5, 9, 26, 23), outline="white", width=2)
    d.line((6, 10, 16, 17, 25, 10), fill="white", width=2)
    outline.save(dest / "outline.png")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for f in ("declarativeAgent.json", "plugin-contract-router.json", "openapi-contract-router.yaml"):
        shutil.copy2(SRC / f, OUT / f)
    manifest = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    manifest["developer"] = {"name": "Agent Preflight fixtures", "websiteUrl": REPO,
                             "privacyUrl": REPO, "termsOfUseUrl": REPO}
    manifest["icons"] = {"color": "color.png", "outline": "outline.png"}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    icons(OUT)
    zpath = ROOT / "dist" / "fixture-01-inbox-triage.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.iterdir()):
            z.write(p, p.name)
    print(zpath)
    for n in zipfile.ZipFile(zpath).namelist():
        print("  ", n)


if __name__ == "__main__":
    main()
