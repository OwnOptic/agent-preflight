"""The trust graph and the what-if, over the fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from preflight.pipeline import analyze
from preflight.policy import Policy
from preflight.report.trustgraph import to_svg
from preflight.whatif import Change, what_if

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


@pytest.fixture(scope="module")
def result():
    return analyze(FIXTURES, Policy.load(ROOT / "policy.example.yaml"))


# --- the trust graph ----------------------------------------------------------------------


def test_the_graph_is_byte_identical_across_runs(result):
    assert to_svg(result.boms, focus="01-inbox-triage") == to_svg(result.boms, focus="01-inbox-triage")


def test_the_graph_draws_the_chain_and_its_evidence(result):
    svg = to_svg(result.boms, focus="01-inbox-triage")
    for name in ("Inbox triage", "Contract router", "records-agent"):
        assert name in svg
    assert "matched" in svg and "auth key" in svg
    assert "irreversible: delete_record" in svg


def test_a_weaker_edge_is_drawn_differently(result):
    """A probed edge must not look like a matched one."""
    boms = analyze(FIXTURES, Policy.load(ROOT / "policy.example.yaml")).boms
    for b in boms:
        for e in b.edges:
            e.confidence = "probed"
    assert "stroke-dasharray" in to_svg(boms)
    assert "stroke-dasharray" not in to_svg(result.boms)


# --- what if -----------------------------------------------------------------------------


def test_a_human_gate_on_the_middle_hop_breaks_the_cross_platform_path():
    w = what_if(FIXTURES, Policy.load(ROOT / "policy.example.yaml"), Change(approve={"callRecordsAgent"}))
    assert any(f.rule == "AP-02" and f.severity == "critical" for f in w.fixed)


def test_the_gate_moves_the_problem_rather_than_removing_it():
    """The honest half of the answer: the sink is still reachable from inside the last agent."""
    w = what_if(FIXTURES, Policy.load(ROOT / "policy.example.yaml"), Change(approve={"callRecordsAgent"}))
    assert any(f.rule == "AP-01" and f.severity == "critical" for f in w.introduced)


def test_trusting_the_server_removes_the_assumed_sinks():
    w = what_if(FIXTURES, Policy.load(ROOT / "policy.example.yaml"),
                Change(trust_servers={"mcp.records.contoso-internal.example"}))
    fixed = {f.rule for f in w.fixed}
    assert "SC-05" in fixed and "SC-06" in fixed


def test_changing_nothing_changes_nothing():
    w = what_if(FIXTURES, Policy.load(ROOT / "policy.example.yaml"), Change())
    assert w.fixed == [] and w.introduced == []
    assert "Nothing changed" in w.render()
