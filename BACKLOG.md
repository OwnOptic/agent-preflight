# Backlog

Last updated: 2026-09-11, audited against the working tree and the tenant. Event-specific items live
in `docs/PLAN.private.md`, which is not in git.

## Where it stands

**The analysis engine is built.** 45 tests pass, including in a clean virtualenv installed the way
CI installs it. `preflight scan fixtures` produces exactly the 21 findings in `fixtures/CHAIN.md`,
and a live scan of the real Foundry project reproduces the same critical path.

### Which fixtures exist where

| Fixture | On disk | In its platform |
|---|---|---|
| 01 Inbox triage, M365 declarative | yes | **yes**, uploaded to the org app catalog from `dist/fixture-01-inbox-triage.zip` |
| 02 Contract router, Copilot Studio | yes, a real unmanaged solution export | **yes**, `apf_contractRouter` in the Sandbox environment, **not yet published** |
| 03 Records agent, Foundry | yes | **yes**, `asst_Y3XUjyknLU4ZzR732qhPDe7F` with MCP tool `records` |

## Next

- [x] **Sideload fixture 01**: `python scripts/package_fixture01.py` builds the package from a copy
      (adds icons and real developer URLs; the fixture and baseline are untouched), uploaded 2026-09-11.
      Capturing it running in Copilot is part of the item below
- [x] **Build fixture 02 in Copilot Studio**: built through the Dataverse API (`PvaProvision`, topic
      YAML), exported, and the collector now reads the real export. The chain reproduces unchanged.
      One finding fewer (18): RA-04 came from a field the stand-in invented; Copilot Studio has no
      forced-citations setting. `scripts/export_fixture02.py` refreshes the export
- [ ] **Decide whether to publish fixture 02.** Unpublished, ID-01 reads "once published". Publishing
      makes an unauthenticated agent reachable; its HTTP call carries a placeholder key, so it cannot
      reach Foundry
- [ ] **Capture each platform's own view** of its agent, for the demo
- [ ] **Demo pull request**: a branch adding a destructive tool or rewriting the MCP manifest, so CI
      fails with the finding on the diff. Leave it unmerged
- [ ] Record the demo
- [ ] Complete the project page (checklist in the private plan)

## What "fully functional" still needs

Audited 2026-09-12 against the working tree, not against intentions. Three tiers, because they are
three different finish lines.

### A. Demo complete (the hackathon)

Everything analytical is built. What remains is evidence, not engine.

| Gap | Size |
|---|---|
| Publish fixture 02, or accept that ID-01 reads "once published" | a decision |
| Capture each platform's own view of its agent | an hour |
| Demo pull request that fails CI on the diff | an hour |
| The video, and the project page | a day |

### B. Usable by another team, on their own agents

This is the real gap, and none of it is hard.

| Gap | Why it matters | Size |
|---|---|---|
| ~~Copilot Studio needs a manual solution export~~ | Done: `--live-copilot-studio` reads the environment over the Dataverse Web API. Verified against the real Sandbox environment: the live read produces the same 21 findings and the same three-platform critical path as the export | |
| M365 declarative agents are read from files only | Real estates keep them in the tenant app catalog; Graph exposes it, but the read needs `AppCatalog.Read.All` | a day |
| ~~No getting-started for someone else's estate~~ | Done: `docs/USAGE.md`, including what Preflight will not tell you | |
| ~~Policy packs are an empty promise~~ | Done: `policies/swiss.yaml`, `eu.yaml`, `financial-services.yaml`. Verified with two controls: the EU pack flags the Swiss regions, the Swiss pack stays silent | |
| ~~Five modules carry no direct test~~ | Done: `tests/test_units.py` covers cost, privilege, the Copilot Studio collector, the dossier and the CLI exit codes | |

### C. The specification, in full

| Gap | Where it stands |
|---|---|
| **32 of the 62 specified rules are implemented** | Missing by family: ML 5, ID 4, MA 4, CO 4, DR 3, SC 3, TS 3, AP 2, RA 2. ML (model lifecycle) has nothing at all, and needs a model catalog to be worth anything |
| Agent Framework collector | Stub. Code-first, so it likely needs an exporter upstream |
| Agent 365 collector | Stub, and licence-blocked. See Blocked |
| Probe tier for edge resolution | Not built, and deliberately so: it makes network calls |
| Standards alignment, CycloneDX or SPDX | Open question, unverified, and not claimed anywhere in writing |
| Review board, trust graph in the dossier, what-if, auto-remediation | Roadmap |

