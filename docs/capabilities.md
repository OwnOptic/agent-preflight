# Agent Preflight

Design-time governance for Microsoft agents, across platforms. Read-only, no deployed traffic, no
token spend on the deterministic pass, and it runs before the agent is registered.

One control point for **governance, security, cost and compliance**.

> **Status, 2026-09-11.** The engine is built: collectors for M365 declarative agents, Copilot Studio
> and Foundry (files and live), edge resolution, attack paths, privilege closure, cost, 15 of the
> catalog's rules, SARIF, the dossier, certification and MCP pinning, with 29 tests. This document
> remains the full specification; the README's Status table separates built from roadmap.

---

## 1. Positioning

**What exists already, and must not be re-built.** Foundry ships evaluators, continuous evaluation
over live traffic, the AI Red Teaming Agent and Agent Optimizer. Agent 365 ships a Registry that
inventories agents from Foundry and Copilot Studio, admin-registered agents, shadow agents found in
the tenant, and metadata synced from external platforms, with Entra Agent ID providing identity,
blueprints and sponsor lifecycle underneath.

**The two gaps that survive.**
1. **Moment.** Everything above needs an agent that is deployed, producing traffic, or registered.
   Nothing answers "is this safe to ship" at the moment a reviewer has to decide.
2. **Layer.** The registry inventories identity, ownership and basic metadata. Nothing resolves
   *composition*: which toolbox version, which auth mode per connection, which knowledge sources,
   which downstream agents, transitively and across platforms.

**The precedent.** `Azure/PSRule.Rules.Azure` already validates Azure infrastructure as code before
deployment and emits SARIF. Preflight is its missing sibling one layer up. This framing does more
work than any other sentence in the pitch.

**Complement, not competitor.** The composition metadata Preflight produces is exactly what the
Agent 365 registry's external-platform sync path ingests.

---

## 2. Data model

### 2.1 Collectors

Platform-neutral schema, pluggable collectors behind one interface, so a new platform is one
self-contained contribution.

| Platform | Read from | Distinctive signal | Phase |
|---|---|---|---|
| Foundry Agent Service | Foundry SDK: prompt and hosted agents, toolboxes, connections | toolbox pinning, MCP auth mode, A2A graph, content filters | **W1** |
| Copilot Studio | solution export and Dataverse: topics, knowledge, actions, channels, auth | auth mode, published channels, connector DLP posture, generative answers scope | **W1** |
| M365 declarative agents | `declarativeAgent.json` (schema 1.8) and the API plugin manifests it references | capabilities versus instructions, `discourage_model_knowledge`, disclaimer, OpenAPI surface, actions cap of 10 | stub |
| Microsoft Agent Framework | code-first: tools registered at build, OpenTelemetry semantics | tool registration surface, no declarative gate exists today | stub |
| Agent 365 / Entra Agent ID | registry roster, ownership, blueprints, OBO versus autonomous | orphaned agents, no sponsor, interactive versus autonomous mismatch | stub |

### 2.2 The AgentBOM

Every analyzer reads this and only this. Build it first.

| Field group | Contents |
|---|---|
| Identity | platform, agent id, Entra agent identity, blueprint, owner, sponsor |
| Model | deployments, region, catalog entry, context limits |
| Tools | tools, toolbox versions, MCP endpoints, API plugins, OpenAPI operations |
| Connections | auth mode per connection, scopes, secret references |
| Knowledge | sources, indexes, citation configuration, chunk profile |
| Storage | thread storage, memory, vector stores, retention |
| Residency | region for every deployment, connection, source and store |
| Graph | connected agents, A2A endpoints, delegation edges |
| Economics | instruction tokens, tool description tokens, grounding profile |

Properties that make it usable as evidence:

- **Transitive.** A toolbox wrapping an MCP server that reaches a third system is followed to the
  end, and so is a declarative agent whose plugin calls a Copilot Studio agent.
- **Signed and timestamped**, versioned, archivable.
- **Reproducible.** Identical inputs produce a byte-identical manifest and report.
- **Diffable**, across versions or dates, with a blast radius query: which agents does toolbox X v4
  change, and how.
- **Standards-aligned.** Extend CycloneDX ML-BOM or the SPDX 3.0 AI profile rather than inventing a
  format. See open questions.

