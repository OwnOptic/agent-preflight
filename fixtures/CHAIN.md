# The expected finding

This is the assertion the analyzer is tested against, in `tests/test_pipeline.py`. If
`preflight scan fixtures` does not produce this, the analyzer is wrong, not the fixtures.

## The chain

```
web content via WebSearch  [Inbox triage, m365-declarative]
  -> POST routeEnquiry (matched, auth none)  -> [Contract router, copilot-studio]
  -> POST callRecordsAgent (matched, auth key)  -> [records-agent, foundry]
  -> delete_record  IRREVERSIBLE (MCP, destructiveHint: true)
```

No `humanApproval` on the Copilot Studio action and `humanInTheLoop: false` on the Foundry agent.
On the MCP tool there is nothing to set: the Foundry v1 API rejects `require_approval` as an unknown
parameter, so the platform offers no tool-level approval gate here at all. **There is no human gate
anywhere on the path**, and on the last hop there is no mechanism for one.

## Why each edge resolves

| Edge | Signal | Confidence |
|---|---|---|
| 01 to 02 | `openapi-contract-router.yaml` server URL equals fixture 02's published Direct Line endpoint | matched |
| 02 to 03 | `callRecordsAgent` URL starts with fixture 03's endpoint, project plus agent id | matched |

Both are **matched**, not probed, and `delete_record` is declared destructive by its own server, so
the path is reported **Critical**.

## Why only one path is Critical

The records MCP server is not on the trusted list in `policy.example.yaml`. MCP says annotations from
an untrusted server must not be relied on, so `get_record` and `search_records`, which claim to be
read-only, are assumed to be irreversible anyway. Paths ending there are reported **High, as possible
paths**, one level lower, because their irreversibility is assumed rather than declared.
`delete_record` is different: the server itself declares it destructive, and an annotation that makes
a classification worse is accepted from any server.

Trust the server in policy and the two assumed sinks disappear, leaving only `delete_record`.

## Every expected finding

19 findings in total.

| Agent | Rule | Count | Why |
|---|---|---|---|
| 01 Inbox triage | ID-01 | 1 | `routeEnquiry` calls fixture 02 with no authentication |
| 01 Inbox triage | TS-06 | 2 | `OneDriveAndSharePoint` and `GraphConnectors` granted, never called for in the instructions |
| 01 Inbox triage | RA-07 | 1 | No disclaimer |
| 01 Inbox triage | ID-08 | 1 | Declares no irreversible action, reaches three through delegation |
| 02 Contract router | ID-01 | 1 | Direct Line endpoint published with `NoAuthentication` |
| 02 Contract router | ID-03 | 1 | `secretRef: inline` on the HTTP action |
| 02 Contract router | RA-04 | 1 | Generative answers over SharePoint with `citationsRequired: false` |
| 02 Contract router | MA-08 | 1 | Cross-platform call to fixture 03 authenticated by key |
| 02 Contract router | ID-08 | 1 | Reaches three irreversible actions it does not hold |
| 03 records-agent | AP-02 | 3 | One Critical to `delete_record`, two High possible paths to the assumed sinks |
| 03 records-agent | ID-03 | 1 | `secretRef: inline` on the MCP connection |
| 03 records-agent | TS-01 | 1 | MCP server attached with `allowed_tools: null` |
| 03 records-agent | RA-01 | 1 | `contentFilter: none` |
| 03 records-agent | RA-03 | 1 | `promptShields: false` |
| 03 records-agent | SC-05 | 1 | Two tools fall to fail-closed because the server is not trusted |
| 03 records-agent | CO-03 | 1 | No token cap, no max turns |

## What each agent looks like on its own

Individually approvable, which is the whole point. 01 researches and routes. 02 receives and
forwards. 03 manages records and can tidy obsolete ones. Each platform's own tooling sees one hop.