**Honest summary, 2026-09-12.** The engine is real and the chain it finds is real, reproduced from
three agents that all exist in their platforms and, for two of them, read live rather than from
files. Tier B is closed apart from reading declarative agents out of the tenant app catalog, which
needs a Graph scope the CLI token does not carry. What is left is breadth, not soundness: half the
rule catalog, two collectors, and the probe tier. Breadth scales with time rather than with
cleverness, which is the good kind of gap to be left with.

## Built

- [x] AgentBOM schema v0.1, drift-guarded pydantic models, canonical serialisation
- [x] Identity derived from the composition hash, not random
- [x] Tool classifier, four tiers; untrusted MCP servers can only worsen a classification
- [x] Collectors: M365 declarative, Copilot Studio (real unmanaged solution export), Foundry from files and live
- [x] Cross-platform edge resolution, identity then endpoint
- [x] Attack path analysis, severity gated on edge evidence and sink evidence
- [x] Effective privilege closure (ID-08)
- [x] Cost in tokens, with money when the policy carries prices
- [x] Rule engine, 32 of the 62 catalog rules: AP-01, AP-02, AP-04, ID-01, ID-02, ID-03, ID-08,
      TS-01, TS-04, TS-05, TS-06, TS-08, MA-02, MA-04, MA-07, MA-08, DR-01, DR-05, RA-01, RA-03,
      RA-04, RA-05, RA-07, RA-08, SC-01, SC-05, SC-06, CO-01, CO-03, CO-06, CO-07, CO-09
- [x] Policy packs: Swiss, EU and financial services, in `policies/`
- [x] `docs/USAGE.md`: how to point it at someone else's estate
- [x] SARIF 2.1.0 for code scanning
- [x] Governance dossier, template v1.0, nothing invented
- [x] Certification that voids on any composition change
- [x] MCP manifest pinning (`preflight pin`, SC-01)
- [x] Baselines, so accepted findings do not fail the build
- [x] `policy.example.yaml`
- [x] GitHub Action: tests, scan, SARIF upload, dossier artifact. Gate verified both ways
- [x] Azure credit checked: CHF 0.23 spent this cycle; budget reset to CHF 130 so every alert fires
      before the spending limit blocks the subscription

## Blocked

- [ ] **`collectors/agent365.py`** needs Microsoft E7 or an Agent 365 licence; the demo tenant has
      E5 EEA, which qualifies as the prerequisite for buying one. Routes: an Agent 365 trial from the
      admin center, or the Frontier programme. The MVP support route is `mvpsupport@microsoft.com`
      from the profile address; `mvpga@` is unmonitored. Interface stubbed; open to a contributor

## Roadmap

- [ ] `collectors/agent_framework.py`
- [ ] Probe tier for edge resolution
- [ ] Review board of specialist agents
- [ ] Remaining catalog rules (residency, model lifecycle, the rest of RA and CO)
- [ ] Trust graph SVG inside the dossier
- [ ] What-if simulation, auto-remediation pull requests, estate intelligence

## After the hackathon

- [ ] **Upstream contribution**: add `ToolAnnotations` to MCP servers in `microsoft/mcp` and
      `Azure/azure-mcp` that ship none. Check contribution guidelines first
- [ ] The e-margot.ch project page, parked 3 Sep over the IP clause
- [ ] Decide whether to rewrite git history to remove event material pushed before 11 Sep

## Open questions

- [ ] Which bill-of-materials standard to extend, CycloneDX ML-BOM or the SPDX 3.0 AI profile.
      **Verify before claiming either in writing**
- [ ] Exact CAF and Zero Trust section numbers for the control column, cited by name for now
- [ ] Build on PSRule, or stay standalone
- [ ] Diagram palette: personal orange and navy, or the magenta brand palette

## Known traps

- **The az default context keeps reverting to an unrelated client subscription.** A token minted
  there hits the Foundry data plane as a 401 reading "invalid subscription key or wrong API
  endpoint". Always pass `--subscription`
- `az role assignment create` fails on this machine with `MissingSubscription`; use a direct ARM PUT
- `Azure AI Developer` does not grant `AIServices/agents`; `Cognitive Services User` does
- The Foundry v1 API rejects `require_approval` on MCP tools: there is no tool-level approval gate
- Microsoft 365 and Entra trials are billed outside Azure, so neither the Azure credit nor the
  spending limit covers them. Turn recurring billing off on anything activated
- Personal Edge must not hold the Playwright profile lock
- **Nothing read inside Innovation Studio goes into this repo.** It is marked Microsoft Confidential