### 2.3 Schema v0.1

The first commit. Every analyzer reads this and nothing else.

```json
{
  "bomFormat": "AgentBOM",
  "specVersion": "0.1",
  "serialNumber": "urn:uuid:...",
  "generated": "2026-09-14T08:00:00Z",
  "generator": { "tool": "preflight", "version": "0.1.0", "collector": "foundry@0.1.0" },
  "agent": {
    "id": "asst_...",
    "platform": "foundry | copilot-studio | m365-declarative | agent-framework",
    "name": "Contract triage",
    "environment": "sub/rg/project or env id",
    "identity": {
      "kind": "entra-agent | app-registration | shared | none",
      "objectId": "...", "appId": "...", "blueprint": "...",
      "mode": "obo | autonomous",
      "owner": "...", "sponsor": "..."
    },
    "instructions": { "hash": "sha256:...", "tokens": 1840, "capChars": 8000 }
  },
  "models": [
    { "deployment": "gpt-5-mini-global", "model": "gpt-5-mini", "version": "2025-08-07",
      "sku": "GlobalStandard", "region": "switzerlandnorth", "capacity": 50,
      "contextWindow": 272000, "status": "current | deprecated | retired" }
  ],
  "tools": [
    {
      "id": "mcp:contracts/delete_record",
      "kind": "mcp | openapi | builtin | connector | function | code-interpreter",
      "name": "delete_record",
      "descriptionTokens": 62,
      "source": { "server": "https://mcp.example.com", "manifestHash": "sha256:...",
                  "trusted": false, "toolbox": "contracts@v4", "pinned": true },
      "auth": { "mode": "key | managed-identity | obo | none", "scopes": ["..."],
                "secretRef": "kv://... | inline" },
      "annotations": { "readOnlyHint": false, "destructiveHint": true,
                       "idempotentHint": false, "openWorldHint": false },
      "classification": {
        "untrustedInput": false, "irreversibleAction": true,
        "source": "policy | registry | protocol | failclosed", "confidence": "high"
      }
    }
  ],
  "knowledge": [
    { "id": "...", "kind": "ai-search | sharepoint | files | fabric | bing",
      "region": "...", "citationsRequired": false, "chunkTokens": 800, "chunksPerTurn": 5 }
  ],
  "storage": [
    { "kind": "thread | memory | vector | logs", "resource": "...", "region": "...",
      "retentionDays": null, "sanitised": false }
  ],
  "guards": {
    "contentFilter": "default | custom | none", "promptShields": true,
    "humanInTheLoop": false, "tokenCap": null, "rateLimit": null,
    "maxTurns": null, "historySummarisation": false
  },
  "edges": [
    { "from": "asst_...", "to": "cs_agent_guid", "via": "http-action",
      "endpoint": "https://.../directline/...", "auth": "key",
      "crossPlatform": true, "crossRegion": false,
      "signal": "identity | endpoint | probe", "confidence": "proven | matched | probed" }
  ],
  "economics": {
    "instructionTokens": 1840, "toolDescriptionTokens": 940,
    "groundingTokensPerTurn": 4000, "fanoutFactor": 3.0,
    "estimatedCostPerInteraction": { "value": 0.031, "currency": "USD" }
  },
  "residency": { "declared": "CH | EU", "observed": ["switzerlandnorth", "westeurope"] },
  "tags": { "costCentre": null },
  "signature": { "alg": "...", "value": "..." }
}
```

Design notes that matter. `classification` and `edges[].confidence` are recorded per item, not
inferred at report time, so a finding can always be traced back to its evidence. `manifestHash` on
every MCP source is what makes rug-pull detection a diff rather than a guess. `null` means *absent
and therefore a finding*, distinct from a value of zero. And the whole document is canonicalised
before signing so that identical inputs produce an identical `serialNumber`-free hash.

---

## 3. Analyzers

Five analyzers, all reading the AgentBOM. The first four are deterministic. Nothing here calls a
model.

### 3.0 Tool classification

Everything downstream depends on one question: for a given tool, is it an **untrusted input**, an
**irreversible action**, both, or neither. This is the part a reviewer will push on, so it is
resolved by a layered model where every classification records its source and can be audited.

