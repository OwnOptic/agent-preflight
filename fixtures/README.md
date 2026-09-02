# Fixtures

Three agents, each individually plausible and individually approvable. Nothing is obviously wrong
with any of them in isolation. That is the point.

| # | Agent | Platform | Individually |
|---|---|---|---|
| 1 | Inbox triage | M365 declarative | `WebSearch` capability plus an API plugin action that POSTs to an internal endpoint |
| 2 | Contract router | Copilot Studio | Published agent, HTTP action to an internal service, key auth |
| 3 | Records agent | Foundry | Toolbox with an MCP server carrying `destructiveHint: true`, key auth, no allowlist, no human gate |

The composed defect nobody reviewed: agent 1's plugin endpoint is agent 2's Direct Line endpoint,
and agent 2's HTTP action is agent 3's project endpoint. Untrusted web content reaches a
destructive tool through three agents and two platform boundaries.
