"""The probe tier. No network: the fetcher is injected, which is also how anyone reviewing this can
see exactly what a probe sends."""

from __future__ import annotations

from datetime import UTC, datetime

from preflight.analyze.paths import AttackPath, Hop
from preflight.bom.models import Agent, AgentBOM, Edge, Generator, Tool, ToolSource
from preflight.resolve.probe import card_identifiers, endpoints_that_would_be_probed, probe


def _bom(aid: str, platform: str = "foundry", **kw) -> AgentBOM:
    return AgentBOM(
        generated=datetime.now(UTC),
        generator=Generator(collector="test@0.0.0"),
        agent=Agent(id=aid, platform=platform, name=aid),
        **kw,
    )


def _caller(url: str = "https://unknown.example/api/v1") -> AgentBOM:
    return _bom("caller", "m365-declarative",
                tools=[Tool(id="op:call", kind="openapi", name="call", source=ToolSource(server=url))])


def test_an_endpoint_that_names_an_estate_agent_becomes_a_probed_edge():
    caller, callee = _caller(), _bom("asst_records")
    cards = {"https://unknown.example/.well-known/agent.json": {"name": "asst_records"}}
    notes = probe([caller, callee], fetch=cards.get)

    assert len(caller.edges) == 1
    e = caller.edges[0]
    assert (e.to, e.signal, e.confidence) == ("asst_records", "probe", "probed")
    assert e.crossPlatform is True
    assert "identified itself as asst_records" in notes[0]


def test_an_endpoint_that_answers_but_is_a_stranger_creates_no_edge():
    caller, callee = _caller(), _bom("asst_records")
    cards = {"https://unknown.example/.well-known/agent.json": {"name": "someone-elses-agent"}}
    notes = probe([caller, callee], fetch=cards.get)
    assert caller.edges == []
    assert "as nothing in this estate" in notes[0]


def test_silence_is_recorded_rather_than_guessed():
    caller = _caller()
    notes = probe([caller, _bom("asst_records")], fetch=lambda _url: None)
    assert caller.edges == []
    assert "returned no agent card" in notes[0]


def test_a_stronger_signal_is_never_overwritten():
    """Endpoint matching already resolved this tool. A probe must not downgrade it."""
    caller, callee = _caller(), _bom("asst_records")
    caller.edges = [Edge(**{"from": "caller"}, to="asst_records", tool="op:call", via="openapi",
                         signal="endpoint", confidence="matched")]
    probe([caller, callee], fetch=lambda _url: {"name": "asst_records"})
    assert [e.confidence for e in caller.edges] == ["matched"]


def test_a_probed_edge_cannot_carry_a_critical_path():
    """Severity is gated on evidence, and a probe is the weakest evidence there is."""
    path = AttackPath(source_agent="caller", source_label="web content", source_rank=0,
                      hops=[Hop("caller", "caller", "m365-declarative")], sink_agent="asst_records",
                      sink_tool="delete_record", sink_tool_id="mcp:delete", sink_desc="MCP",
                      sink_confidence="high", edge_confidences=["probed"])
    assert path.severity == "high"


def test_what_would_be_contacted_can_be_listed_before_turning_it_on():
    assert endpoints_that_would_be_probed([_caller()]) == ["https://unknown.example"]


def test_a_card_identifies_itself_by_any_of_its_names():
    card = {"name": "Records", "id": "asst_1", "provider": {"organization": "Contoso"}}
    assert card_identifiers(card) == {"records", "asst_1", "contoso"}