**Never by asking a model.** A gate must answer the same twice, and a model-classified tool makes
the finding non-reproducible.

| Tier | Source | Rule |
|---|---|---|
| 0 | **Policy override** | The organisation's policy file classifies a tool explicitly. Always wins |
| 1 | **First-party registry** | Curated table of Microsoft built-in tools. Finite and enumerable: Bing grounding, file search, code interpreter, browser automation, computer use, image generation, SharePoint, Fabric, Logic Apps, Azure Functions, Deep Research, OpenAPI, function calling |
| 2 | **Protocol-derived** | Read from the tool definition itself, deterministically. See below |
| 3 | **Unknown** | Fail closed: treat as **both** untrusted input and irreversible action, and raise a Low finding |

#### Tier 2a · MCP, via ToolAnnotations

MCP already defines the metadata this needs, so the classifier reads a protocol field rather than
guessing:

| Annotation | Meaning | Maps to |
|---|---|---|
| `openWorldHint: true` | tool may interact with an open world of external entities | **untrusted input** |
| `readOnlyHint: false` | tool modifies its environment (this is the **spec default**) | mutating |
| `destructiveHint: true` | may perform destructive updates rather than additive ones | **irreversible action** |
| `idempotentHint: true` | repeated calls have no additional effect | lowers severity, never clears it |

Two consequences worth being precise about.

The spec says clients **MUST consider tool annotations untrusted unless they come from a trusted
server**. So annotations are accepted as mitigating only from servers on the trusted list. From an
untrusted server they are recorded but can only ever make a classification worse, never better. A
hostile server cannot annotate its way past the gate.

And `readOnlyHint` defaults to **false**, so an unannotated MCP tool is already assumed to modify
its environment by the protocol's own default. The fail-closed tier is not a Preflight opinion, it
is the spec's.

#### Tier 2b · OpenAPI and API plugins

The HTTP method is the signal. `GET`, `HEAD`, `OPTIONS` are reads. `POST`, `PUT`, `PATCH` are
mutating. `DELETE` is irreversible. Any operation whose response body comes from an external host is
also an untrusted input. Rigorous, free, and it covers declarative agent actions and Foundry OpenAPI
tools in one rule.

#### Tier 2c · Copilot Studio

Power Platform connector operation metadata already carries read versus write classification per
operation. Reuse it rather than re-deriving.

#### Output

Every classification lands in the BOM as `{ classification, source, confidence }` and appears in
dossier appendix B, so a reviewer can audit why a path was flagged rather than taking it on trust.

**Rules this unlocks**

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| SC-05 | MCP tools fall to the fail-closed tier: they carry no annotations, or the server is not on the trusted list | Medium | ZT · communication governance | def |
| SC-06 | Annotations accepted from a server not on the trusted list | Medium | ZT · communication governance | def |
| TS-08 | Mutating OpenAPI operation reachable with no human gate | High | ZT · communication governance | def |

SC-05 also hands you a contribution: **the MCP servers catalogued in `microsoft/mcp` and
`Azure/azure-mcp` that ship no tool annotations.** Adding them is small, mergeable, makes
Microsoft's own catalog machine-auditable, and demonstrates the tool's value in the same pull
request.

### 3.0.5 Cross-platform edge resolution

The headline claim is that a path crosses platforms. That claim is only as good as the ability to
prove an edge exists between agent A on one platform and agent B on another, from definitions alone.
Three signals, strongest first, and every edge records which one produced it.

| Signal | Method | Confidence |
|---|---|---|
| **Identity** | The target's audience, resource id or app id matches an Entra agent identity already present in the estate's BOM set. Entra Agent ID spans Foundry and Copilot Studio, so this works across the boundary | **proven** |
| **Endpoint** | Normalise every outbound URL in every BOM into a canonical host and path key, index every inbound endpoint each agent publishes, and intersect | **matched** |
| **Probe** (opt-in) | For an endpoint that resolves to nothing known, fetch the A2A agent card at its well-known path, or send an MCP `initialize` and `tools/list`. If it answers as an agent, it is one | **probed** |

**Outbound surfaces to collect** so the index is complete: Foundry connected agents and A2A
endpoints, OpenAPI `servers[].url` on every tool and API plugin, MCP server URLs, Copilot Studio
HTTP actions and custom connector hosts, and Direct Line endpoints.

