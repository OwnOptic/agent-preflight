# Fixture 2 - Contract router (Copilot Studio)

A real Copilot Studio agent, built in the demo tenant's Sandbox environment and exported as an
unmanaged solution (`AgentPreflightFixtures`). `solution/` is that export, unzipped exactly as
Dataverse wrote it; `scripts/export_fixture02.py` refreshes it.

What makes it part of the chain, all visible in the export:

- `bots/apf_contractRouter/bot.xml`: `authenticationmode` 1, meaning no end-user authentication
- `botcomponents/apf_contractRouter.topic.RouteEnquiry/data`: an HTTP request to fixture 03's Foundry
  agent, authenticated by an `api-key` header written into the topic, with no confirmation step

The key in that header is a placeholder, not a credential. The call can never succeed, and it does
not need to: the analysis reads the definition, not the traffic.

A solution export does not record which environment it came from or where the agent can be
reached, so `environment.json` carries both, written when the export was taken.
