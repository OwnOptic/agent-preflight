"""Foundry Agent Service collector.

Reads: prompt agents, hosted agents, toolboxes, connections, connected agents and A2A endpoints, content filters

Access: azure-ai-projects plus ARM. Requires a Foundry *project*: an AIServices account with model deployments is not Agent Service.
"""

from __future__ import annotations

from typing import Iterable

from preflight.bom.models import AgentBOM
from preflight.collectors.base import AgentRef, Scope


class FoundryCollector:
    platform = "foundry"
    version = "foundry@0.1.0"

    def available(self) -> tuple[bool, str]:
        return False, "not implemented"

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        raise NotImplementedError

    def collect(self, ref: AgentRef) -> AgentBOM:
        raise NotImplementedError