**The probe tier is opt-in and off by default.** It makes a network call, which breaks the no-traffic
promise. Leave it off in CI, turn it on for an estate review.

**Confidence gates severity, which is what keeps the demo honest.** A path is reported as
**critical** only when every edge on it is proven or matched. A path containing a probed or
suspected edge is reported one severity lower and labelled *possible path*. The tool never claims
certainty it has not earned.

An outbound endpoint that resolves to nothing at all is itself a finding. You cannot govern what you
cannot name.

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| MA-06 | Outbound endpoint resolves to an agent outside the governed estate | High | ZT · communication governance | def |
| MA-07 | Outbound endpoint unresolvable, target unknown | Medium | ZT · agent inventory and discovery | def |
| MA-08 | Cross-platform edge authenticated by key rather than by a shared Entra identity | High | ZT · agent identity and RBAC | def |

### 3.1 Attack path analysis · headline

Classify every tool as an **untrusted input** (web search, file upload, incoming mail, browser
automation, computer use, any MCP server you do not own) or an **irreversible action** (send, write,
delete, purchase, deploy, mutating external API). Compute reachability between the two across the
tool and A2A graph. A path with no human gate is critical, and the report prints the path.

The differentiator is that paths **cross platforms**: a declarative agent whose API plugin calls a
Copilot Studio agent whose action calls a Foundry agent with an unauthenticated MCP server. Each
platform's own tooling sees one hop and reports it clean.

Nearly free once the BOM exists. It is graph reachability over data already collected.

Two modelling rules, implemented in `analyze/paths.py`. A tool whose call resolves to another agent in
the estate is an **edge**, followed transitively, not a sink; only an irreversible tool acting outside
the estate is a sink. And severity needs evidence at both ends: **Critical** requires every edge
proven or matched **and** the sink's irreversibility declared rather than assumed. A sink that is
irreversible only because the classifier failed closed produces a **High**, labelled possible path.

### 3.2 Effective privilege closure

Real privilege is the union of the agent's own identity, every on-behalf-of passthrough, and the
permissions of every downstream agent it can reach, across platform boundaries. Report the effective
set, not the declared one. Flag escalation through delegation, where A cannot read X but can ask B,
which can. Diff the closure between versions so "this change granted Mail.Send transitively" appears
in the pull request.

### 3.3 Cost analysis

Priced from the definition, so no traffic is needed.

| Driver | What it computes |
|---|---|
| Prompt tax | Instructions are charged every turn. Count, price, and show the cost of the system prompt alone per thousand conversations. Declarative agents cap instructions at 8,000 characters and most sit near it unpriced |
| Tool surface tax | Every tool description sits in the context window every turn. Tool count times description length is a fixed per-turn cost. **Same evidence as the over-broad tool surface rule, so one finding is both a security and a cost finding** |
| Grounding | Retrieved chunks per turn times chunk size, per knowledge source |
| Fan-out | Connected agents and A2A hops multiply turns. Worst-case token amplification across the delegation graph. A cycle is unbounded |

Then: right-size the model against the catalog, check the runaway guards exist (token cap, rate
limit, max turns, history summarisation), price storage and retention, verify cost-centre tags, and
forecast monthly spend at a declared volume.

**Cost as a gate.** A budget threshold breach fails the build, and the cost delta is posted on the
pull request the way a bundle-size check is: "this change adds 34% per interaction".

### 3.4 Rule engine

Deterministic, so the gate answers the same twice, and because CAF's own cost guidance says to route
deterministic work to rules rather than premium models. Every rule carries an ID, a severity and a
control reference. Catalog in section 4.

### 3.5 Supply chain integrity

- **MCP rug-pull detection.** Pin a hash of each remote MCP server's tool manifest at approval time,
  re-fetch on every run, alert when descriptions, schemas or the tool list change after approval.
- Toolbox version drift: what changed, and which agents it hits.
- Provenance for every knowledge source and model deployment: owner, last change.
- Injection payload scanning across tool descriptions, MCP metadata, API plugin manifests and
  knowledge source descriptions.

---

## 4. Rule catalog

**Severity model**

