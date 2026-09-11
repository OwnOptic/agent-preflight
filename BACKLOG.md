# Backlog

Last updated: 2026-09-11, audited against the working tree, the tenant and the mailbox rather than
against the plan.

**Three days to the hackathon.** Official hacking is Mon 14 to Wed 16 Sep. The only deliverable is a
video of two minutes or less, due **Mon 21 Sep 23:59 Pacific** (Tue 08:59 in Lausanne, so treat
Monday evening as the deadline). See [docs/PLAN.md](docs/PLAN.md).

## Where it actually stands

| Done | Evidence |
|---|---|
| AgentBOM schema v0.1 | `schema/agentbom-0.1.json` |
| Pydantic models, drift-guarded against the schema | `src/preflight/bom/models.py`, schema test |
| Canonical serialisation, deterministic identity | `src/preflight/bom/canonical.py`, serial derived from the composition hash |
| Collector interface and registry | `src/preflight/collectors/base.py` |
| Tool classifier, four tiers | `src/preflight/classify/classifier.py` |
| First-party tool registry | `src/preflight/classify/registry.py`, 18 entries |
| M365 declarative collector | `src/preflight/collectors/m365_declarative.py` |
| CLI, `collect` and `scan` | `src/preflight/cli.py` |
| Three fixtures, chain verified on disk | `fixtures/`, expected result in `fixtures/CHAIN.md` |
| Foundry project in the MVP tenant | `preflight` on `fdy-demo-agents-de-em`, switzerlandnorth |
| **16 tests passing** | |

### Which fixtures exist where

| Fixture | On disk | In its platform |
|---|---|---|
| 01 Inbox triage, M365 declarative | yes | **no**, never sideloaded |
| 02 Contract router, Copilot Studio | yes, hand-authored stand-in | **no**, never built in Copilot Studio |
| 03 Records agent, Foundry | yes | **yes**, `asst_Y3XUjyknLU4ZzR732qhPDe7F` with MCP tool `records` |

The analyzer only needs the files, so this does not block the build. It **does block the video**: the
1:30 beat opens each platform's own tooling and shows each reports clean, which needs all three to
exist where the platform can see them.

## P0 - before Monday 14

- [ ] **Publish the Innovation Studio project page.** A Description is an eligibility requirement and
      submissions are machine-routed by expertise before a human reads them. Everything is drafted.
- [ ] **Echo the challenge wording in the Description's opening.** The challenge reads "Build
      capabilities, experiences, tools, or infrastructure that make AI agents more trustworthy". A
      first sentence using "tools that make AI agents more trustworthy" helps the classifier route it
      to the right reviewers.
- [ ] Disclose AI-assisted authoring on the project page, naming the tools. The event asks for it.
- [ ] **Deploy fixture 01 before Teams Exploratory expires on 14 Sep.** The base licence is E5 EEA with
      no Teams, so after Monday a declarative agent cannot be shown in Teams at all. If it must appear
      in the video, it has to be sideloaded and captured this weekend. Otherwise decide now that the
      video shows it as files.
- [ ] **Build fixture 02 in Copilot Studio** (Sandbox environment, credits already assigned), then
      export the unmanaged solution and replace the stand-in in `fixtures/02-contract-router/`. The
      collector must produce the same BOM from the real export.
- [ ] `policy.example.yaml` loading into `Policy`, fixture MCP server deliberately absent from
      `trusted_mcp_servers` so the classifier fails closed on it
- [x] Azure credit checked: CHF 130 remaining, CHF 0.23 spent this cycle. The `mvp-billing-guard`
      budget was reset from 150 to CHF 130 on 2026-09-11, so every alert fires before the spending
      limit blocks the subscription. Spend is readable from the budget API (`currentSpend`) even
      though the consumption API returns `pretaxCost: None` for this offer

## P1 - Monday 14, first BOM

- [x] `collectors/m365_declarative.py`: manifest, API plugins and their OpenAPI documents, one `Tool`
      per operation with `httpMethod` set
- [x] Classifier wired in, every tool lands with a `classification` and a `source`
- [x] `cli.py`: `preflight collect` and `preflight scan`
- [x] Test validating a generated BOM against the schema

Monday is therefore free for Tuesday's work. Pull it forward.

## P1 - Tuesday 15, three platforms

- [ ] `collectors/copilot_studio.py` reading the fixture 02 export
- [ ] `collectors/foundry.py` via `azure-ai-projects` against the live project, reading the MCP tool
      manifest so annotations reach the classifier
- [ ] Register both in `cli.COLLECTORS` so `preflight scan fixtures` returns three BOMs

*Cut if short: Foundry from a saved API response rather than live. The BOM is what matters.*

## P0 - Wednesday 16, the demo

