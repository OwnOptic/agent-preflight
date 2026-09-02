# Agent Preflight

Design-time governance for Microsoft agents, across platforms. Read-only, no deployed traffic, no
token spend on the deterministic pass, and it runs before the agent is registered.

One control point for **governance, security, cost and compliance**.

![Architecture](docs/architecture.svg)

## Why

Microsoft Foundry ships evaluators, continuous evaluation over live traffic, the AI Red Teaming
Agent and Agent Optimizer. Agent 365 ships a registry that inventories agents across Foundry and
Copilot Studio, with Entra Agent ID providing identity and lifecycle underneath.

Every one of those needs an agent that is already deployed, producing traffic, or registered. None
of them answers the two questions a reviewer actually has to answer:

**Is this safe to ship, and what changed since last time.**

`Azure/PSRule.Rules.Azure` already validates Azure infrastructure as code before deployment and
emits SARIF. Preflight is its missing sibling one layer up.

## What it does

Resolves any Microsoft agent into an **AgentBOM**, a signed, transitive bill of materials covering
models, tools, toolbox versions, auth modes, knowledge sources, storage, residency and downstream
agents. Then reasons over it, deterministically:

- **Attack path analysis.** Untrusted input reaching an irreversible action with no human gate.
  Paths are followed across the tool graph, across the A2A graph, and **across platform boundaries**,
  where each platform's own tooling sees a single hop and reports it clean.
- **Effective privilege closure.** Identity plus every on-behalf-of passthrough plus every
  downstream agent reachable by delegation. Effective privilege, not declared.
- **Cost analysis.** Priced from the definition before a token is spent: prompt tax, tool surface
  tax, grounding, and fan-out amplification across the delegation graph.
- **Rule engine.** Every finding carries a rule id, a severity and a named Cloud Adoption Framework
  or Zero Trust control, so a finding is audit evidence rather than an opinion.
- **Supply chain.** MCP rug-pull detection by pinned manifest hash, toolbox drift, provenance, and
  injection payload scanning.

Outputs are SARIF for GitHub code scanning, a governance dossier rendered from a versioned template,
and a certification tied to the BOM hash that any composition change voids.

## Design commitments

**The rule engine is deterministic.** A gate must give the same answer twice. Tool classification is
resolved by policy override, then a first-party registry, then protocol metadata (MCP
`ToolAnnotations`, HTTP method for OpenAPI, connector metadata for Copilot Studio), then fail closed.
Never by asking a model.

**Confidence gates severity.** A path is reported critical only when every edge on it is proven or
matched. Anything resting on a probe drops a level and is labelled a possible path.

**Nothing is invented.** Every dossier field traces to a BOM field or a rule result. Anything that
cannot be derived prints *requires human input* rather than being manufactured.

**Read-only, always.** No writes to any agent.

## Not a competitor

Preflight runs before registration and produces exactly the composition metadata that the Agent 365
registry's external-platform sync path ingests. It complements the control plane rather than
duplicating it.

## Status

Design complete, implementation starting. Full specification in
**[docs/capabilities.md](docs/capabilities.md)**: collectors, AgentBOM schema v0.1, the analyzers,
the rule catalog with control mappings, the dossier template, build order and open questions.

## Provenance

Created for the Microsoft Global Hackathon 2026. Intellectual property created during the hackathon
belongs to Microsoft under the Event Participation and Confidentiality Agreement, which is why this
repository is private and carries no open-source licence.
