"""Agent 365 and Entra Agent ID collector.

Reads: registry roster, ownership and sponsor, blueprints, OBO versus autonomous

Access: Microsoft Graph. Requires Microsoft E7 or the Agent 365 add-on, so available() returns False on most tenants.
"""

from __future__ import annotations

from typing import Iterable

from preflight.bom.models import AgentBOM
from preflight.collectors.base import AgentRef, Scope


class Agent365Collector:
    platform = "external"
    version = "agent365@0.1.0"

    def available(self) -> tuple[bool, str]:
        return False, "not implemented"

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        raise NotImplementedError

    def collect(self, ref: AgentRef) -> AgentBOM:
        raise NotImplementedError
