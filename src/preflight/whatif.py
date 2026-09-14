"""What-if: what would it take to make this pass?

A gate that only says no is a tax. The reviewer's real question is which single change removes the
finding, and the answer is computable: apply the change to the composition, run the same
deterministic analysis again, and diff the findings.

Three changes can be asked for, because they are the three a team actually makes:

    --approve TOOL      put a human gate on one tool
    --trust-server HOST treat one MCP server as trusted, so its annotations may be believed
    --remove-tool TOOL  take a tool off an agent

Nothing is written anywhere. The what-if runs entirely in memory, against the same collectors, and
reports the difference in findings. It is a question, not an edit.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from preflight.bom.models import AgentBOM
from preflight.findings import SEVERITY_ORDER, Finding
from preflight.pipeline import Result, analyze
from preflight.policy import Policy


@dataclass
class Change:
    approve: set[str] = field(default_factory=set)
    trust_servers: set[str] = field(default_factory=set)
    remove_tools: set[str] = field(default_factory=set)

    def describe(self) -> list[str]:
        out = []
        out += [f"put a human gate on `{t}`" for t in sorted(self.approve)]
        out += [f"trust the MCP server {s}" for s in sorted(self.trust_servers)]
        out += [f"remove the tool `{t}`" for t in sorted(self.remove_tools)]
        return out

    def matches(self, tool_id: str, tool_name: str, wanted: Iterable[str]) -> bool:
        w = {x.lower() for x in wanted}
        return tool_id.lower() in w or tool_name.lower() in w

    def hook(self) -> Callable[[list[AgentBOM]], None]:
        def apply(boms: list[AgentBOM]) -> None:
            for b in boms:
                kept = []
                for t in b.tools:
                    if self.matches(t.id, t.name, self.remove_tools):
                        continue
                    if self.matches(t.id, t.name, self.approve):
                        t.approval = True
                    kept.append(t)
                b.tools = kept
        return apply


@dataclass
class WhatIf:
    before: Result
    after: Result
    change: Change

    @property
    def fixed(self) -> list[Finding]:
        after = {f.fingerprint for f in self.after.findings}
        return [f for f in self.before.findings if f.fingerprint not in after]

    @property
    def introduced(self) -> list[Finding]:
        before = {f.fingerprint for f in self.before.findings}
        return [f for f in self.after.findings if f.fingerprint not in before]

    def render(self) -> str:
        L = [f"WHAT IF   {', and '.join(self.change.describe()) or 'nothing changes'}", ""]
        counts = lambda r: {  # noqa: E731 - a local formatting helper, not a function worth a name
            s: sum(1 for f in r.findings if f.severity == s) for s in ("critical", "high", "medium", "low")
        }
        b, a = counts(self.before), counts(self.after)
        L.append("  severity   before -> after")
        for s in ("critical", "high", "medium", "low"):
            arrow = "same" if b[s] == a[s] else ("better" if a[s] < b[s] else "worse")
            L.append(f"  {s:<10} {b[s]:>6} -> {a[s]:<5} {arrow}")
        L.append("")
        for label, items in (("fixed", self.fixed), ("introduced", self.introduced)):
            if not items:
                continue
            L.append(f"  {label}:")
            for f in sorted(items, key=lambda x: (-SEVERITY_ORDER[x.severity], x.rule))[:12]:
                L.append(f"    {f.severity:<8} {f.rule}  {f.agent_name or f.agent}: {f.message[:96]}")
            L.append("")
        if not self.fixed and not self.introduced:
            L.append("  Nothing changed. The finding does not depend on what you changed.")
        return "\n".join(L)


def _expand_servers(wanted: set[str], boms: list[AgentBOM]) -> set[str]:
    """A policy trusts a server by its full URL; a person says "trust this host". Accept both, by
    expanding each request against the servers this estate actually uses."""
    out = set(wanted)
    for b in boms:
        for t in b.tools:
            s = t.source.server or ""
            if not s:
                continue
            host = urlsplit(s).netloc.lower()
            if any(w.lower() in (s.lower(), host) for w in wanted):
                out.add(s)
    return out


def what_if(path: str | Path, policy: Policy, change: Change, **kwargs) -> WhatIf:
    before = analyze(path, policy, **kwargs)
    servers = policy.trusted_mcp_servers | _expand_servers(change.trust_servers, before.boms)
    trusted = Policy(**{**policy.__dict__, "trusted_mcp_servers": servers})
    after = analyze(path, trusted, hook=change.hook(), **kwargs)
    return WhatIf(before=before, after=after, change=change)
