"""Cut the real recordings into the beat sheet and concatenate.

Seven of the nine segments are screen recordings made on this machine: three of a console really
running the tool, four of pages on github.com read signed out. The remaining two are a title and a
closing card. Each recorded segment carries a strip saying it is a live capture, so the two kinds
are never confused.

Segment boundaries were measured from the captures with ffmpeg scene detection, not guessed.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CARDS = HERE / "cards"
SEG = HERE / "seg"
TERM = HERE / "term.mp4"
GH = next((HERE / "raw-gh").glob("*.webm"))

FPS = 30
W, H = 1920, 1080

# The injected tool description runs to x=1560 in the source frame, so the crop cannot be tighter
# than that without cutting the very sentence the shot exists to show.
DIFF_CROP = "crop=1560:345:33:395"

# name, kind, source, start, duration, caption strip, optional crop
PLAN = [
    ("01-title",    "still", CARDS / "title.png",        None,  6.60,  None),
    ("02-scan",     "clip",  TERM,                        0.00, 16.10, "cap-scan"),
    ("03-m365",     "still", CARDS / "portal-m365.png",  None,  7.80,  None),
    ("04-cs",       "still", CARDS / "portal-cs.png",    None,  7.30,  None),
    ("05-whatif",   "clip",  TERM,                       16.20, 14.90, "cap-whatif"),
    ("06-gate",     "clip",  TERM,                       31.20, 20.30, "cap-gate"),
    ("07-run",      "clip",  GH,                         21.00, 13.60, "cap-run"),
    # GitHub's lazy load leaves a spinner in the page until about t=49 in the recording, so the
    # wide shot is taken after it clears. The crop below sits above it either way.
    ("08-diff",     "clip",  GH,                         49.60,  3.80, "cap-diff"),
    ("08b-line",    "clip",  GH,                         45.70,  7.00, "cap-diff", DIFF_CROP),
    ("09-dossier",  "still", CARDS / "dossier.png",      None, 12.00, None),
    # The event caps the video at two minutes, so the close absorbs the rounding.
    ("10-close",    "still", CARDS / "close.png",        None,  10.20, None),
]


def run(args: list[str]) -> None:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        print(" ".join(str(a) for a in args))
        print(r.stderr[-2500:])
        sys.exit(1)


def build_segment(name, kind, src, start, dur, cap, crop=None) -> Path:
    out = SEG / f"{name}.mp4"
    common = ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
              "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", str(out)]
    if kind == "still":
        # Held, not drifting. Two of these frames are documents the viewer has to read, and a
        # moving frame fights that. A slow push also made ffmpeg resample every frame, which
        # turned a six second title card into 95 MB.
        run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", f"{dur}",
             "-i", str(src), "-vf", f"scale={W}:{H},format=yuv420p",
             "-tune", "stillimage", *common])
        return out

    if cap:
        # The strip gets its own band. Overlaying it on top of the picture buried the payload:
        # on the failing-gate shot it sat directly over the two lines explaining the failure.
        pre = f"{crop}," if crop else ""
        fit = (f"{pre}scale={W}:{H - 132}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:({H}-132-ih)/2:color=0x0A1420")
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start}", "-t", f"{dur}",
             "-i", str(src), "-i", str(CARDS / f"{cap}.png"),
             "-filter_complex", f"[0:v]{fit}[b];[b][1:v]overlay=0:{H - 132}:format=auto",
             *common])
    else:
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x0A1420")
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start}", "-t", f"{dur}",
             "-i", str(src), "-vf", vf, *common])
    return out


def probe(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())


def main() -> None:
    SEG.mkdir(exist_ok=True)
    total = 0.0
    paths = []
    for entry in PLAN:
        name, kind = entry[0], entry[1]
        p = build_segment(*entry)
        d = probe(p)
        total += d
        paths.append(p)
        print(f"  {name:<12} {kind:<5} {d:6.2f}s   running {total:6.2f}s")

    listing = SEG / "list.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in paths), encoding="utf-8")
    silent = HERE / "cut-silent.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(silent)])
    print(f"\ncut-silent.mp4  {probe(silent):.2f}s")


if __name__ == "__main__":
    main()
