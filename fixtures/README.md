# Fixtures

Three agents, each individually plausible and individually approvable. Nothing is obviously wrong
with any of them in isolation. That is the point.

| # | Agent | Platform | Individually |
|---|---|---|---|
| 1 | Inbox triage | M365 declarative | `WebSearch` capability plus an API plugin action that POSTs to an internal endpoint |
| 2 | Contract router | Copilot Studio | No end-user sign-in, a topic whose HTTP request calls another service with a key |
| 3 | Records agent | Foundry | Toolbox with an MCP server carrying `destructiveHint: true`, key auth, no allowlist, no human gate |

All three exist in their platforms: 1 is in the tenant's app catalog, 2 is a real Copilot Studio
solution export, and 3 is a live Foundry agent.

The composed defect nobody reviewed: agent 1's plugin endpoint is agent 2's connection URL,
and agent 2's HTTP action is agent 3's project endpoint. Untrusted web content reaches a
destructive tool through three agents and two platform boundaries.
