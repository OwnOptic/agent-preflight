"""Policy as code.

The tool ships defaults; the organisation enforces its own. Every rule marked ``pol`` in the
catalog reads from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolOverride:
    untrusted_input: bool
    irreversible_action: bool


@dataclass
class Policy:
    origin: str = "defaults"
    allowed_regions: set[str] = field(default_factory=set)
    allowed_models: set[str] = field(default_factory=set)
    required_auth_modes: set[str] = field(default_factory=set)
    trusted_mcp_servers: set[str] = field(default_factory=set)
    budget_per_interaction: float | None = None
    max_cost_delta_pct: float | None = None
    tool_overrides: dict[str, ToolOverride] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "Policy":
        return cls()
