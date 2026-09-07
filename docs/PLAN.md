# Implementation plan

Rewritten 2026-09-07 against the real rules, read from Innovation Studio rather than assumed.

## What the event actually requires

**The only deliverable is a video of two minutes or less.** A project is eligible for Executive
Challenge judging only if the project page has a Description and a video is uploaded by the
deadline. No deck, no repo, no write-up is required. The repo is optional evidence.

| When | What |
|---|---|
| Mon 14 Sep | Hacking begins |
| Tue 15 Sep | Continues |
| **Wed 16 Sep, close of business** | Official hacking ends. Teams may keep working |
| Thu 17 - Fri 18 Sep | Science fairs and demos |
| **Mon 21 Sep, 23:59 Pacific** | **Video upload and submission deadline** |

Build window is Monday to Wednesday. The weekend is for the video. Elliot's Agent-a-thon
(Thu 17, 13:15-16:30) and M365 Con keynote (Fri 18, 08:00) now fall on science-fair days rather
than on build time.

**Executive Challenge: Hack to Make Agents Trustworthy**, sponsored by Sarah Bird. Exactly one
Executive Challenge per project; selecting "Other" removes the project from judging entirely.

**Submissions are machine-sorted before a human sees them.** AI is used to classify submissions
against challenge goals and route them to reviewers with matching expertise. The description is
read by a classifier first, so wording that echoes the challenge earns the right reviewer.

**Disclose AI-assisted authoring.** The event encourages it and asks that major tools be named.

## The judging rubric

Every one of these must be visible in a two-minute video. Anything implicit is unscored.

| Category | What it asks | Where the video earns it |
|---|---|---|
| Inspiration | Energy, novelty, fresh perspective | The cross-platform path nobody can currently see |
| Business Value | Monetary or non-monetary value to Microsoft | Agents blocked before they ship; the composition metadata feeds Agent 365 |
| Customer Focus | Clear target audience, compelling for them | Named out loud: the engineer shipping an agent, and the reviewer who has to approve it |
| Feasibility | Viable pathway to implementation | Deterministic, SARIF, runs in CI, complements a control plane Microsoft is already building |
| Make Something | Built, not proposed | A working CLI failing a real build on a real finding |

## Phase 0 - before Monday 14

| # | Task | Done when |
|---|---|---|
| 0.1 | ~~Innovation Studio access~~ | Done. Registered, project creation open |
| 0.2 | **Create a Foundry project** on `fdy-demo-agents-de-em` | Verified 2026-09-07: `projects` still returns `[]`. Agent Service is not set up. This blocks the Foundry collector and the fixtures |
| 0.3 | **Build the three fixtures** | `fixtures/` holds three agents whose endpoints chain, per `fixtures/README.md` |
| 0.4 | `policy.example.yaml` | Loads into `Policy`, fixture MCP server deliberately absent from the trusted list |
| 0.5 | Fill `classify/registry.py` | Every Foundry built-in has an entry with a rationale |
| 0.6 | **Publish the project page** with Title, Tagline, Description, Executive Challenge, Topic Challenges | Description is an eligibility requirement, not a nicety. Do it now, edit later |

## Build, Monday 14 to Wednesday 16

Vertical slices. Every slot ends with something demoable, and each names what to drop first.

**Mon 14 - first BOM.** The M365 declarative collector: parse `declarativeAgent.json`, follow the
API plugin manifests and their OpenAPI documents, emit one `Tool` per operation with `httpMethod`
set. Wire in the classifier. `preflight collect <path>` prints canonical JSON, validated against
the schema in a test. Files on disk, no licence, no tenant, so the whole pipeline runs on day one.
*Cut: skip OpenAPI following, treat the plugin as one opaque tool.*

**Tue 15 - three platforms.** Copilot Studio from an exported unmanaged solution on disk. Foundry
via `azure-ai-projects` against the project from 0.2. `preflight scan <dir>` runs every available
collector.
*Cut: Foundry from a saved API response rather than live.*

**Wed 16 - the demo.** Edge resolution: index published inbound endpoints, normalise outbound URLs,
intersect. Identity match first, endpoint match second, no probe. Attack path reachability with
severity gated on confidence. Print the path as a readable chain.
*Cut: none. Without this there is no video. Protect it by moving Foundry work earlier if Monday
runs long.*

Then, if Wednesday allows: the `def` rules from AP, ID, TS and MA, SARIF output, and a GitHub
Action that fails a build. That is what makes "Make Something" and "Feasibility" concrete on
camera.

## The video, Thursday 17 to Monday 21

Two minutes. Every second is scored. Rehearse it; do not narrate live.

| Time | Beat | Rubric |
|---|---|---|
| 0:00-0:20 | Three agents, three platforms, each reviewed and approved separately. Name the customer out loud: the engineer shipping the agent, and the reviewer who has to sign it off | Customer Focus |
| 0:20-0:35 | `preflight scan`. Deterministic, no traffic, no tokens, two seconds | Make Something |
| 0:35-1:05 | One critical. Print the path. Then open each platform's own tooling and show each reports clean. The defect exists only in the composition | Inspiration |
| 1:05-1:25 | Why it can be trusted: deterministic, every finding cites a CAF or Zero Trust control, confidence gates severity | Feasibility |
| 1:25-1:45 | SARIF failing a pull request. The dossier | Make Something |
| 1:45-2:00 | It runs before registration and feeds Agent 365 rather than competing. An agent stopped before it ships is the value | Business Value |

Record Thursday or Friday so the weekend is contingency, not the plan. Upload well before Monday
23:59 Pacific, which is Tuesday 08:59 in Lausanne, so **the practical deadline is Monday evening.**

## Where extra hands go

| Piece | Interface | Note |
|---|---|---|
| A new platform collector | `collectors/base.py` | Analyzers read the BOM, never the platform |
| The Agent 365 collector | Same | Needs Microsoft E7 or the Agent 365 add-on. The MVP tenant is E5, so this cannot be built or tested here. An internal contributor can |
| Tier 1 registry entries | `classify/registry.py` | A table with rationales |
| Policy packs | `policy.py` | Swiss and EU residency, financial services, public sector |

## Definition of done

1. A video of two minutes or less, uploaded before Monday 21 Sep 23:59 Pacific
2. The project page carries a Description and the Executive Challenge is set
3. `preflight scan fixtures/` finds the cross-platform critical path
4. A pull request shows the finding as a SARIF annotation
5. AI-assisted authoring disclosed on the project page

Items 1 and 2 are eligibility. Everything else is score.

## Risks

| Risk | Mitigation |
|---|---|
| No Foundry project | Phase 0.2, and it also settles whether Agent Service exists in switzerlandnorth |
| Azure credit exhausted | `rg-agentlens` deleted. Check the balance in the portal |
| Wednesday slips | It is the video's content. Move Foundry earlier and cut Tuesday's live integration |
| Two minutes is short | Rehearse. The single biggest risk is trying to show two findings instead of one |
| Confidentiality | Innovation Studio content is Microsoft Confidential. Nothing from it goes into the public repo, the website, or a post |
