"""Re-export fixture 02 (Contract router) from its Copilot Studio environment.

Writes the unmanaged solution, unzipped, to ``fixtures/02-contract-router/solution`` and refreshes
``environment.json`` beside it. Read-only against the environment: it calls ExportSolution and
reads the bot's publish date, nothing else.

    python scripts/export_fixture02.py --subscription <sub-id>

Needs the Azure CLI signed in to the tenant that owns the environment.
"""
import argparse
import base64
import io
import json
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "02-contract-router"
ORG = "https://elliot-sandbox.crm17.dynamics.com"
ENV_ID = "668de38d-2e66-ec7d-b6e0-a1e20283c34e"
SOLUTION = "AgentPreflightFixtures"
SCHEMA = "apf_contractRouter"


def token(subscription: str) -> str:
    cmd = ["az", "account", "get-access-token", "--resource", ORG, "--query", "accessToken", "-o", "tsv"]
    if subscription:
        cmd += ["--subscription", subscription]
    return subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True).stdout.strip()


def call(tok: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"{ORG}/api/data/v9.2/{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {tok}", "Accept": "application/json",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def connection_url(env_id: str, schema: str) -> str:
    """The Agents SDK connection URL: environment id without dashes, a dot before the last two."""
    h = env_id.replace("-", "").lower()
    return (f"https://{h[:-2]}.{h[-2:]}.environment.api.powerplatform.com/copilotstudio/"
            f"dataverse-backed/authenticated/bots/{schema}/conversations?api-version=2022-03-01-preview")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subscription", default="")
    tok = token(ap.parse_args().subscription)

    blob = base64.b64decode(call(tok, "ExportSolution", {"SolutionName": SOLUTION, "Managed": False})["ExportSolutionFile"])
    out = FIXTURE / "solution"
    if out.exists():
        shutil.rmtree(out)
    zipfile.ZipFile(io.BytesIO(blob)).extractall(out)

    bot = call(tok, f"bots?$select=publishedon&$filter=schemaname eq '{SCHEMA}'".replace(" ", "%20"))["value"][0]
    env = json.loads((FIXTURE / "environment.json").read_text(encoding="utf-8"))
    env.update(environmentId=ENV_ID, published=bot.get("publishedon") is not None,
               endpoints=[connection_url(ENV_ID, SCHEMA)])
    (FIXTURE / "environment.json").write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")
    print(f"exported {SOLUTION} to {out.relative_to(ROOT)}; published={env['published']}")


if __name__ == "__main__":
    main()
