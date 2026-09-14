"""The CycloneDX export, validated against the published 1.6 schema rather than against my reading
of it. The schema and its two dependencies are vendored under schema/cyclonedx/ so this runs offline
and in CI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

from preflight.pipeline import analyze
from preflight.policy import Policy
from preflight.report.cyclonedx import to_cyclonedx

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schema" / "cyclonedx"
BASE = "http://cyclonedx.org/schema/"


@pytest.fixture(scope="module")
def validator() -> Draft7Validator:
    def load(name: str) -> dict:
        return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))

    registry = Registry().with_resources([
        (BASE + n, Resource.from_contents(load(n), default_specification=DRAFT7))
        for n in ("spdx.schema.json", "jsf-0.82.schema.json")
    ])
    return Draft7Validator(load("bom-1.6.schema.json"), registry=registry)


@pytest.fixture(scope="module")
def documents() -> list[dict]:
    result = analyze(ROOT / "fixtures", Policy.load(ROOT / "policy.example.yaml"))
    return [to_cyclonedx(b, version="0.1.0") for b in result.boms]


def test_every_agent_exports_a_valid_cyclonedx_document(validator, documents):
    assert len(documents) == 3
    for doc in documents:
        errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
        assert not errors, f"{doc['metadata']['component']['name']}: {[e.message for e in errors][:3]}"


def test_the_serial_number_is_the_same_composition_identity(documents):
    """A CycloneDX consumer and Preflight must be talking about the same composition."""
    for doc in documents:
        assert doc["serialNumber"].startswith("urn:uuid:")


def test_a_tool_that_calls_out_is_a_service_with_its_endpoint(documents):
    router = next(d for d in documents if d["metadata"]["component"]["name"] == "Contract router")
    svc = next(s for s in router["services"] if s["name"] == "callRecordsAgent")
    assert svc["endpoints"] and svc["endpoints"][0].startswith("https://")
    assert svc["authenticated"] is True, "it authenticates with a key, badly, but it authenticates"
    assert svc["x-trust-boundary"] is True


def test_unknown_authentication_is_not_reported_as_authenticated(documents):
    """`authenticated` is a claim. Silence is not a yes."""
    triage = next(d for d in documents if d["metadata"]["component"]["name"] == "Inbox triage")
    svc = next(s for s in triage["services"] if s["name"] == "routeEnquiry")
    assert svc["authenticated"] is False


def test_the_model_is_a_machine_learning_model_component(documents):
    records = next(d for d in documents if d["metadata"]["component"]["name"] == "records-agent")
    kinds = {c["type"] for c in records["components"]}
    assert "machine-learning-model" in kinds
