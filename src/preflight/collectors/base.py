"""Collector interface.

A collector turns one agent, on one platform, into an :class:`AgentBOM`. It is the only
part of Preflight that talks to a platform, and it is strictly read-only.

Adding a platform means implementing this protocol and registering it. Nothing else in the
codebase changes, because every analyzer reads the BOM and never the platform.

Contract
--------
* **Read-only.** A collector never writes to an agent. No exceptions.
* **No inference.** A collector reports what the definition says. It does not classify tools
  and it does not resolve cross-platform edges; those run afterwards, over the whole estate,
  in ``preflight.classify`` and ``preflight.resolve``.
* **Absent is not zero.** A field the platform does not expose is ``None``. Analyzers treat
  ``None`` as "absent and therefore a finding", which is why a collector must never fill a
  gap with a default.
* **Deterministic.** The same agent definition produces the same BOM, byte for byte after
  canonicalisation. No timestamps beyond ``generated``, no ordering by dictionary iteration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

from preflight.bom.models import AgentBOM, Platform

__all__ = ["AgentRef", "Scope", "Collector", "register", "get_collector", "all_collectors"]


@dataclass(frozen=True)
class Scope:
    """Where to look. Interpretation is platform-specific.

    Foundry reads ``subscription``/``resource_group``/``project``; Copilot Studio reads
    ``environment``; the declarative-agent collector reads ``path``.
    """

    subscription: str | None = None
    resource_group: str | None = None
    project: str | None = None
    environment: str | None = None
    tenant: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class AgentRef:
    """A discovered agent, before anything has been collected about it."""

    id: str
    platform: Platform
    name: str | None = None
    scope: Scope | None = None


@runtime_checkable
class Collector(Protocol):
    """One platform. Implement, register, done."""

    #: Platform this collector speaks for. Must match ``AgentBOM.agent.platform``.
    platform: Platform

    #: ``name@version``, recorded in ``AgentBOM.generator.collector`` for provenance.
    version: str

    def available(self) -> tuple[bool, str]:
        """Whether this collector can run here.

        Returns ``(False, reason)`` rather than raising, so ``preflight scan`` can report
        "Agent 365 collector skipped: requires Microsoft E7 or the Agent 365 add-on" instead
        of failing the run. A missing licence or credential is a normal outcome, not an error.
        """
        ...

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        """Enumerate agents in scope. Cheap: identifiers only, no composition."""
        ...

    def collect(self, ref: AgentRef) -> AgentBOM:
        """Resolve one agent into a BOM.

        Transitive within the platform: a toolbox is followed to the tools it contains, and a
        tool that wraps a remote MCP server is followed to that server's tool manifest. Not
        transitive across platforms; an outbound endpoint is recorded as an unresolved edge and
        ``preflight.resolve`` matches it against the rest of the estate later.
        """
        ...


_REGISTRY: dict[Platform, Collector] = {}


def register(collector: Collector) -> Collector:
    """Register a collector. Usable as a decorator on the class or on an instance factory."""
    if collector.platform in _REGISTRY:
        raise ValueError(f"collector already registered for platform {collector.platform!r}")
    _REGISTRY[collector.platform] = collector
    return collector


def get_collector(platform: Platform) -> Collector:
    try:
        return _REGISTRY[platform]
    except KeyError:
        raise LookupError(f"no collector registered for platform {platform!r}") from None


def all_collectors() -> list[Collector]:
    return list(_REGISTRY.values())
