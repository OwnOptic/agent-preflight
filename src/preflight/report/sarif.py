"""SARIF 2.1.0, so GitHub code scanning ingests findings natively and they land in the pull request.

Rule ids from the catalog become SARIF rule ids. Fingerprints are stable across runs, so a finding
accepted once stays accepted.

One subtlety. GitHub reads ``security-severity`` from the rule descriptor, never from the result. A
finding the evidence gate downgraded (a possible path, reported High rather than Critical) would
therefore show in code scanning at its rule's default severity, and the gate would vanish in the one
place a reviewer looks. So a finding whose severity differs from its rule's default is emitted under
its own descriptor, ``<rule>/<severity>``, carrying the severity Preflight actually assigned.
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


def sarif_rule_id(f: Finding) -> str:
    return f.rule if f.severity == RULES[f.rule].severity else f"{f.rule}/{f.severity}"


def to_sarif(findings: list[Finding], *, version: str, base: str | Path | None = None) -> dict:
    ids = sorted({sarif_rule_id(f) for f in findings})
    index = {rid: i for i, rid in enumerate(ids)}

    rules = []
    for rid in ids:
        catalog_id, _, downgraded = rid.partition("/")
        r = RULES[catalog_id]
        sev = downgraded or r.severity
        title = r.title if not downgraded else f"{r.title} (reported {sev}: evidence below the {r.severity} bar)"
        rules.append({
            "id": rid,
            "name": rid.replace("-", "").replace("/", "_"),
            "shortDescription": {"text": title},
            "fullDescription": {"text": f"{title}. Control: {r.control}."},
            "helpUri": f"{REPO}/blob/main/docs/capabilities.md#4-rule-catalog",
            "defaultConfiguration": {"level": LEVEL[sev]},
            "properties": {
                "security-severity": SECURITY_SEVERITY[sev],
                "catalogRule": catalog_id,
                "tags": ["security", "agent-governance", r.control],
            },
        })

    results = []
    for f in findings:
        rid = sarif_rule_id(f)
        text = f.message + ("\n\n" + "\n".join(f.chain) if f.chain else "")
        res = {
            "ruleId": rid,
            "ruleIndex": index[rid],
            "level": LEVEL[f.severity],
            "message": {"text": text},
            "partialFingerprints": {"preflight/v1": f.fingerprint},
            "baselineState": "unchanged" if f.baselined else "new",
            "properties": {"severity": f.severity, "catalogRule": f.rule, "agent": f.agent,
                           "agentName": f.agent_name, "platform": f.platform, "control": f.control},
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