| Severity | Meaning | Default |
|---|---|---|
| Critical | An exploitable path, or an unauthenticated surface | Fails the build |
| High | A control absent where the platform offers one | Fails the build |
| Medium | Weaker than the declared policy | Warns |
| Low | Hygiene, cost and documentation gaps | Informational |

**Needs** column: `def` readable from the agent definition alone (week one), `cat` needs the model
catalog, `pol` needs the policy file, `reg` needs the registry, `tel` needs telemetry.

### Attack paths (AP)

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| AP-01 | Untrusted input reaches an irreversible action with no human gate | Critical | ZT · communication governance | def |
| AP-02 | The path crosses a platform boundary | Critical | ZT · communication governance | def |
| AP-03 | The path crosses a residency or tenant boundary | Critical | CAF · data residency | def |
| AP-04 | Reachable irreversible action with no confirmation step declared | High | ZT · communication governance | def |
| AP-05 | Untrusted input feeds a knowledge store that other agents read | High | ZT · memory and retrieval hygiene | def |

### Identity and authentication (ID)

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| ID-01 | Anonymous or unauthenticated execution mode on any tool or MCP connection | Critical | ZT · agent identity and RBAC | def |
| ID-02 | Shared credential, or no unique Entra agent identity | Critical | ZT · agent identity and RBAC | def |
| ID-03 | Secret inline in a connection rather than a Key Vault reference | Critical | ZT · agent identity and RBAC | def |
| ID-04 | Key-based auth where managed identity or OBO was available | High | ZT · agent identity and RBAC | def |
| ID-05 | OBO scope wider than the declared purpose | High | ZT · agent identity and RBAC | def |
| ID-06 | Autonomous where the workload implies OBO, or the reverse | Medium | CAF · agent registry | def |
| ID-07 | No accountable owner or sponsor | Medium | CAF · accountability | reg |
| ID-08 | Effective privilege exceeds declared privilege | High | ZT · agent identity and RBAC | def |

### Tool surface (TS)

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| TS-01 | MCP endpoint attached without a tool allowlist | High | ZT · communication governance | def |
| TS-02 | Tool count far beyond what the instructions reference | Medium | ZT · agent identity and RBAC | def |
| TS-03 | Tools granted at agent level that are only needed at thread or run level | Medium | ZT · agent identity and RBAC | def |
| TS-04 | Toolbox floating on default rather than pinned to a version | High | CAF · standardise protocols | def |
| TS-05 | Duplicate or shadowed tools across toolboxes | Low | CAF · standardise protocols | def |
| TS-06 | Declarative agent capability granted but never referenced in instructions | Medium | ZT · agent identity and RBAC | def |
| TS-07 | OpenAPI operations exposed beyond what the agent needs | Medium | ZT · agent identity and RBAC | def |

TS-02 is justified by embedding similarity between instructions and tool descriptions, which keeps
the check reproducible rather than handing the judgment to a model.

### Multi-agent and A2A (MA)

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| MA-01 | A2A endpoint without an allowlist | Critical | ZT · communication governance | def |
| MA-02 | Recursive or cyclic delegation path | High | ZT · communication governance | def |
| MA-03 | Downstream agent in a different tenant or subscription | High | CAF · data residency | def |
| MA-04 | Downstream agent in a different residency region | High | CAF · data residency | def |
| MA-05 | Delegation to an agent absent from the registry | Medium | ZT · agent inventory and discovery | reg |

### Data, residency and retention (DR)

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| DR-01 | A deployment, connection, source or store outside the declared residency policy | Critical | CAF · data residency | pol |
| DR-02 | Knowledge source reaching data outside the declared scope | High | CAF · data privacy | def |
| DR-03 | No retention policy on logs or threads | Medium | CAF · data retention | def |
| DR-04 | Bring-your-own thread storage absent where the workload requires it | Medium | CAF · data privacy | def |
| DR-05 | Memory or vector store with no sanitisation declared | High | ZT · memory and retrieval hygiene | def |

