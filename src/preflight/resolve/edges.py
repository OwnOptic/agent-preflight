"""Cross-platform edge resolution.

The headline claim is that a path crosses platforms. That claim is only as good as the ability to
prove an edge exists between agent A on one platform and agent B on another, from definitions alone.

Two signals, strongest first, and every edge records which one produced it:

    identity   the call's scope names an Entra identity already in the estate     proven
    endpoint   the call's URL starts with an endpoint another agent publishes     matched

The probe tier (fetch an A2A agent card, or send an MCP ``initialize``) makes a network call, which
breaks the no-traffic promise, so it is not implemented here. An outbound URL that resolves to
nothing is left as an ordinary tool: if it is irreversible it is a sink, which is the conservative
reading.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from preflight.bom.models import AgentBOM, Edge

#: Tool kinds that can carry a call to another agent, and how the edge is labelled.
_VIA = {"openapi": "openapi", "connector": "http-action", "a2a": "a2a"}

_EU = {
    "westeurope", "northeurope", "europe", "francecentral", "germanywestcentral",
    "swedencentral", "italynorth", "polandcentral", "spaincentral",
}


def normalise(url: str | None) -> str:
    """Canonical ``scheme://host/path``: lowercase host, no query, no fragment, no trailing slash."""
    if not url:
        return ""
    s = urlsplit(url.strip())
    if s.scheme.lower() not in ("http", "https"):
        return ""
    return f"{s.scheme.lower()}://{s.netloc.lower()}{s.path.rstrip('/')}"


def geo(region: str | None) -> str | None:
    """Coarse data boundary for a region name, so 'switzerland' and 'switzerlandnorth' agree."""
    r = (region or "").lower().replace(" ", "")
    if not r:
        return None
    if r.startswith("switzerland"):
        return "CH"
    if r in _EU:
        return "EU"
    return r


def _geos(bom: AgentBOM) -> set[str]:
    return {g for g in (geo(r) for r in bom.residency.observed) if g}


def resolve(boms: list[AgentBOM]) -> list[AgentBOM]:
    """Populate ``edges`` on every BOM. Replaces any edges already present; idempotent."""
    index: list[tuple[str, AgentBOM]] = []
    for b in boms:
        for ep in b.agent.endpoints:
            n = normalise(ep)
            if n:
                index.append((n, b))
    # Longest endpoint first, so a specific agent path beats its project root.
    index.sort(key=lambda x: len(x[0]), reverse=True)

    by_app = {b.agent.identity.appId.lower(): b for b in boms if b.agent.identity.appId}

    for b in boms:
        b.edges = []
        for t in b.tools:
            if t.kind not in _VIA:
                continue
            out = normalise(t.source.server)
            if not out:
                continue

            target, signal, confidence = None, None, None
            for scope in t.auth.scopes:
                for app, other in by_app.items():
                    if other is not b and app in scope.lower():
                        target, signal, confidence = other, "identity", "proven"
                        break
                if target:
                    break

            if target is None:
                for ep, other in index:
                    if other is b:
                        continue
                    if out == ep or out.startswith(ep + "/"):
                        target, signal, confidence = other, "endpoint", "matched"
                        break

            if target is None:
                continue

            ga, gb = _geos(b), _geos(target)
            b.edges.append(
                Edge(
                    from_=b.agent.id,
                    to=target.agent.id,
                    tool=t.id,
                    via=_VIA[t.kind],
                    endpoint=t.source.server,
                    auth=t.auth.mode,
                    crossPlatform=b.agent.platform != target.agent.platform,
                    crossRegion=bool(ga and gb and ga.isdisjoint(gb)),
                    crossTenant=False,
                    signal=signal,
                    confidence=confidence,
                )
            )
    return boms
