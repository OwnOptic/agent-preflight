"""End to end over fixture 01: files on disk in, schema-valid BOM out.

This is also the drift guard. The JSON Schema is the contract and the pydantic models are the
convenient view of it; if they diverge, this fails.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from preflight.bom.canonical import composition_hash, stamp, to_dict
from preflight.classify import classify
from preflight.collectors.base import Scope
from preflight.collectors.m365_declarative import M365DeclarativeCollector
from preflight.policy import Policy

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "01-inbox-triage"
SCHEMA = json.loads((ROOT / "schema" / "agentbom-0.1.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bom():
    c = M365DeclarativeCollector()
    refs = list(c.discover(Scope(path=str(FIXTURE))))
    assert len(refs) == 1
    b = c.collect(refs[0])
    for t in b.tools:
        t.classification = classify(t, Policy.default())
    return stamp(b)


def test_bom_validates_against_the_schema(bom):
    Draft202012Validator(SCHEMA).validate(to_dict(bom))


def test_capabilities_and_the_action_are_both_collected(bom):
    names = {t.name for t in bom.tools}
    assert {"WebSearch", "OneDriveAndSharePoint", "GraphConnectors", "routeEnquiry"} <= names


def test_websearch_is_untrusted_input_from_the_registry(bom):
    t = next(t for t in bom.tools if t.name == "WebSearch")
    assert t.classification.untrustedInput is True
    assert t.classification.source == "registry"


def test_post_operation_is_irreversible_from_protocol(bom):
    t = next(t for t in bom.tools if t.name == "routeEnquiry")
    assert t.source.httpMethod == "POST"
    assert t.classification.irreversibleAction is True
    assert t.classification.source == "protocol"


def test_outbound_url_is_captured_whole(bom):
    """resolve/ matches this string against the estate, so it must survive intact."""
    t = next(t for t in bom.tools if t.name == "routeEnquiry")
    assert t.source.server.endswith("/bots/cr_contractRouter/conversations")
    assert t.source.server.startswith("https://")


def test_absent_disclaimer_is_none_not_empty(bom):
    """None means absent and therefore a finding. Empty string would hide RA-07."""
    assert bom.tags["disclaimer"] is None


def test_composition_hash_is_stable_across_runs(bom):
    c = M365DeclarativeCollector()
    ref = list(c.discover(Scope(path=str(FIXTURE))))[0]
    again = c.collect(ref)
    for t in again.tools:
        t.classification = classify(t, Policy.default())
    assert composition_hash(bom) == composition_hash(again)
    assert stamp(again).serialNumber == bom.serialNumber
    assert bom.serialNumber.startswith("urn:uuid:")