### Responsible AI (RA)

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| RA-01 | Content filter absent | Critical | CAF · prepare environment | def |
| RA-02 | Content filter weaker than the project default | High | CAF · prepare environment | def |
| RA-03 | Prompt shields or jailbreak filters disabled | Critical | CAF · prepare environment | def |
| RA-04 | Grounding configured with no citation requirement in the instructions | Medium | CAF · data privacy | def |
| RA-05 | No human-in-the-loop declared for an irreversible action | High | ZT · communication governance | def |
| RA-06 | Instructions with no refusal or escalation path | Medium | CAF · prepare environment | def |
| RA-07 | Declarative agent with no disclaimer | Low | CAF · prepare environment | def |
| RA-08 | `discourage_model_knowledge` unset where grounding is the agent's whole purpose | Low | CAF · prepare environment | def |

### Model and lifecycle (ML)

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| ML-01 | Model pinned to a deprecated or retired deployment | High | CAF · govern AI models | cat |
| ML-02 | Model unavailable in the target region | High | CAF · govern AI models | cat |
| ML-03 | Model not permitted by Azure Policy model restrictions | High | CAF · govern AI models | pol |
| ML-04 | Dormant agent: registered, deployed, no traffic | Low | CAF · lifecycle management | tel |
| ML-05 | No recertification within the policy window | Medium | ZT · lifecycle management | reg |

### Supply chain (SC)

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| SC-01 | Remote MCP tool manifest changed since approval | Critical | ZT · communication governance | def |
| SC-02 | Injection payload in a tool description, plugin manifest or source description | Critical | ZT · memory and retrieval hygiene | def |
| SC-03 | Toolbox version bumped since the last certified BOM | Medium | CAF · standardise protocols | def |
| SC-04 | Knowledge source or model deployment with no known owner | Low | CAF · accountability | reg |

### Cost (CO)

| ID | Rule | Sev | Control | Needs |
|---|---|---|---|---|
| CO-01 | Forecast monthly spend exceeds the declared budget threshold | High | CAF · track and allocate costs | pol |
| CO-02 | Cost per interaction regressed beyond the allowed delta | High | CAF · track and allocate costs | pol |
| CO-03 | No token cap, rate limit or max-turn limit | High | CAF · track and allocate costs | def |
| CO-04 | Premium model used for deterministic work | Medium | CAF · systematize cost optimization | cat |
| CO-05 | A cheaper catalog model meets the declared capability needs | Low | CAF · systematize cost optimization | cat |
| CO-06 | Instructions near the character cap and unpriced | Low | CAF · track and allocate costs | def |
| CO-07 | Tool surface tax above threshold for the turn budget | Medium | CAF · track and allocate costs | def |
| CO-08 | No cost-centre tag per agent or use case | Medium | CAF · track and allocate costs | def |
| CO-09 | No conversation history summarisation on a long-running agent | Low | CAF · systematize cost optimization | def |

**Week one is every `def` rule**, which is most of the catalog. `cat`, `pol`, `reg` and `tel` rules
each need a data source outside the agent definition and are the ones most likely to slip. Plan for
that rather than discovering it on Thursday.

---

## 5. Policy as code

The tool ships defaults; the organisation enforces its own. A versioned policy file supplies allowed
regions, allowed models, required auth modes, banned tool combinations, mandatory human gates,
budget thresholds and the allowed cost delta. Every `pol` rule reads from it.

Policy packs: Swiss and EU residency, financial services, public sector.

---

## 6. Outputs

### 6.1 SARIF
Ingested natively by GitHub code scanning, so findings land in the pull request beside the BOM diff
and the cost delta. Rule IDs from section 4 become SARIF rule ids.

### 6.2 Governance dossier

Renders a **versioned template**. Every field traces to a BOM field or a rule result. Anything that
cannot be derived prints **requires human input** rather than being invented, so the tool never
manufactures a control claim it cannot evidence.

| # | Section | Source |
|---|---|---|
| 1 | Identification | agent id, platform, owner and sponsor, BOM hash, certification status, version, date |
| 2 | Purpose and intended use | description and instructions |
| 3 | Out of scope and prohibited uses | policy file plus human input |
| 4 | Architecture and trust graph | rendered SVG, composition table |
| 5 | Composition inventory | the AgentBOM |
| 6 | Identity and permissions | declared set, effective closure, OBO versus autonomous, sponsor |
| 7 | Data, residency and retention | sources, regions, classification, memory and vector stores |
| 8 | Attack surface analysis | untrusted inputs, irreversible actions, ranked paths, human gates |
| 9 | Responsible AI | filters, prompt shields, citation policy, human oversight, limitations, disclaimer |
| 10 | Cost and capacity | per-interaction estimate, drivers, guards, allocation tags, forecast |
| 11 | Findings and remediation | findings by severity, accepted baseline with justification and expiry |
| 12 | Change log and certification | BOM diff against the last certified version, hash, sign-off, expiry |
| A | Control mapping matrix | every rule id to its CAF or Zero Trust control |
| B | Full rule results | complete pass and fail list |

