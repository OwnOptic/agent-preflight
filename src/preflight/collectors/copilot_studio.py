"""Copilot Studio collector.

Reads: topics, knowledge sources, actions, channels, authentication mode, connector references

Access: Solution export (unmanaged) or the Dataverse bot tables. Prefer solution export: offline, versionable, needs no live environment.
"""

from __future__ import annotations

from typing import Iterable

from preflight.bom.models import AgentBOM
from preflight.collectors.base import AgentRef, Scope


class CopilotStudioCollector:
    platform = "copilot-studio"
    version = "copilot_studio@0.1.0"

    def available(self) -> tuple[bool, str]:
        return False, "not implemented"

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        raise NotImplementedError

    def collect(self, ref: AgentRef) -> AgentBOM:
        raise NotImplementedError
