"""Unit tests for the pieces the end-to-end test only exercises in passing.

Each one pins a decision that would otherwise be easy to undo by accident: how cost behaves when
there is nothing to divide by, that an approval gate stops privilege flowing, that Copilot Studio's
non-standard YAML still parses, that the dossier admits what it cannot derive, and that the CLI's
exit codes mean what the README says they mean.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from preflight.analyze.cost import compute, per_turn
from preflight.analyze.privilege import closure
from preflight.bom.models import (
    Agent,
    AgentBOM,
    Classification,
    Edge,
    Generator,
    Instructions,
    Model,
    Tool,
    ToolSource,
)
from preflight.cli import main
from preflight.collectors.base import Scope
from preflight.collectors.copilot_studio import CopilotStudioCollector, _load_yaml, connection_url
from preflight.pipeline import analyze
from preflight.policy import Policy
from preflight.report.dossier import REQ, render_agent

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


def _bom(aid: str, platform: str = "foundry", **kw) -> AgentBOM:
    return AgentBOM(
        generated=datetime.now(timezone.utc),
        generator=Generator(collector="test@0.0.0"),
        agent=Agent(id=aid, platform=platform, name=aid, **kw.pop("agent", {})),
        **kw,
    )


def _irreversible(tid: str, name: str) -> Tool:
    return Tool(id=tid, kind="mcp", name=name,
                classification=Classification(untrustedInput=False, irreversibleAction=True,
                                              source="protocol", confidence="high"))


# --- cost ---------------------------------------------------------------------------------


def test_fanout_is_unknown_rather_than_a_huge_multiple_of_zero():
    b = _bom("a")
    compute([b], Policy.default())
    assert b.economics.instructionTokens == 0
    assert b.economics.fanoutFactor is None, "a ratio against a zero per-turn cost means nothing"


def test_fanout_counts_the_delegated_agent_turn():
    caller = _bom("caller", agent={"instructions": Instructions(tokens=100)})
    callee = _bom("callee", agent={"instructions": Instructions(tokens=100)})
    caller.edges = [Edge(**{"from": "caller", "to": "callee", "via": "a2a",
                           "signal": "endpoint", "confidence": "matched"})]
    compute([caller, callee], Policy.default())
    assert caller.economics.fanoutFactor == 2.0
    assert callee.economics.fanoutFactor == 1.0


def test_money_appears_only_when_the_policy_prices_the_model():
    b = _bom("a", agent={"instructions": Instructions(tokens=1_000_000)},
             models=[Model(deployment="d", model="gpt-5-mini")])
    compute([b], Policy.default())
    assert b.economics.estimatedCostPerInteraction is None
    compute([b], Policy(prices={"gpt-5-mini": 2.0}, currency="CHF"))
    cost = b.economics.estimatedCostPerInteraction
    assert cost is not None and cost.value == 2.0 and cost.currency == "CHF"


def test_per_turn_splits_the_three_drivers():
    b = _bom("a", agent={"instructions": Instructions(tokens=10)},
             tools=[Tool(id="t", kind="mcp", name="t", descriptionTokens=5)])
    assert per_turn(b) == (10, 5, 0)


# --- privilege ----------------------------------------------------------------------------


def test_privilege_flows_through_delegation():
    caller = _bom("caller")
    callee = _bom("callee", tools=[_irreversible("t:del", "delete_record")])
    caller.edges = [Edge(**{"from": "caller", "to": "callee", "via": "a2a",
                            "signal": "endpoint", "confidence": "matched"})]
    p = closure([caller, callee])["caller"]
    assert p.own == set()
    assert {n for _, _, n in p.gained} == {"delete_record"}


def test_an_approval_gate_stops_privilege_flowing():
    carrier = Tool(id="t:call", kind="a2a", name="call", approval=True,
                   source=ToolSource(server="https://callee.example"))
    caller = _bom("caller", tools=[carrier])
    callee = _bom("callee", tools=[_irreversible("t:del", "delete_record")])
    caller.edges = [Edge(**{"from": "caller", "to": "callee", "tool": "t:call", "via": "a2a",
                            "signal": "endpoint", "confidence": "matched"})]
    assert closure([caller, callee])["caller"].gained == set()


# --- the Copilot Studio collector ----------------------------------------------------------


def test_power_fx_values_do_not_break_the_yaml_parser():
    """Copilot Studio writes `=` expressions unquoted, which strict YAML rejects."""
    data = _load_yaml("kind: AdaptiveDialog\nbody:\n  content: ={ enquiry: System.Activity.Text }\n")
    assert data is not None and data["body"]["content"] == "={ enquiry: System.Activity.Text }"


def test_unreadable_yaml_is_reported_not_skipped():
    assert _load_yaml("kind: [unclosed\n") is None


def test_the_connection_url_matches_what_the_channels_page_shows():
    """Environment id without dashes, with a dot before the last two characters."""
    url = connection_url("668de38d-2e66-ec7d-b6e0-a1e20283c34e", "apf_contractRouter")
    assert url.startswith("https://668de38d2e66ec7db6e0a1e20283c3.4e.environment.api.powerplatform.com/")
    assert "/bots/apf_contractRouter/conversations" in url


@pytest.fixture(scope="module")
def contract_router() -> AgentBOM:
    c = CopilotStudioCollector()
    refs = list(c.discover(Scope(path=str(FIXTURES / "02-contract-router"))))
    assert [r.id for r in refs] == ["apf_contractRouter"]
    return c.collect(refs[0])


def test_the_export_gives_the_agent_its_auth_mode_and_its_http_call(contract_router):
    assert contract_router.agent.inboundAuth == "none"
    tool = next(t for t in contract_router.tools if t.name == "callRecordsAgent")
    assert tool.source.httpMethod == "POST"
    assert tool.auth.mode == "key" and tool.auth.secretRef == "inline"
    assert tool.approval is False


def test_every_component_in_the_export_was_read(contract_router):
    assert contract_router.tags["unparsedComponents"] == "none"


def test_the_endpoint_comes_from_environment_json_not_from_a_guess(contract_router):
    assert contract_router.agent.endpoints, "no endpoints without environment.json"
    assert contract_router.agent.environment and contract_router.residency.observed == ["switzerland"]


# --- the dossier --------------------------------------------------------------------------


def test_the_dossier_admits_what_it_cannot_derive():
    result = analyze(FIXTURES, Policy.load(ROOT / "policy.example.yaml"))
    b = next(x for x in result.boms if x.agent.platform == "copilot-studio")
    text = render_agent(b, result, version="0.1.0")
    assert "# Governance dossier: Contract router" in text
    assert "Composition hash" in text
    assert REQ in text, "owner and sponsor cannot be derived, and the dossier must say so"


# --- the CLI ------------------------------------------------------------------------------


def test_scan_exit_codes(capsys, tmp_path):
    assert main(["scan", str(FIXTURES), "--policy", str(ROOT / "policy.example.yaml"),
                 "--fail-on", "none"]) == 0
    assert main(["scan", str(FIXTURES), "--policy", str(ROOT / "policy.example.yaml"),
                 "--fail-on", "critical"]) == 1, "fixtures carry a critical finding by design"
    assert main(["scan", str(tmp_path)]) == 2, "nothing found is a usage error, not a pass"


def test_the_baseline_makes_the_same_scan_pass(capsys, tmp_path):
    out = tmp_path / "baseline.json"
    assert main(["baseline", str(FIXTURES), "--policy", str(ROOT / "policy.example.yaml"),
                 "--out", str(out)]) == 0
    assert main(["scan", str(FIXTURES), "--policy", str(ROOT / "policy.example.yaml"),
                 "--baseline", str(out), "--fail-on", "critical"]) == 0
