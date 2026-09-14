"""Policy as code.

The tool ships defaults; the organisation enforces its own. Every rule marked ``pol`` in the
catalog reads from here, and so does the classifier's trusted-server list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ToolOverride:
    untrusted_input: bool
    irreversible_action: bool


@dataclass
class Policy:
    origin: str = "defaults"
    residency: str | None = None
    allowed_regions: set[str] = field(default_factory=set)
    allowed_models: set[str] = field(default_factory=set)
    required_auth_modes: set[str] = field(default_factory=set)
    trusted_mcp_servers: set[str] = field(default_factory=set)
    budget_per_interaction: float | None = None
    max_cost_delta_pct: float | None = None
    currency: str = "USD"
    #: Models the organisation has retired or is retiring. ML-01 reads this, because no platform
    #: tells you at design time that a deployment is about to disappear.
    deprecated_models: set[str] = field(default_factory=set)
    #: CO-08: whether every agent must carry a cost centre, and under which tag.
    require_cost_centre: bool = False
    cost_centre_tag: str = "costCentre"
    #: ML-05: how long a certification stays valid before the agent must be reviewed again.
    recertify_days: int | None = None
    #: Model or deployment name -> price per million input tokens. Empty means cost is reported in
    #: tokens only. Fill from the Azure pricing page rather than guessing.
    prices: dict[str, float] = field(default_factory=dict)
    tool_overrides: dict[str, ToolOverride] = field(default_factory=dict)

    @classmethod
    def default(cls) -> Policy:
        return cls()

    @classmethod
    def load(cls, path: str | Path) -> Policy:
        p = Path(path)
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        overrides = {
            k: ToolOverride(
                untrusted_input=bool(v.get("untrusted_input", True)),
                irreversible_action=bool(v.get("irreversible_action", True)),
            )
            for k, v in (raw.get("tool_overrides") or {}).items()
        }
        return cls(
            origin=str(p),
            residency=raw.get("residency"),
            allowed_regions=set(raw.get("allowed_regions") or []),
            allowed_models=set(raw.get("allowed_models") or []),
            required_auth_modes=set(raw.get("required_auth_modes") or []),
            trusted_mcp_servers=set(raw.get("trusted_mcp_servers") or []),
            budget_per_interaction=raw.get("budget_per_interaction"),
            max_cost_delta_pct=raw.get("max_cost_delta_pct"),
            currency=raw.get("currency") or "USD",
            deprecated_models=set(raw.get("deprecated_models") or []),
            require_cost_centre=bool(raw.get("require_cost_centre", False)),
            cost_centre_tag=raw.get("cost_centre_tag") or "costCentre",
            recertify_days=raw.get("recertify_days"),
            prices={str(k): float(v) for k, v in (raw.get("prices_per_million_input_tokens") or {}).items()},
            tool_overrides=overrides,
        )
