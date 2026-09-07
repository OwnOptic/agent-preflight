# The expected finding

This is the assertion the analyzer is tested against. If `preflight scan fixtures/` does not
produce this, the analyzer is wrong, not the fixtures.

## The chain

```
web content
  -> [01 inbox-triage]      M365 declarative, capability: WebSearch        UNTRUSTED INPUT
  -> POST routeEnquiry      OpenAPI server = fixture 02 Direct Line        cross-platform edge
  -> [02 contract-router]   Copilot Studio, NoAuthentication, published
  -> POST callRecordsAgent  url = fixture 03 project endpoint, key auth    cross-platform edge
  -> [03 records-agent]     Foundry, switzerlandnorth
  -> delete_record          MCP, destructiveHint: true                     IRREVERSIBLE ACTION
```

No `humanApproval` on the Copilot Studio action and `humanInTheLoop: false` on the Foundry agent.
On the MCP tool there is nothing to set: the Foundry v1 API rejects `require_approval` as an unknown
parameter, so the platform offers no tool-level approval gate here at all. **There is no human gate
anywhere on the path**, and on the last hop there is no mechanism for one.

## Why each edge resolves

| Edge | Signal | Confidence |
|---|---|---|
| 01 to 02 | `openapi-contract-router.yaml` server URL matches fixture 02's published Direct Line endpoint | matched |
| 02 to 03 | `callRecordsAgent` URL matches fixture 03's project endpoint and agent id | matched |

Both are **matched**, not probed, so the path is eligible to be reported **Critical**.

## Rules each fixture should also trip

| Fixture | Rule | Why |
|---|---|---|
| 01 | TS-06 | `OneDriveAndSharePoint` and `GraphConnectors` granted, never referenced in instructions |
| 01 | RA-07 | No disclaimer |
| 02 | ID-01 | `NoAuthentication` on a published Direct Line channel |
| 02 | RA-04 | Generative answers on, `citationsRequired: false` |
| 02 | ID-03 | `secretRef: inline` on the HTTP action |
| 03 | ID-03 | `secretRef: inline` on the MCP connection |
| 03 | TS-01 | MCP endpoint with `allowed_tools: null`, no allowlist |
| 03 | RA-01 | `contentFilter: none` |
| 03 | RA-03 | `promptShields: false` |
| 03 | SC-05 | Two of three MCP tools carry annotations; the server is not on the trusted list, so all three fall to fail-closed anyway |
| 03 | CO-03 | No token cap, no max turns |

## What each agent looks like on its own

Individually approvable, which is the whole point. 01 researches and routes. 02 receives and
forwards. 03 manages records and can tidy obsolete ones. Each platform's own tooling sees one hop.
