"""End to end over the three fixtures. The assertions here are fixtures/CHAIN.md, executable.

If these fail, the analyzer is wrong, not the fixtures.
"""

import copy
import json
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from preflight.analyze.paths import find_paths, group
from preflight.bom.canonical import to_dict
from preflight.certify import certify, status
from preflight.pipeline import analyze
from preflight.policy import Policy
from preflight.report.sarif import to_sarif
from preflight.supply import pin

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
SCHEMA = json.loads((ROOT / "schema" / "agentbom-0.1.json").read_text(encoding="utf-8"))

A1 = "01-inbox-triage"
A2 = "apf_contractRouter"
A3 = "asst_Y3XUjyknLU4ZzR732qhPDe7F"


@pytest.fixture(scope="module")
def result():
    return analyze(FIXTURES, Policy.load(ROOT / "policy.example.yaml"))


def test_three_agents_on_three_platforms(result):
    assert {b.agent.id for b in result.boms} == {A1, A2, A3}
    assert {b.agent.platform for b in result.boms} == {"m365-declarative", "copilot-studio", "foundry"}


def test_every_bom_validates_against_the_schema(result):
    v = Draft202012Validator(SCHEMA)
    for b in result.boms:
        v.validate(to_dict(b))


def test_both_cross_platform_edges_resolve_by_endpoint_match(result):
    edges = {(e.from_, e.to, e.signal, e.confidence, e.crossPlatform) for b in result.boms for e in b.edges}
    assert edges == {
        (A1, A2, "endpoint", "matched", True),
        (A2, A3, "endpoint", "matched", True),
    }


def test_exactly_one_critical_path_and_it_is_the_chain(result):
    critical = [g for g in result.groups if g.best.severity == "critical"]
    assert len(critical) == 1
    p = critical[0].best
    assert p.sink_tool == "delete_record"
    assert [h.agent_id for h in p.hops] == [A1, A2, A3]
    assert p.cross_platform and len(set(p.platforms)) == 3
    assert "WebSearch" in p.source_label
    assert set(p.edge_confidences) == {"matched"}


def test_assumed_sinks_are_possible_paths_not_critical(result):
    sev = {g.best.sink_tool: g.best.severity for g in result.groups}
    assert sev["get_record"] == "high"
    assert sev["search_records"] == "high"


def test_findings_match_chain_md(result):
    got = Counter((f.rule, f.agent) for f in result.findings)
    assert got == Counter({
        ("AP-02", A3): 3, ("CO-03", A3): 1, ("ID-03", A3): 1, ("RA-01", A3): 1,
        ("RA-03", A3): 1, ("SC-05", A3): 1, ("TS-01", A3): 1,
        ("ID-01", A2): 1, ("ID-03", A2): 1, ("ID-08", A2): 1, ("MA-08", A2): 1,
        ("ID-01", A1): 1, ("ID-08", A1): 1, ("RA-07", A1): 1, ("TS-06", A1): 2,
    })


def test_findings_are_deterministic():
    a = analyze(FIXTURES, Policy.load(ROOT / "policy.example.yaml"))
    b = analyze(FIXTURES, Policy.load(ROOT / "policy.example.yaml"))
    assert [f.fingerprint for f in a.findings] == [f.fingerprint for f in b.findings]
    assert [x.serialNumber for x in a.boms] == [x.serialNumber for x in b.boms]


def test_a_human_gate_on_the_middle_hop_breaks_the_path(result):
    boms = copy.deepcopy(result.boms)
    for b in boms:
        if b.agent.id == A2:
            for t in b.tools:
                t.approval = True
    crossing = [g for g in group(find_paths(boms)) if g.best.cross_platform and g.best.source_agent == A1]
    assert crossing == []


def test_trusting_the_mcp_server_changes_what_is_a_sink():
    policy = Policy.load(ROOT / "policy.example.yaml")
    policy.trusted_mcp_servers = {"https://mcp.records.contoso-internal.example/mcp"}
    r = analyze(FIXTURES, policy)
    sinks = {g.best.sink_tool for g in r.groups}
    assert sinks == {"delete_record"}


def test_certification_voids_when_composition_changes(result):
    record = certify(result.boms, by="test")
    assert set(status(result.boms, record).values()) == {"valid"}
    boms = copy.deepcopy(result.boms)
    boms[0].tools[0].name = "changed"
    assert "void" in status(boms, record).values()


def test_lock_detects_a_rewritten_manifest(result):
    lock = pin(result.boms)["servers"]
    assert lock
    tampered = {s: "sha256:" + "0" * 64 for s in lock}
    r = analyze(FIXTURES, Policy.load(ROOT / "policy.example.yaml"), lock=tampered)
    assert any(f.rule == "SC-01" for f in r.findings)


def test_sarif_is_well_formed(result):
    s = to_sarif(result.findings, version="test", base=ROOT)
    assert s["version"] == "2.1.0"
    run = s["runs"][0]
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    for res in run["results"]:
        assert res["ruleId"] in rule_ids
        assert res["level"] in ("error", "warning", "note")
        assert not res["locations"][0]["physicalLocation"]["artifactLocation"]["uri"].startswith("/")
    critical = [r for r in run["results"] if r["properties"]["severity"] == "critical" and r["ruleId"] == "AP-02"]
    assert len(critical) == 1 and "delete_record" in critical[0]["message"]["text"]


def test_code_scanning_sees_the_severity_the_evidence_gate_assigned(result):
    """GitHub reads security-severity per rule, not per result. A possible path must not show as
    critical there, or the evidence gate vanishes in the place a reviewer actually looks."""
    s = to_sarif(result.findings, version="test", base=ROOT)
    run = s["runs"][0]
    rules = {r["id"]: r for r in run["tool"]["driver"]["rules"]}
    assert rules["AP-02"]["properties"]["security-severity"] == "9.5"
    assert rules["AP-02/high"]["properties"]["security-severity"] == "7.5"
    assert rules["AP-02/high"]["properties"]["catalogRule"] == "AP-02"
    possible = [r for r in run["results"] if r["ruleId"] == "AP-02/high"]
    assert len(possible) == 2
    assert {r["properties"]["catalogRule"] for r in run["results"]} >= {"AP-02"}
