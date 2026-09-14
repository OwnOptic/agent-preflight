"""Narration for the real-screens cut.

One clip per segment, padded with silence to that segment's measured length, so the voice lands on
the screen it is describing without any manual nudging. A clip that overruns its slot is reported
rather than quietly pushing everything after it out of sync.

Slot lengths come from assemble.py, which measured them from the recordings.
"""
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from azure_tts import key, say  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "audio2"
VOICE = "en-GB-OllieMultilingualNeural"

# (segment, slot seconds, line)
SCENES = [
    ("01-title", 6.6,
     "Three agents, on three platforms. Each reviewed and approved on its own."),
    ("02-scan", 16.1,
     "Preflight reads their definitions. Nothing is deployed, no tokens are spent, no traffic "
     "leaves the machine. In two seconds it finds one critical path that crosses all three, and "
     "no single platform owns it."),
    ("03-m365", 7.8,
     "Microsoft 365 Copilot shows Inbox triage. Everything it can see is fine."),
    ("04-cs", 7.3,
     "Copilot Studio shows Contract router, published and answering. Fine, on its own terms."),
    ("05-whatif", 14.9,
     "So the reviewer asks what one approval gate would change. Preflight answers in memory, "
     "before anyone builds it. One critical is fixed, and a different one appears. The gate moves "
     "the problem."),
    ("06-gate", 20.3,
     "Now the same scan inside a build. On this branch an approved server quietly rewrote one tool "
     "description. Nothing else changed: same tools, same model, same allow list. The scan exits "
     "one. Two independent rules fired, and neither needed the agent to run."),
    ("07-run", 13.6,
     "That is the real workflow run, on a public repository. Failure, twenty eight seconds, no "
     "model in the loop. The engineer shipping the agent finds out here, and so does the reviewer "
     "approving it."),
    ("08-diff", 10.8,
     "And this is the line: a tool description that now tells the model to delete records and hide "
     "it from the user. Prose, in a routine diff."),
    ("09-dossier", 12.0,
     "Every run writes the dossier a reviewer signs, with the trust graph drawn from the bill of "
     "materials. Change the composition, and the certification voids."),
    ("10-close", 10.2,
     "It runs before the agent exists. Deterministic, standards based, and its "
     "output is what Agent 365 needs at registration."),
]


def duration(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    k = key()
    parts, overruns = [], []
    for name, slot, line in SCENES:
        wav = OUT / f"{name}.wav"
        d = say(line, VOICE, wav, k=k)
        pad = slot - d
        if pad < 0:
            overruns.append((name, -pad))
        print(f"  {name:<12} {d:5.1f}s speech  {slot:5.1f}s slot  {max(pad, 0):4.1f}s silence"
              + ("   OVERRUN" if pad < 0 else ""))
        parts.append((wav, max(pad, 0.0)))

    listing = OUT / "list.txt"
    with open(listing, "w", encoding="utf-8") as f:
        for wav, pad in parts:
            f.write(f"file '{wav.as_posix()}'\n")
            if pad > 0.05:
                sil = OUT / f"sil_{wav.stem}.wav"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                                f"anullsrc=r=24000:cl=mono:d={pad:.2f}", str(sil)], check=True)
                f.write(f"file '{sil.as_posix()}'\n")

    out = HERE / "narration2.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-ar", "44100", "-ac", "1", str(out)], check=True)
    print(f"\nnarration2.wav {duration(out):.1f}s, {len(overruns)} overrun(s)")
    for name, by in overruns:
        print(f"  {name} runs {by:.1f}s past its slot")


if __name__ == "__main__":
    main()
