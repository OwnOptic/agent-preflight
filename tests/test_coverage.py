"""Estate coverage. The tenant's published list is injected, so this runs without a tenant."""

from __future__ import annotations

from pathlib import Path

import pytest

from preflight.coverage import tenant_coverage
from preflight.pipeline import analyze
from preflight.policy import Policy

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def boms():
    return analyze(ROOT / "fixtures", Policy.load(ROOT / "policy.example.yaml")).boms


def test_a_published_agent_this_scan_saw_counts_as_reviewed(boms):
    c = tenant_coverage(boms, published=[{"displayName": "Inbox triage", "externalId": "01-inbox-triage"}])
    assert c.available and c.reviewed == ["Inbox triage"] and c.unreviewed == []


def test_a_published_agent_this_scan_never_saw_is_the_finding(boms):
    c = tenant_coverage(boms, published=[
        {"displayName": "Inbox triage", "externalId": "01-inbox-triage"},
        {"displayName": "Expenses bot", "externalId": "9f0c"},
    ])
    assert c.unreviewed == ["Expenses bot"]
    assert "1 of 2 published agent(s)" in c.render()[0]


def test_no_coverage_information_is_not_full_coverage(boms):
    c = tenant_coverage(boms, subscription="nonexistent-subscription-id")
    if not c.available:
        assert "not checked" in c.render()[0]
        assert c.reviewed == [] and c.unreviewed == []