Section 9 mirrors the shape of Microsoft's own Transparency Note for Foundry Agent Service, so the
output is recognisable to anyone who has read one.

Template packs: **Microsoft RAI** (default), **EU AI Act technical documentation** (reordered to the
annex structure), **internal deployment review** (short form, findings and sign-off only). Templates
are files, so an organisation swaps in its own without touching the tool.

### 6.3 Certification record
Certifies a BOM hash, so the certificate names exactly what was reviewed. Any composition change
voids it, which means an approval from March cannot silently cover an agent rebuilt in September.
This is the artifact CAF's recertification requirement asks for and that has nowhere to live today.

### 6.4 AgentBOM manifest
Signed, for archival and for the Agent 365 registry sync path.

---

## 7. Delivery surfaces

- CLI, read-only, one collector per platform
- GitHub Action gating a pull request, posting the BOM diff and cost delta as comments
- Azure DevOps task
- Baseline file, so existing findings can be accepted with a justification and an expiry, and only
  new ones break the build

---

## 8. Judgment layer

A review board of specialist agents built with connected agents in Foundry: security, cost,
accessibility, residency. Each reads the same AgentBOM. An orchestrator merges and de-duplicates and
**may not contradict a deterministic finding**. The board handles only what no rule can decide, and
drafts the prose sections of the dossier for a human to confirm.

It is in the design for two reasons beyond capability. One specialist agent, or one platform
collector, is a self-contained day for anyone who joins, and a CLI is not joinable. And auditing
Foundry agents with Foundry agents surfaces friction worth writing up.

---

## 9. Roadmap, not week one

- **What-if.** Simulate a change before making it: add this tool, switch this model, connect this
  agent, and see the new findings, paths and cost.
- **Auto-remediation.** Generate the fix as a pull request against the agent's infrastructure
  definition. Suggest the narrowest tool set that still satisfies the instructions.
- **Estate intelligence.** Run across a tenant or subscription and answer questions over the
  collected BOMs: which agents reach customer data, which share this toolbox, which break if this
  MCP server disappears, which have no owner, which cost most per conversation.
- **Trust graph visualisation** with residency boundaries drawn and attack paths highlighted.

---

## 10. Non-goals

- Not a runtime evaluator. Foundry ships evaluators, continuous evaluation and the AI Red Teaming
  Agent
- Not a competitor to the Agent 365 registry or Entra Agent ID. It runs before registration and
  feeds them
- No writes to the agent. Read-only, always
- Never invents a governance claim. Underivable fields are marked as requiring human input

---

## 11. Microsoft repos to anchor to

Verified 2026-09-02 that each repo exists, is active and contains what is claimed. Contribution
guidelines and maintainer appetite are **not** verified.

| Repo | Stars | Why it matters |
|---|---|---|
| `Azure/PSRule.Rules.Azure` | 447 | The precedent. Design-time IaC validation with SARIF output, one layer down. Lead with it |
| `Azure/review-checklists` | 1,334 | Microsoft's own best-practice checklists in JSON with a review process. **Recommended contribution target**: the control mappings as an AI agents checklist |
| `microsoft/agent-framework` | 13,294 | Code-first collector's counterpart. Cleanest contribution is a tool-registration exporter, which the collector needs anyway |
| `microsoft/mcp` | 3,638 | Catalog of official Microsoft MCP servers. Natural home for manifest-hash pinning |
| `Azure/azure-mcp` | 1,223 | Same, for the Azure MCP server |
| `microsoft/Agents` | 1,054 | M365 Agent SDK, the equivalent surface |
| `Azure-Samples/azureai-samples` | - | A sample is the easiest possible merge |
| `Azure/AI-Landing-Zones`, `Azure/azure-policy` | - | Secondary, for the policy packs |

