"""A finding: one rule, one agent, one subject, with its evidence."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
SEVERITIES = ("critical", "high", "medium", "low")


@dataclass
class Finding:
    rule: str
    severity: str
    title: str
    message: str
    agent: str
    agent_name: str | None
    platform: str
    control: str
    location: str | None = None
    #: What the finding is about, part of the fingerprint. Stable across runs, so baselines work.
    subject: str = ""
    chain: list[str] = field(default_factory=list)
    baselined: bool = False

    @property
    def fingerprint(self) -> str:
        key = "|".join([self.rule, self.platform, self.agent, self.subject])
        return "sha256:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["fingerprint"] = self.fingerprint
        return d


def at_or_above(severity: str, threshold: str) -> bool:
    """Whether ``severity`` meets a ``--fail-on`` threshold. ``none`` never fails."""
    if threshold == "none":
        return False
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(threshold, 99)
