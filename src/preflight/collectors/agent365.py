"""Agent 365 registry collector.

Reads: the tenant's agent registry, over Microsoft Graph, read-only.

    GET /v1.0/copilot/admin/catalog/packages

What the registry adds that a definition cannot: **who is accountable**, whether an agent is blocked,
and who it is deployed to. It is also the only place that knows an agent exists at all, which is how
Preflight can tell a reviewed estate from a reviewed sample of one.

Access needs an Agent 365 or Microsoft E7 licence in the tenant, plus the delegated permission
``CopilotPackages.Read.All``. The Azure CLI token does not carry that scope by default, so::

    az login --scope https://graph.microsoft.com/CopilotPackages.Read.All

Without it this collector reports itself unavailable, with the reason, and the scan continues. An
unavailable collector is a normal outcome, never silently a clean one.

Registry entries are not agent definitions: the registry does not say what tools an agent holds. So
the BOM built here carries identity, accountability and status, and the analysers that need a
composition simply have none to read. That is deliberate, and it is why these agents appear on the
``external`` platform rather than pretending to be a definition Preflight resolved.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from preflight.bom.models import Agent, AgentBOM, Generator, Guards, Identity, Instructions
from preflight.collectors.base import AgentRef, Scope

GRAPH = "https://graph.microsoft.com/v1.0/copilot/admin/catalog/packages"
SCOPE = "https://graph.microsoft.com/CopilotPackages.Read.All"


class Agent365Collector:
    platform = "external"
    version = "agent365@0.1.0"

    def __init__(self, *, subscription: str | None = None, token: str | None = None) -> None:
        self.subscription = subscription
        self._token = token
        self._packages: list[dict[str, Any]] | None = None
        self._why = ""

    # --- access -------------------------------------------------------------------------

    def _get_token(self) -> str | None:
        if self._token:
            return self._token
        az = shutil.which("az") or shutil.which("az.cmd")
        if not az:
            self._why = "no az on PATH"
            return None
        cmd = [az, "account", "get-access-token", "--resource-type", "ms-graph",
               "--query", "accessToken", "-o", "tsv"]
        if self.subscription:
            cmd += ["--subscription", self.subscription]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=(os.name == "nt"))
        except Exception:
            self._why = "az token call failed"
            return None
        self._token = r.stdout.strip() or None
        if not self._token:
            self._why = "no az token; run az login"
        return self._token

    def _fetch(self) -> list[dict[str, Any]] | None:
        if self._packages is not None:
            return self._packages
        token = self._get_token()
        if not token:
            return None
        req = urllib.request.Request(GRAPH, headers={"Authorization": f"Bearer {token}",
                                                     "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self._packages = json.loads(resp.read().decode("utf-8")).get("value", [])
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                self._why = (f"the token lacks CopilotPackages.Read.All, or the tenant has no Agent 365 "
                             f"licence (HTTP {e.code}). Run: az login --scope {SCOPE}")
            else:
                self._why = f"registry returned HTTP {e.code}"
            return None
        except Exception as e:  # noqa: BLE001 - a collector reports, it never raises
            self._why = f"registry unreachable: {type(e).__name__}"
            return None
        return self._packages

    def available(self) -> tuple[bool, str]:
        pkgs = self._fetch()
        if pkgs is None:
            return False, self._why or "agent registry unavailable"
        return True, f"agent registry readable, {len(pkgs)} package(s)"

    # --- collection ---------------------------------------------------------------------

    def discover(self, scope: Scope) -> Iterable[AgentRef]:
        """Only what the tenant is accountable for.

        Microsoft's own agents and marketplace listings are inventory, not this estate's
        composition, and including 200 of them would drown the agents a reviewer owns.
        """
        for p in self._fetch() or []:
            if str(p.get("type", "")).lower() not in ("custom", "lob", "sideloaded"):
                continue
            yield AgentRef(id=str(p.get("id")), platform=self.platform,
                           name=p.get("displayName"), scope=Scope(tenant=scope.tenant))

    def collect(self, ref: AgentRef) -> AgentBOM:
        p = next((x for x in self._fetch() or [] if str(x.get("id")) == ref.id), {})
        owner = p.get("owner") or p.get("publisher")
        return AgentBOM(
            generated=datetime.now(UTC),
            generator=Generator(collector=self.version),
            agent=Agent(
                id=str(p.get("manifestId") or p.get("id") or ref.id),
                platform=self.platform,
                name=p.get("displayName"),
                description=p.get("shortDescription"),
                # The registry records an app identity; it does not record what the agent may do.
                identity=Identity(kind="app-registration" if p.get("appId") else "unknown",
                                  appId=p.get("appId")),
                instructions=Instructions(),
                sourceFile=f"agent365:{p.get('id')}",
            ),
            guards=Guards(),
            tags={
                "registry": "agent365",
                "registryId": str(p.get("id") or ""),
                "owner": owner,
                "blocked": str(p.get("isBlocked")) if p.get("isBlocked") is not None else None,
                "availableTo": p.get("availableTo"),
                "deployedTo": p.get("deployedTo"),
                "originPlatform": p.get("platform"),
                "elementTypes": ",".join(p.get("elementTypes") or []) or None,
            },
        )