**Do not** try to land the tool itself in a Microsoft repo during hack week. Maintainers, CLA and
review cycles will not clear in five days. Own repo for the tool, one small deliberate contribution
elsewhere.

Somebody will ask why this is not simply a PSRule module. Building it as one would inherit the
engine, SARIF output, CI integrations and docs for free, at the cost of PowerShell. Use PSRule as
the precedent regardless; adopt it as the engine only if that cost is acceptable.

---

## 12. The demo

Everything else is preparation for three minutes. Build the fixtures first, on day one, because
they define what the tool has to detect.

### 12.1 Fixture set

Three agents, each individually plausible and individually approvable. Nothing is obviously wrong
with any of them in isolation. That is the entire point.

| # | Agent | Platform | What is wrong with it, on its own |
|---|---|---|---|
| 1 | **Inbox triage** | M365 declarative | Has `WebSearch` capability plus an API plugin action. Reasonable. The plugin is a `POST` to an internal endpoint |
| 2 | **Contract router** | Copilot Studio | Published agent with an HTTP action calling an internal service, authenticated by key. Reasonable |
| 3 | **Records agent** | Foundry | A toolbox with an MCP server carrying `destructiveHint: true`, connected with key auth, no allowlist, no human gate. Reviewed and signed off six weeks ago |

The composed defect nobody reviewed: agent 1's plugin endpoint is agent 2's Direct Line endpoint,
and agent 2's HTTP action is agent 3's project endpoint. Untrusted web content reaches a destructive
tool through three agents and two platform boundaries.

Build these in the MVP tenant: 2 and 3 as real agents on Copilot Studio Sandbox and the Foundry
project, 1 as a `declarativeAgent.json` on disk, which needs no licence.

### 12.2 The three minutes

| Time | Beat |
|---|---|
| 0:00 | Three agents, three platforms, all approved separately. Show the definitions. Nothing looks wrong |
| 0:30 | `preflight scan --estate ./fixtures`. Deterministic, no traffic, no tokens, two seconds |
| 0:45 | **One CRITICAL.** Print the path: `web content → [1] declarative agent → POST plugin → [2] Copilot Studio agent → HTTP action → [3] Foundry agent → MCP delete_record (destructiveHint: true)`. No human gate anywhere on it |
| 1:15 | Show why each edge is trusted: identity match, endpoint match, and the annotation the MCP server itself declared. Not a guess, evidence |
| 1:30 | **The money moment.** Open each platform's own tooling in turn. Each sees one hop. Each reports clean. The defect exists only in the composition, and composition is what nothing inventories |
| 2:00 | The rest, fast: privilege closure showing `Mail.Send` reachable transitively, cost delta at plus 34 percent, SARIF landing in the pull request |
| 2:30 | The dossier, generated, with the trust graph and the control mapping matrix |
| 2:50 | It ran before any of these was registered, and it feeds Agent 365 rather than competing with it |

### 12.3 What makes it land

One finding no existing tool can produce, shown in ninety seconds, on a defect the audience agrees
was individually approvable. Resist adding a second finding to the demo. Breadth is what the
capability list is for.

## 13. Build order

1. **AgentBOM schema and the collector interface**, platform-neutral from the first commit
2. **Foundry and Copilot Studio collectors**
3. **Attack path analysis**, nearly free once the BOM exists, and it is the demo
4. **Rule engine** with the `def` rules from AP, ID, TS and MA
5. **Cost model**, prompt tax and tool surface tax first, since they share evidence with TS-02
6. **SARIF output and the GitHub Action**, with the cost delta comment
7. **Dossier renderer** against the template
8. **Privilege closure, supply chain pinning, policy as code, certification**, each small and
   independent, good pieces to hand to anyone who joins
9. **Declarative agent and Agent Framework collectors, review board, estate intelligence**, only if
   the week allows

---

## 14. Open questions

- Which bill-of-materials standard to extend. CycloneDX carries an ML-BOM component type and SPDX
  3.0 added an AI profile. Both have moved recently. **Verify before committing in writing.**
- Exact CAF and Zero Trust section numbers for the control column. Controls are cited by name here
  because the numbering differs across doc versions. Confirm against the live docs before the
  mapping matrix ships.
- Whether to build on PSRule or standalone.
- Contribution guidelines for every repo in section 11.
