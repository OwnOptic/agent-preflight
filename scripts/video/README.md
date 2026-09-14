# Demo video pipeline

Builds `dist/agent-preflight-demo.mp4`: two minutes, 1920x1080, narrated.

Seven of the ten segments are live screen recordings. The other three present artefacts the tool
itself wrote. Nothing in the cut is a mock-up of what the tool would do.

| Segment | What it is |
|---|---|
| Title, close | Designed cards |
| Scan, whatif, gate | A real console on this machine, captured with ffmpeg window capture |
| Workflow run, diff | github.com read signed out, recorded with Playwright |
| Platform views | Real captures of the demo tenant's own portals |
| Dossier | The SVG `preflight scan --dossier` writes, not a redrawing |

## Order

```
python  cards.py          # writes cards/*.html, including the caption strips
node    shoot-cards.mjs   # screenshots them to cards/*.png
.\record-term.ps1         # runs demo-term.ps1 for real and captures the window -> term.mp4
node    record-gh.mjs     # records the pull request, workflow run and diff -> raw-gh/*.webm
python  assemble.py       # cuts to the beat sheet, adds caption strips -> cut-silent.mp4
python  narrate.py        # Azure neural narration, one clip per slot -> narration2.wav
```

Then mux:

```bash
ffmpeg -y -i cut-silent.mp4 -i narration2.wav -filter_complex "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,apad[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart ../../dist/agent-preflight-demo.mp4
```

## Traps, all paid for once

- **Window capture needs conhost.** `ffmpeg -f gdigrab -i title=PREFLIGHT-DEMO` cannot find the
  window under Windows Terminal, which owns the title bar. `record-term.ps1` launches through
  `conhost` so the title applies.
- **Hold the window open.** The first capture truncated at 31s because the script ended and closed
  its console, and gdigrab died with "Couldn't get window rectangle". `demo-term.ps1` sleeps at the
  end.
- **Watch the console's scrollback.** Piping 26 lines of scan output scrolled the CRITICAL block off
  the top, which is the one thing the demo exists to show. 17 lines fit.
- **git writes to stderr.** `git switch` piped with `2>&1` renders as a red PowerShell ErrorRecord,
  which on video reads as a crash. Print `$_.ToString()` instead.
- **Signed-out GitHub hides things.** The merge box and the check log will not render for a visitor,
  so the failing check is recorded from the public Actions run page instead of the Checks tab.
  `record-gh.mjs` asserts on real content before the camera holds, because one attempt got a 504 and
  held five seconds on a gateway error.
- **No zoompan on the stills.** A slow push made ffmpeg resample every frame and turned a six second
  title card into 95 MB. The stills are held, which also suits frames the viewer has to read.
- **Give the caption strip its own band.** Overlaid on the picture it sat directly over the two
  lines explaining the build failure.

## Narration

`azure_tts.py` reads the Speech key from the Azure CLI at call time. It is never written to disk and
never printed. Voice is `en-GB-OllieMultilingualNeural` with `narration-professional`.

`narrate.py` pads each line with silence to its segment's measured length and reports any line that
overruns its slot, because an overrun silently pushes everything after it out of sync. Slot lengths
come from `assemble.py`, which measures them rather than assuming the planned values.

## Also here

`gallery.py` and `shoot-gallery.mjs` build the still images in `docs/media/`, from the same
recordings the video uses.

`logo.py` and `shoot-logo.mjs` build the identity in `docs/brand/`. The SVG is the source; every PNG
beside it is rendered from that SVG.

`render-dossier.py` and `shoot-dossier.mjs` render a governance dossier as the document it is, so
the output in `docs/example-output/dossier/` can be looked at rather than read as markdown. Only the
subset of markdown the dossier actually emits is handled, and an unrecognised asset reference prints
as a visible "missing asset" rather than disappearing.
