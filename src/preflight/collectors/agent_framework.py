"""Microsoft Agent Framework collector.

Reads: tools registered at build time, plus OpenTelemetry semantic attributes where available

Access: Code-first, so there is no declarative artifact to read. Hardest collector; likely needs an exporter contributed upstream.
"""

from __future__ import annotations

from typing import Iterable

from preflight.bom.models import AgentBOM
from preflight.collectors.base import AgentRef, Scope


class AgentFrameworkCollector:
    platform = "agent-framework"
    version = "agent_framework@0.1.0"

    def available(self) -> tuple[bool, str]:
        return False, "not implemented"

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        raise NotImplementedError

    def collect(self, ref: AgentRef) -> AgentBOM:
        raise NotImplementedError
