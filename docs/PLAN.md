# Implementation plan

Updated 2026-09-11. The analysis engine is built and tested; the README's Status table has the split
between what is built and what is roadmap. What remains is making the demo real in each platform,
and pulling forward the parts of the roadmap that strengthen it.

## Done

- Collectors for M365 declarative agents, Copilot Studio (fixture format) and Foundry, from files
  and live over the data plane
- AgentBOM schema v0.1, canonical serialisation, identity derived from the composition hash
- Tool classification in four tiers, cross-platform edge resolution by identity and endpoint
- Attack path analysis with severity gated on evidence, effective privilege closure, cost
- A 15-rule engine with control mappings
- SARIF, the governance dossier, certification, MCP manifest pinning, baselines
- A GitHub Action that fails a pull request on a new critical finding or a changed MCP manifest,
  verified with a control that must pass and one that must fail
- **Verified live**: scanning the real Foundry project reproduces the same critical path as the
  fixtures, so the headline is not an artefact of files written by hand

## Next, in order

1. ~~Put fixtures 01 and 02 into their platforms.~~ Done: 01 is in the tenant's app catalog and
   visible in Microsoft 365 Copilot, 02 is a real Copilot Studio agent. Publishing 02 is still open.
2. ~~Read a real Copilot Studio export.~~ Done: the collector reads the unmanaged solution export,
   and the chain reproduces from it unchanged.
3. **A demo pull request.** A branch that adds a destructive tool, or rewrites the MCP manifest, so
   CI fails with the finding annotated on the diff. Leave it unmerged; it is the demo.
4. **Record the demo.**

## Where extra hands go

Each piece is self-contained behind an interface that already exists.

| Piece | Interface | Note |
|---|---|---|
| A new platform collector | `collectors/base.py` | Analyzers read the BOM, never the platform |
| The Agent 365 collector | same | Needs Microsoft E7 or the Agent 365 licence; the demo tenant has neither. An internal contributor can finish it |
| The Agent Framework collector | same | Code-first, so it likely needs a tool-registration exporter upstream |
| Tier 1 registry entries | `classify/registry.py` | A table with rationales |
| Rules | `rules/catalog.py` | One function per rule, returning id, severity and control |
| Policy packs | `policy.example.yaml` | Swiss and EU residency, financial services, public sector |

## Roadmap

- Probe tier for edge resolution (opt-in, since it makes network calls)
- Review board of specialist agents for the judgments no rule can make
- What-if simulation and auto-remediation pull requests
- Estate intelligence across a tenant
- Trust graph rendered into the dossier as SVG
- The remaining catalog rules

## Engineering risks

| Risk | Mitigation |
|---|---|
| The az default context points at an unrelated subscription | The live collector always passes `--subscription` |
| Copilot Studio YAML is not strict YAML (unquoted Power Fx) | The collector quotes `=` values before parsing, and lists any component it still cannot read |
| The live Foundry API does not expose guards or connection secrets | Rules treat silence as unknown, never as absent, so live scans report fewer findings rather than wrong ones |
| Demo tenant loses Teams | Sideload and capture fixture 01 before it does |
