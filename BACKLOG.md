# Backlog

Last updated: 2026-09-11, audited against the working tree and the tenant. Event-specific items live
in `docs/PLAN.private.md`, which is not in git.

## Where it stands

**The analysis engine is built.** 29 tests pass, including in a clean virtualenv installed the way
CI installs it. `preflight scan fixtures` produces exactly the 19 findings in `fixtures/CHAIN.md`,
and a live scan of the real Foundry project reproduces the same critical path.

### Which fixtures exist where

| Fixture | On disk | In its platform |
|---|---|---|
| 01 Inbox triage, M365 declarative | yes | **yes**, uploaded to the org app catalog from `dist/fixture-01-inbox-triage.zip` |
| 02 Contract router, Copilot Studio | yes, hand-authored stand-in | **no**, never built in Copilot Studio |
| 03 Records agent, Foundry | yes | **yes**, `asst_Y3XUjyknLU4ZzR732qhPDe7F` with MCP tool `records` |

## Next

- [x] **Sideload fixture 01**: `python scripts/package_fixture01.py` builds the package from a copy
      (adds icons and real developer URLs; the fixture and baseline are untouched), uploaded 2026-09-11.
      Capturing it running in Copilot is part of the item below
- [ ] **Build fixture 02 in Copilot Studio** (Sandbox environment), export the unmanaged solution,
      replace the stand-in, and make the collector read the real export into the same BOM
- [ ] **Capture each platform's own view** of its agent, for the demo
- [ ] **Demo pull request**: a branch adding a destructive tool or rewriting the MCP manifest, so CI
      fails with the finding on the diff. Leave it unmerged
- [ ] Record the demo
- [ ] Complete the project page (checklist in the private plan)

## Built

- [x] AgentBOM schema v0.1, drift-guarded pydantic models, canonical serialisation
- [x] Identity derived from the composition hash, not random
- [x] Tool classifier, four tiers; untrusted MCP servers can only worsen a classification
- [x] Collectors: M365 declarative, Copilot Studio (stand-in format), Foundry from files and live
- [x] Cross-platform edge resolution, identity then endpoint
- [x] Attack path analysis, severity gated on edge evidence and sink evidence
- [x] Effective privilege closure (ID-08)
- [x] Cost in tokens, with money when the policy carries prices
- [x] Rule engine, 15 rules: AP-01, AP-02, ID-01, ID-03, ID-08, TS-01, TS-06, MA-08, RA-01, RA-03,
      RA-04, RA-07, SC-01, SC-05, CO-03
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
