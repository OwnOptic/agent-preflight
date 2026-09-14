"""The probe tier: ask an endpoint what it is.

Identity and endpoint matching resolve edges from definitions alone, which is why they are the
default. Some endpoints resolve to nothing, and then Preflight has a choice: call the target and
find out, or say it does not know. It says it does not know, unless you ask for a probe.

``--probe`` is opt-in because it breaks the promise the rest of the tool keeps: it puts a request on
the network. What it sends is the smallest, most boring thing that identifies a service:

    GET {endpoint}/.well-known/agent.json        the A2A agent card
    GET {endpoint}/.well-known/agent-card.json   its newer name

No credentials, no payload, a short timeout, and a GET. It never sends a prompt, never calls a tool
and never authenticates, so it cannot cause a side effect on the target. An endpoint that answers
with a card naming an agent in the estate produces an edge with signal ``probe``. That edge is
marked ``probed`` rather than ``proven``, and the severity gate treats it as weaker evidence, which
is the whole point of recording how a thing was learned rather than only what was learned.

The report says a probe ran. A scan whose result depends on a network call should never be mistaken
for one that did not need it.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit

from preflight.bom.models import AgentBOM, Edge
from preflight.resolve.edges import _VIA, geo, normalise

CARD_PATHS = ("/.well-known/agent.json", "/.well-known/agent-card.json")
Fetcher = Callable[[str], dict | None]


def _http_get_json(url: str, timeout: float = 3.0) -> dict | None:
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def card_identifiers(card: dict) -> set[str]:
    """Every string in an agent card that could name an agent this estate already knows."""
    out: set[str] = set()
    for key in ("name", "id", "agentId", "schemaName", "clientId", "appId"):
        v = card.get(key)
        if isinstance(v, str) and v.strip():
            out.add(v.strip().lower())
    provider = card.get("provider")
    if isinstance(provider, dict) and isinstance(provider.get("organization"), str):
        out.add(provider["organization"].strip().lower())
    return out


def _estate_index(boms: list[AgentBOM]) -> dict[str, AgentBOM]:
    idx: dict[str, AgentBOM] = {}
    for b in boms:
        for key in (b.agent.id, b.agent.name, b.agent.identity.appId):
            if key:
                idx[key.strip().lower()] = b
    return idx


def probe(boms: list[AgentBOM], *, fetch: Fetcher | None = None) -> list[str]:
    """Resolve what endpoint matching could not. Returns a note per probe attempted, for the report.

    Only unresolved outbound tools are probed: anything already matched by identity or endpoint is
    left exactly as it was, because a weaker signal must never overwrite a stronger one.
    """
    get = fetch or _http_get_json
    index = _estate_index(boms)
    notes: list[str] = []

    for b in boms:
        resolved = {e.tool for e in b.edges if e.tool}
        for t in b.tools:
            if t.kind not in _VIA or t.id in resolved:
                continue
            base = normalise(t.source.server)
            if not base:
                continue
            root = f"{urlsplit(base).scheme}://{urlsplit(base).netloc}"
            card = next((c for c in (get(root + p) for p in CARD_PATHS) if c), None)
            if card is None:
                notes.append(f"{b.agent.id}: {root} returned no agent card")
                continue
            target = next((index[i] for i in card_identifiers(card) if i in index), None)
            if target is None or target is b:
                notes.append(f"{b.agent.id}: {root} identified itself, but as nothing in this estate")
                continue
            ga, gb = _geos(b), _geos(target)
            b.edges.append(
                Edge(
                    **{"from": b.agent.id},
                    to=target.agent.id,
                    tool=t.id,
                    via=_VIA[t.kind],
                    endpoint=t.source.server,
                    auth=t.auth.mode,
                    crossPlatform=b.agent.platform != target.agent.platform,
                    crossRegion=bool(ga and gb and ga.isdisjoint(gb)),
                    crossTenant=False,
                    signal="probe",
                    confidence="probed",
                )
            )
            notes.append(f"{b.agent.id}: {root} identified itself as {target.agent.id}")
    return notes


def _geos(bom: AgentBOM) -> set[str]:
    return {g for g in (geo(r) for r in bom.residency.observed) if g}


def endpoints_that_would_be_probed(boms: Iterable[AgentBOM]) -> list[str]:
    """What ``--probe`` would contact, so it can be printed before anyone turns it on."""
    out: list[str] = []
    for b in boms:
        resolved = {e.tool for e in b.edges if e.tool}
        for t in b.tools:
            if t.kind in _VIA and t.id not in resolved and normalise(t.source.server):
                s = urlsplit(normalise(t.source.server))
                out.append(f"{s.scheme}://{s.netloc}")
    return sorted(set(out))
