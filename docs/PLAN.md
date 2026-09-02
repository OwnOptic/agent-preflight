# Implementation plan

Hackathon week is 14 to 18 September 2026. It is not a clear week.

| Commitment | When | Leaves free |
|---|---|---|
| Frontier Transformation Week | 14 to 17 Sep, up to 3.5h/day | afternoons |
| Global Agent-a-thon, moderating L2 | Thu 17 Sep, 13:15 to 16:30 | Thursday morning |
| M365 Con D-A-CH keynote | Fri 18 Sep, 08:00 to 08:45 | Friday from 09:30 |

Five usable half-days, roughly two and a half effective days. The plan is built to that, not to
what the capability list describes.

## The rule that governs everything below

**Every slot ends with something demoable.** Vertical slices, never horizontal layers. If the week
collapses after slot 3, there is still a demo. If it collapses after slot 1, there is still a
working tool that does one useful thing.

Each slot below names a **cut line**: the thing to drop first if time runs out.

---

## Phase 0 · Before the week (now to 13 September)

This is the phase that decides whether the week works. None of it is coding.

| # | Task | Why it blocks | Done when |
|---|---|---|---|
| 0.1 | **Get into Innovation Studio** | Nothing else matters without it | Registered, profile tagged `MVP26`, role Hackers, project created |
| 0.2 | **Create a Foundry project** on `fdy-demo-agents-de-em` | Verified 2026-09-02: `projects` returns `[]`. Model deployments exist, Agent Service does not. Also settles whether Agent Service is available in switzerlandnorth | A project exists and one agent can be created in it |
| 0.3 | **Build the three fixtures** | They define what the tool must detect, so they come before the code that detects it | `fixtures/` holds three agents whose endpoints chain, per `fixtures/README.md` |
| 0.4 | **Write `policy.example.yaml`** | Every `pol` rule reads it, and the trusted-server list gates the classifier | Loads into `Policy`, with the fixture MCP server deliberately absent from the trusted list |
| 0.5 | **Fill `classify/registry.py`** | Tier 1 is a table, not code. Cheap, and it can be done in gaps | Every Foundry built-in tool has an entry with a rationale |

Do not skip 0.3. Building fixtures after the analyzer is how you end up with a tool that only
detects what you happened to build.

---

## Slot 1 · Monday 14 PM — first BOM

**Target: `preflight collect` produces a schema-valid AgentBOM.**

Start with the M365 declarative collector. It reads files from disk, needs no licence, no tenant
and no network, so it reaches a real BOM faster than anything else, and it exercises the whole
pipeline end to end on day one.

- `collectors/m365_declarative.py`: parse `declarativeAgent.json`, follow every referenced API
  plugin manifest, follow each plugin's OpenAPI document, emit one `Tool` per operation with
  `httpMethod` populated
- Wire the classifier in: every tool comes out with a `classification` and a `source`
- `cli.py`: `preflight collect <path>` prints canonical JSON
- Validate the output against `schema/agentbom-0.1.json` in a test

**Demoable:** a real agent, a real BOM, every tool classified with its reasoning attached.
**Cut line:** skip OpenAPI following, emit the plugin as a single opaque tool.

---

## Slot 2 · Tuesday 15 PM — three platforms

**Target: three BOMs from three platforms, one schema.**

- `collectors/copilot_studio.py`: read an exported unmanaged solution from disk. Prefer the export
  over live Dataverse: offline, versionable, no environment needed mid-demo
- `collectors/foundry.py`: `azure-ai-projects` against the project from 0.2. Agents, toolboxes,
  connections, connected agents, content filters
- `preflight scan <dir>` runs every available collector and writes one BOM per agent

**Demoable:** one command, one directory, three platforms, three BOMs.
**Cut line:** Foundry from a saved API response rather than live. The BOM is what matters, not
where it came from.

---

## Slot 3 · Wednesday 16 PM — the demo

**Target: the critical path prints. This is the slot that decides the week.**

