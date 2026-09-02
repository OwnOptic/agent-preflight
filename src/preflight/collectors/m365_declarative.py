"""Microsoft 365 declarative agents collector.

Reads: declarativeAgent.json capabilities, instructions, actions, behavior_overrides and disclaimer, plus every referenced API plugin manifest and its OpenAPI document

Access: Files on disk. Needs no licence and no tenant, which makes this the cheapest collector to finish.
"""

from __future__ import annotations

from typing import Iterable

from preflight.bom.models import AgentBOM
from preflight.collectors.base import AgentRef, Scope


class M365DeclarativeCollector:
    platform = "m365-declarative"
    version = "m365_declarative@0.1.0"

    def available(self) -> tuple[bool, str]:
        return False, "not implemented"

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        raise NotImplementedError

    def collect(self, ref: AgentRef) -> AgentBOM:
        raise NotImplementedError
