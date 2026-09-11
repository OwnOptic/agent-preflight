"""SARIF 2.1.0, so GitHub code scanning ingests findings natively and they land in the pull request.

Rule ids from the catalog become SARIF rule ids. ``security-severity`` drives how GitHub ranks them.
Fingerprints are stable across runs, so a finding accepted once stays accepted.
"""

from __future__ import annotations

import os
from pathlib import Path

from preflight.findings import Finding
from preflight.rules.catalog import RULES

REPO = "https://github.com/OwnOptic/agent-preflight"
LEVEL = {"critical": "error", "high": "error", "medium": "warning", "low": "note"}
SECURITY_SEVERITY = {"critical": "9.5", "high": "7.5", "medium": "5.0", "low": "2.0"}


def relative(location: str | None, base: str | Path | None = None) -> str | None:
    """Repo-relative URI with forward slashes, which is what code scanning needs to annotate a diff."""
    if not location:
        return None
    try:
        rel = os.path.relpath(location, base or os.getcwd())
    except ValueError:
        rel = location
    return rel.replace("\\", "/")


def to_sarif(findings: list[Finding], *, version: str, base: str | Path | None = None) -> dict:
    used = sorted({f.rule for f in findings})
    index = {rid: i for i, rid in enumerate(used)}
    rules = []
    for rid in used:
        r = RULES[rid]
        rules.append({
            "id": rid,
            "name": rid.replace("-", ""),
            "shortDescription": {"text": r.title},
            "fullDescription": {"text": f"{r.title}. Control: {r.control}."},
            "helpUri": f"{REPO}/blob/main/docs/capabilities.md#4-rule-catalog",
            "defaultConfiguration": {"level": LEVEL[r.severity]},
            "properties": {
                "security-severity": SECURITY_SEVERITY[r.severity],
                "tags": ["security", "agent-governance", r.control],
            },
        })

    results = []
    for f in findings:
        text = f.message + ("\n\n" + "\n".join(f.chain) if f.chain else "")
        res = {
            "ruleId": f.rule,
            "ruleIndex": index[f.rule],
            "level": LEVEL[f.severity],
            "message": {"text": text},
            "partialFingerprints": {"preflight/v1": f.fingerprint},
            "baselineState": "unchanged" if f.baselined else "new",
            "properties": {"severity": f.severity, "agent": f.agent, "agentName": f.agent_name,
                           "platform": f.platform, "control": f.control},
        }
        uri = relative(f.location, base)
        if uri:
            res["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": uri},
                                                      "region": {"startLine": 1}}}]
        results.append(res)

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "Agent Preflight", "informationUri": REPO, "version": version,
                                "rules": rules}},
            "results": results,
        }],
    }
