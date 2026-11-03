# Work Order — I00 OpenAdapt investigation and Engine build plan

```text
Task ID / Run ID: TASK-REDRISE-V2-BETA-20261026 / RUN-I00-20261026-01
Roadmap step: I00 (roadmap revision 3)
Human request and authorized scope: user 2026-10-26 submitted docs/AGENT-START-BETA.md and authorized research, local development and local proofs with synthetic data through a release-ready Beta. No commit/push/publication.
Product: product:redrise-v2
Repository: repo:redrise-v2
Root / remote / branch: D:/Correnth/products/redrise-v2/repos/app / https://github.com/correnth-ai/redrise_v2.git / main
Actual HEAD (or unborn) and source-tree digest: unborn; scripts/source-digest.mjs at start = dba9b34313b4cd720006c9f07f4cd9789d49cc873ddcd0e73843f57b259417f8 (44 files, includes this new script)
Existing dirty files to preserve: whole tree untracked (no commits); .local/ (prior lab venv on D:, left untouched)
Objective and observable acceptance: source map with pinned revisions and catalogue-use table; independent behaviour spec; reviewed E01–E04/P01 build plan; delivery/evidence/I00/investigation.json.
Non-objectives: Engine code; installing upstream OpenAdapt; dynamic analysis without a concrete unanswered question; cloud/MCP/qualification/plugins mapping beyond boundary.
Predecessor evidence (path + SHA256): delivery/evidence/P00/bootstrap.json (hash recorded in I00 evidence)
Allowed write set / read sources: docs/investigation/**, delivery/evidence/I00/**, delivery/work-orders/I00-*.md, delivery/status.json, scripts/source-digest.mjs. Read: C:/Users/raulv/RedRise-v2-dev/research/{awesome-reverse-engineering,OpenAdapt,openadapt-capture,openadapt-flow}.
Dependencies and technical decisions to make: none installed; Engine language/boundary proposal handed to E01.
Applicable skills / resolved pins: scope-planning fd7b13af…8bfa; upstream-license-governance 74699dbd…3ec1; task-context-checkpoint 88c25b1e…3437 (catalog HEAD 63ffa260e8807b9a3fa28a59e16103a591fbea22).
Memory workspace/project, availability and primary-source confirmations: correnth/redrise-v2; ai-memory CLI absent (AppData/Local/ai-memory-correnth/bin missing) -> degraded, canonical files used.
Registered graph root/query or canonical fallback: repo:redrise-v2 registered in repositories.yaml; no graphify root for it -> no graph use; source reading fallback.
Delegation envelope: two read-only Explore subagents (capture/finalization; compile/IR/execution), root-limited to the lab checkouts, no writes/execution/recursion, cited <=1200-word reports; principal verifies material claims in source.
Commands or native scenarios proving acceptance: git rev-parse of each checkout; source-citation spot checks by principal; node scripts/validate-base.mjs.
Expected artifacts / retention and data class: markdown docs + JSON evidence, public-source derived, no personal data.
Stop condition / bounded attempts: upstream not resolvable by revision, or design-blocking uncertainty -> I00 blocked with reason.
Recovery or rollback without destroying data: remove only files created by this WO.
External/interactive/cost/credential/HITL boundaries: public git clones only; no credentials; no native interaction.
Independent review requirement and reviewer: read-only review agent (not the author) over the three documents.
Completion / failures / next action: see delivery/evidence/I00/investigation.json.
```
