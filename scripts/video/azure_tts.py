"""Neural narration from the Azure AI Services resource in switzerlandnorth.

The key is read from the Azure CLI at call time and never written to disk or printed. Output is
24 kHz mono PCM, which ffmpeg mixes straight into the video.
"""
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGION = "switzerlandnorth"
ENDPOINT = f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
ACCOUNT = ["--name", "fdy-demo-agents-de-em", "--resource-group", "rg-demo-agents-de",
           "--subscription", "9049e88f-118a-4bd0-ac6b-d8fb1201262e"]


def key() -> str:
    r = subprocess.run(["az", "cognitiveservices", "account", "keys", "list", *ACCOUNT,
                        "--query", "key1", "-o", "tsv"],
                       capture_output=True, text=True, shell=True, check=True)
    return r.stdout.strip()


def say(text: str, voice: str, out: Path, *, rate: str = "+4%", k: str | None = None) -> float:
    ssml = (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-GB">'
        f'<voice name="{voice}"><mstts:express-as style="narration-professional">'
        f'<prosody rate="{rate}">{text}</prosody></mstts:express-as></voice></speak>'
    )
    req = urllib.request.Request(
        ENDPOINT, data=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": k or key(),
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
            "User-Agent": "agent-preflight-demo",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        out.write_bytes(resp.read())
    with wave.open(str(out)) as w:
        return w.getnframes() / w.getframerate()


if __name__ == "__main__":
    # Sample mode: one line per candidate voice, concatenated for a single listen.
    voices = ["en-GB-AdaMultilingualNeural", "en-GB-RyanNeural", "en-GB-SoniaNeural",
              "en-GB-OllieMultilingualNeural"]
    k = key()
    out = HERE / "voicetest"
    out.mkdir(exist_ok=True)
    listing = out / "list.txt"
    with open(listing, "w", encoding="utf-8") as f:
        for v in voices:
            name = v.replace("en-GB-", "").replace("MultilingualNeural", "").replace("Neural", "")
            w = out / f"{name}.wav"
            d = say(f"This is {name}. Preflight reads the definitions instead. No traffic, no tokens, "
                    f"nothing registered yet. In two seconds it finds the path none of them can see.",
                    v, w, k=k)
            print(f"  {name:<8} {d:4.1f}s  {v}")
            f.write(f"file '{w.as_posix()}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-ar", "44100", str(HERE / "voice-samples.mp3")], check=True)
    print("wrote voice-samples.mp3")
