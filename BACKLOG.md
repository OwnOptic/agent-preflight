# Backlog

Last updated: 2026-09-09, audited against the working tree rather than against the plan.

**Five days to the hackathon.** Official hacking is Mon 14 to Wed 16 Sep. The only deliverable is a
video of two minutes or less, due **Mon 21 Sep 23:59 Pacific** (Tue 08:59 in Lausanne, so treat
Monday evening as the deadline). See [docs/PLAN.md](docs/PLAN.md).

## Where it actually stands

| Done | Evidence |
|---|---|
| AgentBOM schema v0.1 | `schema/agentbom-0.1.json` |
| Pydantic models mirroring it | `src/preflight/bom/models.py` |
| Collector interface and registry | `src/preflight/collectors/base.py` |
| Tool classifier, four tiers | `src/preflight/classify/classifier.py`, 9 tests passing |
| First-party tool registry | `src/preflight/classify/registry.py`, 12 entries |
| Policy model | `src/preflight/policy.py` |
| Three fixtures, chain verified | `fixtures/`, expected result in `fixtures/CHAIN.md` |
| Foundry project in the MVP tenant | `preflight` on `fdy-demo-agents-de-em`, switzerlandnorth |
| Live fixture agent with MCP tool | `asst_Y3XUjyknLU4ZzR732qhPDe7F`, `allowed_tools: null` |

**Nothing runs end to end.** There is no CLI, and all five collectors raise `NotImplementedError`.

## P0 - before Monday 14

- [ ] **Publish the Innovation Studio project page.** A Description is an eligibility requirement and
      submissions are machine-routed by expertise before a human reads them. Title, tagline,
      description, Executive Challenge and five Topic Challenges are all drafted and ready to paste.
      Editable afterwards. **This is the highest value item in the file and it costs ten minutes.**
- [ ] Disclose AI-assisted authoring on the project page, naming the tools. The event asks for it.
- [ ] `policy.example.yaml` that loads into `Policy`, with the fixture MCP server deliberately
      absent from `trusted_mcp_servers` so the classifier fails closed on it
- [ ] Check the remaining Azure credit in the portal. The consumption API returns `pretaxCost: None`
      for this offer, so it cannot be read from the CLI

## P1 - Monday 14, first BOM

- [ ] `collectors/m365_declarative.py`: parse `declarativeAgent.json`, follow the API plugin
      manifests and their OpenAPI documents, emit one `Tool` per operation with `httpMethod` set.
      Files on disk, no licence, no tenant, so the whole pipeline runs on day one
- [ ] Wire the classifier in so every tool lands with a `classification` and a `source`
- [ ] `cli.py`: `preflight collect <path>` printing canonical JSON
- [ ] Test validating a generated BOM against `schema/agentbom-0.1.json`, so models and schema cannot
      drift silently

*Cut if short: skip OpenAPI following, treat the plugin as one opaque tool.*

## P1 - Tuesday 15, three platforms

- [ ] `collectors/copilot_studio.py` reading `fixtures/02-contract-router/`
- [ ] `collectors/foundry.py` via `azure-ai-projects` against the live project
- [ ] `preflight scan <dir>` running every available collector, one BOM per agent

*Cut if short: Foundry from a saved API response rather than live. The BOM is what matters.*

## P0 - Wednesday 16, the demo

**No cut line. Without this there is no video.**

- [ ] `resolve/edges.py`: index published inbound endpoints, normalise outbound URLs, intersect.
      Identity match first, endpoint match second. No probe
- [ ] `analyze/paths.py`: graph reachability from untrusted-input sources to irreversible-action
      sinks, dropping any path crossing a declared human gate
- [ ] Severity gating: Critical only when every edge is proven or matched
- [ ] Print the path as a readable chain, not JSON
- [ ] Assert the result against `fixtures/CHAIN.md`

## P2 - if Wednesday allows

- [ ] `rules/` with the `def` rules from AP, ID, TS and MA. One module per domain, one function per
      rule, each returning id, severity and control reference
- [ ] `report/sarif.py`, SARIF 2.1.0, rule ids from the catalog become SARIF rule ids
- [ ] `.github/workflows/preflight.yml` uploading SARIF via `github/codeql-action/upload-sarif`
- [ ] Baseline file so existing findings can be accepted and only new ones fail the build

## P0 - Thursday 17 to Monday 21, the video

- [ ] Record the two-minute video to the beat sheet in `docs/PLAN.md`. Rehearse, do not narrate live
- [ ] Every rubric category must be visible: Inspiration, Business Value, Customer Focus,
      Feasibility, Make Something. Implicit means unscored
- [ ] Upload well before the deadline

## P3 - roadmap, not this week

- [ ] Effective privilege closure
- [ ] Cost model: prompt tax and tool surface tax first, they share evidence with TS-02
- [ ] Dossier renderer against the v1.0 template
- [ ] Supply chain: MCP manifest hash pinning, toolbox drift
- [ ] Continuous certification tied to the BOM hash
- [ ] `collectors/agent_framework.py`
- [ ] Review board of specialist agents

## Blocked

- [ ] `collectors/agent365.py` - needs Microsoft E7 or the Agent 365 add-on. The MVP tenant is
      E5 EEA, so this cannot be built or tested here. Interface is stubbed and documented; an
      internal contributor can finish it. This is deliberately named in the project description as a
      recruiting hook

## Open questions

- [ ] Which bill-of-materials standard to extend. CycloneDX ML-BOM or the SPDX 3.0 AI profile. Both
      have moved recently, **verify before claiming either in writing**
- [ ] Exact CAF and Zero Trust section numbers for the control column. Cited by name for now because
      numbering differs across doc versions
- [ ] Whether to build on PSRule rather than standalone
- [ ] Contribution guidelines for the repos named in `docs/capabilities.md`

## Known traps

- Personal Edge must not hold the Playwright profile lock. Kill only processes whose command line
  contains `playwright-edge`
- `az role assignment create` fails on this machine with `MissingSubscription`; use a direct ARM PUT
- `Azure AI Developer` does not grant `AIServices/agents`; `Cognitive Services User` does
- Innovation Studio content is Microsoft Confidential. None of it goes into this public repo, the
  website, or a post
