"""The whole analysis, in the only order that is correct.

    collect -> classify -> resolve edges -> cost -> stamp -> paths -> privilege -> rules

Classification and edges are part of an agent's composition, so the document identity is stamped
after both. Paths and privilege need the resolved edges. Rules read everything.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from preflight.analyze.cost import compute as compute_cost
from preflight.analyze.paths import AttackPath, PathGroup, find_paths, group
from preflight.analyze.privilege import Privilege, closure
from preflight.bom.canonical import stamp
from preflight.bom.models import AgentBOM
from preflight.certify import status as cert_status
from preflight.classify import classify
from preflight.collectors.agent365 import Agent365Collector
from preflight.collectors.agent_framework import AgentFrameworkCollector
from preflight.collectors.base import Scope
from preflight.collectors.copilot_studio import CopilotStudioCollector, CopilotStudioLiveCollector
from preflight.collectors.foundry import FoundryCollector, FoundryLiveCollector
from preflight.collectors.m365_declarative import M365DeclarativeCollector
from preflight.coverage import Coverage, tenant_coverage
from preflight.findings import Finding
from preflight.policy import Policy
from preflight.resolve.edges import resolve
from preflight.resolve.probe import probe as run_probe
from preflight.rules.catalog import Context, evaluate


@dataclass
class Result:
    boms: list[AgentBOM]
    paths: list[AttackPath]
    groups: list[PathGroup]
    privilege: dict[str, Privilege]
    findings: list[Finding]
    policy: Policy
    skipped: list[tuple[str, str]] = field(default_factory=list)
    certification: dict[str, str] = field(default_factory=dict)
    #: One line per endpoint the probe tier contacted. Empty unless --probe was passed, and the
    #: report prints it, because a result that needed a network call must say so.
    probes: list[str] = field(default_factory=list)
    #: What the tenant has published versus what this scan saw. None unless asked for.
    coverage: Coverage | None = None


def collectors_for(*, live_foundry: str | None = None, subscription: str | None = None,
                   region: str | None = None, mcp_manifests: list | None = None,
                   live_copilot_studio: str | None = None, cs_environment_id: str | None = None,
                   agent365: bool = False) -> list:
    out = [M365DeclarativeCollector(), AgentFrameworkCollector()]
    if agent365:
        out.append(Agent365Collector(subscription=subscription))
    out.append(
        CopilotStudioLiveCollector(live_copilot_studio, subscription=subscription, region=region,
                                   environment_id=cs_environment_id)
        if live_copilot_studio else CopilotStudioCollector()
    )
    if live_foundry:
        out.append(FoundryLiveCollector(live_foundry, subscription=subscription, region=region,
                                        manifest_dirs=mcp_manifests))
    else:
        out.append(FoundryCollector(manifest_dirs=mcp_manifests))
    return out


def analyze(path: str | Path, policy: Policy | None = None, *, live_foundry: str | None = None,
            subscription: str | None = None, region: str | None = None,
            mcp_manifests: list | None = None, live_copilot_studio: str | None = None,
            cs_environment_id: str | None = None, agent365: bool = False, probe: bool = False,
            coverage: bool = False,
            lock: dict[str, str] | None = None,
            certification: dict | None = None, baseline: set[str] | None = None,
            hook: Callable[[list[AgentBOM]], None] | None = None) -> Result:
    policy = policy or Policy.default()
    boms: list[AgentBOM] = []
    skipped: list[tuple[str, str]] = []

    scope = Scope(path=str(path), project=live_foundry)
    for c in collectors_for(live_foundry=live_foundry, subscription=subscription, region=region,
                            mcp_manifests=mcp_manifests, live_copilot_studio=live_copilot_studio,
                            cs_environment_id=cs_environment_id, agent365=agent365):
        ok, why = c.available()
        if not ok:
            skipped.append((c.platform, why))
            continue
        for ref in c.discover(scope):
            boms.append(c.collect(ref))
    boms.sort(key=lambda b: (b.agent.platform, b.agent.id))
    # The only place anything may alter a collected composition, and only in memory: `preflight
    # whatif` uses it to ask what a change would do. Nothing is written back to any platform.
    if hook is not None:
        hook(boms)

    for b in boms:
        for t in b.tools:
            t.classification = classify(t, policy)
    resolve(boms)
    probes = run_probe(boms) if probe else []
    compute_cost(boms, policy)
    for b in boms:
        stamp(b)

    paths = find_paths(boms)
    groups = group(paths)
    privilege = closure(boms)
    findings = evaluate(Context(boms=boms, groups=groups, privilege=privilege, policy=policy, lock=lock,
                                cert=certification))
    if baseline:
        for f in findings:
            f.baselined = f.fingerprint in baseline

    return Result(
        boms=boms, paths=paths, groups=groups, privilege=privilege, findings=findings, policy=policy,
        skipped=skipped, certification=cert_status(boms, certification) if certification else {},
        probes=probes,
        coverage=tenant_coverage(boms, subscription=subscription) if coverage else None,
    )
