"""Command line entry point.

    preflight scan PATH        analyse every agent found; text report, SARIF, dossiers, exit code
    preflight collect PATH     print the AgentBOMs as JSON
    preflight pin PATH         record MCP tool manifest hashes (the lock for SC-01)
    preflight certify PATH     sign off the current composition of every agent
    preflight baseline PATH    accept today's findings so only new ones fail the build

Exit codes: 0 clean, 1 a finding at or above --fail-on that is not in the baseline, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from preflight import __version__
from preflight.bom.canonical import to_dict
from preflight.certify import certify
from preflight.findings import at_or_above
from preflight.pipeline import analyze
from preflight.policy import Policy
from preflight.report.dossier import render_agent
from preflight.report.sarif import relative, to_sarif
from preflight.report.text import render
from preflight.supply import load_lock, pin


def _common(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("path", type=Path, help="directory to scan for agent definitions")
    sp.add_argument("--policy", type=Path, help="policy file, see policy.example.yaml")
    sp.add_argument("--live-foundry", metavar="ENDPOINT", help="read Foundry agents live from this project endpoint")
    sp.add_argument("--subscription", help="Azure subscription for the live token (always pass it)")
    sp.add_argument("--region", help="region of the live Foundry project")
    sp.add_argument("--mcp-manifests", action="append", default=[], metavar="DIR",
                    help="directory of captured MCP tools/list manifests")


def _read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    p = argparse.ArgumentParser(prog="preflight", description="Design-time governance for Microsoft agents.")
    p.add_argument("--version", action="version", version=f"agent-preflight {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="analyse agents and report")
    _common(s)
    s.add_argument("--out", type=Path, help="write one AgentBOM per agent here")
    s.add_argument("--sarif", type=Path, help="write SARIF 2.1.0 here")
    s.add_argument("--dossier", type=Path, help="write one governance dossier per agent here")
    s.add_argument("--baseline", type=Path, help="accepted findings; only new ones fail")
    s.add_argument("--lock", type=Path, help="pinned MCP manifests; a change is SC-01")
    s.add_argument("--cert", type=Path, help="certification record to check against")
    s.add_argument("--fail-on", default="critical", choices=["critical", "high", "medium", "low", "none"])
    s.add_argument("--json", action="store_true", help="print findings as JSON instead of the report")

    for name, helptext in [("collect", "print AgentBOMs as JSON"), ("pin", "pin MCP tool manifests"),
                           ("certify", "certify the current composition"),
                           ("baseline", "accept current findings")]:
        sp = sub.add_parser(name, help=helptext)
        _common(sp)
        if name != "collect":
            sp.add_argument("--out", type=Path, required=True)
        if name == "certify":
            sp.add_argument("--by", default="unknown", help="who signs off")

    args = p.parse_args(argv)
    policy = Policy.load(args.policy) if args.policy else Policy.default()
    kwargs = dict(live_foundry=args.live_foundry, subscription=args.subscription, region=args.region,
                  mcp_manifests=args.mcp_manifests)

    if args.cmd == "scan":
        lock = load_lock(args.lock) if args.lock and args.lock.exists() else None
        cert = _read_json(args.cert) if args.cert and args.cert.exists() else None
        base = set(_read_json(args.baseline).get("fingerprints", [])) if args.baseline and args.baseline.exists() else None
        result = analyze(args.path, policy, lock=lock, certification=cert, baseline=base, **kwargs)
        if not result.boms:
            print("no agents found", file=sys.stderr)
            return 2
        for f in result.findings:
            f.location = relative(f.location)

        if args.out:
            for b in result.boms:
                _write(args.out / f"{b.agent.platform}--{b.agent.id}.json",
                       json.dumps(to_dict(b), indent=2, sort_keys=True, ensure_ascii=False))
        if args.sarif:
            _write(args.sarif, json.dumps(to_sarif(result.findings, version=__version__), indent=2))
        if args.dossier:
            for b in result.boms:
                _write(args.dossier / f"{b.agent.platform}--{b.agent.id}.md",
                       render_agent(b, result, version=__version__))

        if args.json:
            print(json.dumps([f.to_dict() for f in result.findings], indent=2))
        else:
            print(render(result, version=__version__))

        failing = [f for f in result.findings if not f.baselined and at_or_above(f.severity, args.fail_on)]
        return 1 if failing else 0

    result = analyze(args.path, policy, **kwargs)
    if args.cmd == "collect":
        print(json.dumps([to_dict(b) for b in result.boms], indent=2, sort_keys=True, ensure_ascii=False))
    elif args.cmd == "pin":
        _write(args.out, json.dumps(pin(result.boms), indent=2))
        print(f"pinned {len(pin(result.boms)['servers'])} MCP server manifest(s) -> {args.out}")
    elif args.cmd == "certify":
        _write(args.out, json.dumps(certify(result.boms, args.by), indent=2))
        print(f"certified {len(result.boms)} agent(s) -> {args.out}")
    elif args.cmd == "baseline":
        fps = sorted({f.fingerprint for f in result.findings})
        _write(args.out, json.dumps({"version": 1, "fingerprints": fps}, indent=2))
        print(f"accepted {len(fps)} finding(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
