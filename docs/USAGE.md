# Running Preflight against your own agents

Nothing here writes to an agent, sends traffic to one, or spends tokens. Every command reads
definitions and exits.

## Install

```bash
pip install -e .
preflight --version
```

## Point it at something

`preflight scan` takes a directory and finds whatever it recognises inside it.

| Platform | What to put in the directory |
|---|---|
| M365 declarative agents | the `manifest.json`, its `declarativeAgent.json`, and any plugin manifests and OpenAPI files they reference |
| Copilot Studio | an unmanaged solution export, unzipped, plus `environment.json` (below) |
| Foundry | exported agent JSON, or read the project live with `--live-foundry` |

```bash
preflight scan ./agents --policy policies/swiss.yaml
```

### Copilot Studio

Export the solution containing the agent (Copilot Studio > Solutions > Export, unmanaged), unzip it,
and write `environment.json` beside it:

```json
{
  "environmentId": "<environment guid>",
  "region": "switzerland",
  "published": true,
  "endpoints": ["https://<env-host>.environment.api.powerplatform.com/copilotstudio/dataverse-backed/authenticated/bots/<schema name>/conversations"]
}
```

A solution export records neither the environment nor where the agent answers, and Preflight will
not guess: without this file the agent has no endpoints and no region, and the report says so. The
endpoint is the connection string on the agent's **Channels** page.

### Copilot Studio, live

No export step: read the environment itself, read-only.

```bash
preflight scan ./agents \
  --live-copilot-studio https://<org>.crm<n>.dynamics.com \
  --cs-environment-id <environment guid> \
  --subscription <subscription id> \
  --region switzerland
```

The Dataverse org URL is on **Settings > Session details** in any Power Platform app. Without
`--cs-environment-id` the agent still reports fully, but it has no connection URL, so a call from
another agent cannot be matched to it. The environment id is on the agent's **Settings > Advanced**
page in Copilot Studio.

### Foundry, live

```bash
preflight scan ./agents \
  --live-foundry https://<resource>.services.ai.azure.com/api/projects/<project> \
  --subscription <subscription id> \
  --region switzerlandnorth
```

Read-only, `GET` only. The account needs **Cognitive Services User** on the resource; Owner alone
does not grant `AIServices/agents`. Always pass `--subscription`: the Azure CLI's default context
drifts, and a token from the wrong tenant fails as an unhelpful 401.

## Make the result mean something

```bash
# Accept what exists today, so only new findings fail the build.
preflight baseline ./agents --policy policies/swiss.yaml --out preflight.baseline.json

# Record what each MCP server's tool manifest looked like at approval.
preflight pin ./agents --out preflight.lock.json

# Certify a composition. Any change to it voids the certificate.
preflight certify ./agents --out preflight.cert.json --by "security review"
```

Then the gate itself:

```bash
preflight scan ./agents \
  --policy policies/swiss.yaml \
  --baseline preflight.baseline.json \
  --lock preflight.lock.json \
  --sarif preflight.sarif \
  --dossier dossier \
  --fail-on critical
```

`--sarif` uploads to GitHub code scanning, so findings land on the pull request. `--dossier` writes
one governance dossier per agent; fields that cannot be derived print *requires human input* rather
than a guess. `.github/workflows/preflight.yml` in this repository is a working example.

## Policy

`policies/` holds Swiss, EU and financial-services packs. A policy decides what counts as a
violation rather than what the tool can see: allowed regions, permitted authentication modes,
trusted MCP servers, prices and budgets. Without prices, cost is reported in tokens and money is
left unstated.

## What it will not tell you

- Whether a tool behaves as its description claims. Preflight reads definitions, not behaviour.
- Anything about a platform it cannot read. Agent Framework and Agent 365 collectors are stubs, and
  an unavailable collector is reported as skipped, never as clean.
- Whether an unknown field is safe. A field the platform does not expose is unknown, never false.
