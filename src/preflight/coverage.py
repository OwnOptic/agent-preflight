"""Estate coverage: did this review see everything that is actually deployed?

Every other part of Preflight answers "is this agent safe to ship". This one answers the question a
reviewer asks afterwards and usually cannot: **is the thing I reviewed the thing that is running,
and is there anything running that I never reviewed at all**.

It reads the tenant's app catalog over Microsoft Graph:

    GET /v1.0/appCatalogs/teamsApps?$filter=distributionMethod eq 'organization'

and compares what is published against what this scan collected. Needs the delegated permission
``AppCatalog.Read.All``::

    az login --scope https://graph.microsoft.com/AppCatalog.Read.All

Without it, coverage reports itself unavailable and says why. A scan with no coverage information
is not a scan that found full coverage, and the report says which of the two it is.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from preflight.bom.models import AgentBOM

GRAPH = "https://graph.microsoft.com/v1.0/appCatalogs/teamsApps"
SCOPE = "https://graph.microsoft.com/AppCatalog.Read.All"


@dataclass
class Coverage:
    available: bool
    reason: str = ""
    #: Published in the tenant and present in this scan.
    reviewed: list[str] = field(default_factory=list)
    #: Published in the tenant and absent from this scan. The interesting list.
    unreviewed: list[str] = field(default_factory=list)

    def render(self) -> list[str]:
        if not self.available:
            return [f"COVERAGE   not checked: {self.reason}"]
        out = [f"COVERAGE   {len(self.reviewed)} of {len(self.reviewed) + len(self.unreviewed)} "
               "published agent(s) in this tenant were reviewed here"]
        for name in self.unreviewed[:10]:
            out.append(f"  unreviewed  {name}")
        if len(self.unreviewed) > 10:
            out.append(f"  and {len(self.unreviewed) - 10} more")
        return out


def _token(subscription: str | None) -> tuple[str | None, str]:
    az = shutil.which("az") or shutil.which("az.cmd")
    if not az:
        return None, "no az on PATH"
    cmd = [az, "account", "get-access-token", "--resource-type", "ms-graph", "--query", "accessToken", "-o", "tsv"]
    if subscription:
        cmd += ["--subscription", subscription]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=(os.name == "nt"))
    except Exception:
        return None, "az token call failed"
    return (r.stdout.strip() or None), ("" if r.stdout.strip() else "no az token; run az login")


def _published(token: str) -> tuple[list[dict] | None, str]:
    url = GRAPH + "?" + urllib.parse.urlencode({"$filter": "distributionMethod eq 'organization'"})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("value", []), ""
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return None, f"the token lacks AppCatalog.Read.All (HTTP {e.code}). Run: az login --scope {SCOPE}"
        return None, f"app catalog returned HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 - coverage reports, it never raises
        return None, f"app catalog unreachable: {type(e).__name__}"


def tenant_coverage(boms: list[AgentBOM], *, subscription: str | None = None,
                    published: list[dict] | None = None) -> Coverage:
    """``published`` is injectable so this is testable without a tenant."""
    if published is None:
        token, why = _token(subscription)
        if not token:
            return Coverage(available=False, reason=why)
        published, why = _published(token)
        if published is None:
            return Coverage(available=False, reason=why)

    known = {b.agent.id.lower() for b in boms}
    known |= {(b.agent.name or "").lower() for b in boms if b.agent.name}
    reviewed, unreviewed = [], []
    for app in published:
        name = app.get("displayName") or app.get("id") or "unnamed"
        ids = {str(app.get(k, "")).lower() for k in ("externalId", "id", "displayName")}
        (reviewed if ids & known else unreviewed).append(name)
    return Coverage(available=True, reviewed=sorted(reviewed), unreviewed=sorted(unreviewed))
