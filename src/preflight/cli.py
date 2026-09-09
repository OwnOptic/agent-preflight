"""Command line entry point.

``preflight collect <path>``  one agent, one BOM, on stdout
``preflight scan <path>``     every agent found, one BOM per file in --out
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from preflight.bom.canonical import canonical_json, stamp
from preflight.classify import classify
from preflight.collectors.base import Scope
from preflight.collectors.m365_declarative import M365DeclarativeCollector
from preflight.policy import Policy

COLLECTORS = [M365DeclarativeCollector()]


def _classified(bom, policy: Policy):
    """Classification runs over the BOM, never inside a collector."""
    for tool in bom.tools:
        tool.classification = classify(tool, policy)
    return stamp(bom)


def _collect_all(path: Path, policy: Policy):
    scope = Scope(path=str(path))
    for collector in COLLECTORS:
        ok, why = collector.available()
        if not ok:
            print(f"skipped {collector.platform}: {why}", file=sys.stderr)
            continue
        for ref in collector.discover(scope):
            yield _classified(collector.collect(ref), policy)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="preflight")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="Resolve agents under a path into BOMs on stdout.")
    c.add_argument("path", type=Path)
    c.add_argument("--policy", type=Path, default=None)

    s = sub.add_parser("scan", help="Resolve agents under a path, one BOM per file.")
    s.add_argument("path", type=Path)
    s.add_argument("--out", type=Path, default=Path("out"))
    s.add_argument("--policy", type=Path, default=None)

    args = p.parse_args(argv)
    policy = Policy.default()

    boms = list(_collect_all(args.path, policy))
    if not boms:
        print("no agents found", file=sys.stderr)
        return 1

    if args.cmd == "collect":
        for bom in boms:
            print(canonical_json(bom))
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    for bom in boms:
        f = args.out / f"{bom.agent.platform}--{bom.agent.id}.json"
        f.write_text(canonical_json(bom), encoding="utf-8")
        crit = sum(
            1
            for t in bom.tools
            if t.classification and t.classification.untrustedInput and t.classification.irreversibleAction
        )
        print(f"{bom.agent.platform:18} {bom.agent.id:22} {len(bom.tools):3} tools  {crit} both-ways  -> {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