- `resolve/edges.py`: index every published inbound endpoint across all BOMs, normalise every
  outbound URL, intersect. Identity match first, endpoint match second. Probe stays unimplemented
- `analyze/paths.py`: build the graph, mark untrusted-input sources and irreversible-action sinks,
  find reachability, drop any path that crosses a declared human gate
- Severity gating: **critical only when every edge on the path is proven or matched**
- Print the path as a readable chain, not a JSON blob

**Demoable:** the whole pitch. Three approved agents, one critical finding, the path printed.
**Cut line:** none. If this slot does not land, the project has no demo. Protect it by moving
slot 2's Foundry work earlier if slot 1 runs long.

---

## Slot 4 · Thursday 17 AM — findings that land somewhere

**Target: findings in a pull request.**

- `rules/`: the `def` rules from AP, ID, TS and MA. One module per domain, one function per rule,
  each returning a finding with its id, severity and control reference
- `report/sarif.py`: SARIF 2.1.0 output, rule ids from the catalog become SARIF rule ids
- `.github/workflows/preflight.yml`: run on PR, upload SARIF via `github/codeql-action/upload-sarif`
- Baseline file, so existing findings can be accepted and only new ones fail the build

**Demoable:** open a PR that adds a tool to a fixture, watch the check fail with the finding
annotated on the diff.
**Cut line:** drop the baseline file. Drop the Azure DevOps task entirely, it adds nothing to the
demo.

---

## Slot 5 · Friday 18 from 09:30 — cost, dossier, submit

**Target: submitted, with the demo recorded.**

- `analyze/cost.py`: prompt tax and tool surface tax only. Both are token counts already in the
  BOM, so this is arithmetic rather than integration
- Cost delta posted as a PR comment
- `report/dossier.py`: render the template. Sections 1, 4, 5, 8 and 11 are fully derivable from the
  BOM and the findings; everything else prints *requires human input*
- **Record the three-minute demo** and attach it to the Innovation Studio project

**Cut line:** the dossier. Cost is cheaper to finish and lands harder in a room. If only one of the
two happens, make it cost.

---

## Where extra hands go

Anyone who joins can take one of these without touching the core. Each is self-contained and each
has a clear interface already in the repo.

| Piece | Interface | Why it is separable |
|---|---|---|
| A new platform collector | `collectors/base.py` `Collector` protocol | Analyzers read the BOM, never the platform |
| The Agent 365 collector | Same | **Needs Microsoft E7 or the Agent 365 add-on. The MVP tenant is E5, so this cannot be built or tested here.** An internal contributor can |
| Tier 1 registry entries | `classify/registry.py` | A table with rationales |
| Policy packs | `policy.py` | Swiss and EU residency, financial services, public sector |
| A review board specialist | not yet scaffolded | Reads the BOM, produces findings, cannot contradict a deterministic one |
| MCP annotation contributions | upstream | Servers in `microsoft/mcp` and `Azure/azure-mcp` that ship no `ToolAnnotations` |

---

## Definition of done for the week

1. `preflight scan fixtures/` finds the cross-platform critical path, printed as a chain
2. A pull request shows the finding as a SARIF annotation on the diff
3. Every finding cites a rule id and a named control
4. The three-minute demo is recorded and attached to the project
5. The repo README explains the gap in four paragraphs to someone who has never seen it

Everything else in `capabilities.md` is roadmap, and the project description should say so rather
than let anyone assume it ships by Friday.

---

## Known risks

| Risk | Mitigation |
|---|---|
| No Innovation Studio access | Phase 0.1. Nothing else matters until it is resolved |
| Agent Service unavailable in switzerlandnorth | Phase 0.2 settles it. Fallback is a project in a supported region, which costs the Swiss residency angle in the demo narrative |
| Azure credit exhausted mid-week | `rg-agentlens` already deleted. Check the balance in the portal, the subscription has a spending limit and will disable rather than bill |
| Slot 3 slips | It is the demo. Move Foundry collection earlier and cut slot 2's live integration instead |
| Scope creep from `capabilities.md` | The capability list is the vision. This file is the commitment |