**No cut line. Without this there is no video.**

- [ ] `resolve/edges.py`: index published inbound endpoints, normalise outbound URLs, intersect.
      Identity match first, endpoint match second. No probe
- [ ] `analyze/paths.py`: reachability from untrusted-input sources to irreversible-action sinks,
      dropping any path crossing a declared human gate
- [ ] Severity gating: Critical only when every edge is proven or matched
- [ ] Print the path as a readable chain, not JSON
- [ ] Test asserting the result equals `fixtures/CHAIN.md`

## P2 - if Wednesday allows

- [ ] `rules/` with the `def` rules from AP, ID, TS and MA, each returning id, severity and control
- [ ] Assert the secondary findings listed in `fixtures/CHAIN.md`, which is a ready-made test set
- [ ] `report/sarif.py`, SARIF 2.1.0
- [ ] `.github/workflows/preflight.yml` uploading SARIF via `github/codeql-action/upload-sarif`
- [ ] Baseline file so accepted findings do not fail the build

## During the week

- [ ] Respond to join requests in Innovation Studio. Collaborators are the reason the repo is public
- [ ] Attend the Garage Talk "MCP Debugger: From Hackathon Project to 10K Users". Closest precedent to
      the outcome worth wanting

## P0 - Thursday 17 to Monday 21, the video

- [ ] **Capture each platform's own view reporting clean** for the 1:30 beat: the Foundry portal on
      `records-agent`, Copilot Studio on the contract router, and the declarative agent where it runs.
      Capture while all three exist
- [ ] Record the two-minute video to the beat sheet in `docs/PLAN.md`. Screen capture plus
      voiceover, captions burned in. Rehearse, do not narrate live
- [ ] Every rubric category visible: Inspiration, Business Value, Customer Focus, Feasibility, Make
      Something. Implicit means unscored
- [ ] Upload well before the deadline

## Blocked

- [ ] **`collectors/agent365.py`** needs Microsoft E7 or the Agent 365 add-on; the MVP tenant is E5
      EEA. The request sent to `mvpga@microsoft.com` on 3 Sep got an **auto-reply only**: that mailbox
      is unmonitored. The real route is `mvpsupport@microsoft.com`, **sent from the address on the MVP
      profile**. An answer is unlikely before the week, so the stub stays as the recruiting hook.
      Decide whether to re-send for after the hackathon.

## P3 - roadmap, not this week

- [ ] Effective privilege closure
- [ ] Cost model: prompt tax and tool surface tax first, they share evidence with TS-02
- [ ] Dossier renderer against the v1.0 template
- [ ] Supply chain: MCP manifest hash pinning, toolbox drift
- [ ] Continuous certification tied to the composition hash
- [ ] `collectors/agent_framework.py`
- [ ] Review board of specialist agents

## After the hackathon

- [ ] **Upstream contribution**: add `ToolAnnotations` to the MCP servers in `microsoft/mcp` and
      `Azure/azure-mcp` that ship none. Small, mergeable, and proves the tool in the same PR. Check
      contribution guidelines first
- [ ] The e-margot.ch project page, parked 3 Sep over the IP clause. Revisit once the agreement is
      checked
- [ ] README "Status" line still says implementation is starting

## Open questions

- [ ] Which bill-of-materials standard to extend, CycloneDX ML-BOM or the SPDX 3.0 AI profile.
      **Verify before claiming either in writing**
- [ ] Exact CAF and Zero Trust section numbers for the control column, cited by name for now
- [ ] Build on PSRule, or stay standalone
- [ ] Diagram palette: `docs/architecture.svg` uses the personal orange and navy, while the standing
      diagram rule names the magenta brand palette. Settle which applies to a personal public project

## Known traps

- **The az default context keeps reverting to a client landing zone** (`sub-iasp-lz-APIXNP`, tenant
  `329e91b0`). A token minted there hits the MVP Foundry endpoint as a 401 reading "invalid
  subscription key or wrong API endpoint", which looks like a Foundry fault and is not. Always pass
  `--subscription 9049e88f-118a-4bd0-ac6b-d8fb1201262e` when minting tokens or touching resources
- Teams Exploratory expires 14 Sep and nothing underneath provides Teams
- Personal Edge must not hold the Playwright profile lock. Kill only processes whose command line
  contains `playwright-edge`
- `az role assignment create` fails on this machine with `MissingSubscription`; use a direct ARM PUT
- `Azure AI Developer` does not grant `AIServices/agents`; `Cognitive Services User` does
- The Foundry v1 API rejects `require_approval` on MCP tools: there is no tool-level approval gate
- Innovation Studio content is Microsoft Confidential. None of it goes into this public repo, the
  website, or a post
