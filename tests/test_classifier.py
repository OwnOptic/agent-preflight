"""The classifier is the part a reviewer will push on, so it is the part with tests."""

from preflight.bom.models import Annotations, Tool, ToolSource
from preflight.classify import classify
from preflight.policy import Policy, ToolOverride

SERVER = "https://mcp.example.com"


def mcp(name="t", server=SERVER, **ann):
    return Tool(
        id="mcp:" + name,
        kind="mcp",
        name=name,
        source=ToolSource(server=server),
        annotations=Annotations(**ann) if ann else None,
    )


def test_unannotated_tool_fails_closed():
    c = classify(mcp(), Policy.default())
    assert (c.untrustedInput, c.irreversibleAction) == (True, True)
    assert c.source == "failclosed"


def test_annotations_from_untrusted_server_cannot_improve_a_classification():
    """MCP spec: annotations MUST NOT be relied on unless the server is trusted."""
    c = classify(mcp(readOnlyHint=True, openWorldHint=False), Policy.default())
    assert (c.untrustedInput, c.irreversibleAction) == (True, True)
    assert c.source == "failclosed"


def test_untrusted_server_declaring_its_own_tool_destructive_is_believed():
    """A worsening annotation is accepted from any server: nobody overstates their own danger."""
    c = classify(mcp(readOnlyHint=False, destructiveHint=True), Policy.default())
    assert (c.untrustedInput, c.irreversibleAction) == (True, True)
    assert c.source == "protocol"
    assert c.confidence == "high"


def test_annotations_from_trusted_server_are_authoritative():
    policy = Policy(trusted_mcp_servers={SERVER})
    c = classify(mcp(readOnlyHint=True, openWorldHint=False), policy)
    assert (c.untrustedInput, c.irreversibleAction) == (False, False)
    assert c.source == "protocol"


def test_destructive_hint_is_irreversible():
    policy = Policy(trusted_mcp_servers={SERVER})
    assert classify(mcp(readOnlyHint=False, destructiveHint=True), policy).irreversibleAction


def test_open_world_is_untrusted_input():
    policy = Policy(trusted_mcp_servers={SERVER})
    assert classify(mcp(readOnlyHint=True, openWorldHint=True), policy).untrustedInput


def test_policy_override_wins():
    policy = Policy(tool_overrides={"mcp:t": ToolOverride(False, False)})
    c = classify(mcp(destructiveHint=True), policy)
    assert c.source == "policy"
    assert c.irreversibleAction is False


def test_http_delete_is_irreversible():
    tool = Tool(id="op:x", kind="openapi", name="x", source=ToolSource(httpMethod="DELETE"))
    c = classify(tool, Policy.default())
    assert c.irreversibleAction is True
    assert c.source == "protocol"


def test_http_get_is_read_but_still_untrusted_input():
    tool = Tool(id="op:y", kind="openapi", name="y", source=ToolSource(httpMethod="GET"))
    c = classify(tool, Policy.default())
    assert c.irreversibleAction is False
    assert c.untrustedInput is True


def test_first_party_registry():
    tool = Tool(id="b:bing", kind="builtin", name="bing",
                source=ToolSource(builtinId="bing_grounding"))
    c = classify(tool, Policy.default())
    assert c.source == "registry"
    assert c.untrustedInput is True
