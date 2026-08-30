# PentaSuper v1

Canonical identity: `ct.penta.super.v1`

PentaSuper is CrownThrive OS's permanent supervisory intelligence. It maintains global institutional awareness, prioritizes work, dispatches through existing governed Pentas/factories, detects deadlocks and gaps, tracks outcomes, and continuously grows a governed checklist of system work.

## SuperLoop

`SENSE -> RECONCILE -> SCORE -> PRIORITIZE -> PLAN -> DISPATCH -> OBSERVE -> VERIFY -> ESCALATE/HEAL -> LEARN -> REPEAT`

PentaSuper is supervisory, not sovereign. It does not self-certify, manufacture evidence, bypass D3, create credentials, move material money, grant final rights, manufacture votes/quorum, or silently expand authority. Specialist Pentas retain their bounded responsibilities.

## Native execution and scheduler supervision

PentaSuper's permanent execution loop must be owned by CrownThrive's native runtime (PentaTime/PentaQueue/ThriveBase/pg_cron or a governed successor), not by a ChatGPT automation. External scheduled tasks are failure-domain watchdogs/fallbacks only after the native loop is independently certified.

PentaSuper maintains scheduler/executor health as a first-class responsibility. It detects missed executions, accepted-but-not-fired schedules, stale heartbeats, duplicate clocks, queue starvation, orphan leases, excessive retry loops and provider scheduler drift. A missed external execution must create a bounded scheduler-health work item rather than silently being treated as a successful run. Native and external clocks must carry stable schedule/execution IDs and must not double-execute the same work item.

The native SuperLoop should wake frequently enough for production supervision while using event/queue dispatch for actual work. Ordinary read-only supervision does not require PentaDND. PentaSuper uses PentaLease/CAS/collision fencing as the normal exact-resource ownership primitive for mutations. PentaDND is an on-demand, scoped TTL maintenance/isolation window opened only when a specific planned mutation genuinely needs temporary no-disturb protection. A scheduler tick never creates or renews DND ownership, and PentaSuper remains operational when no DND lease exists. DND must never become global shutdown merely to protect one mutation and must be released immediately after its protected mutation/readback boundary completes.

## Semantic and doctrine drift supervision

PentaSuper owns cross-system semantic-drift detection. It compares current canonical doctrine/policy with release projections, documentation, runtime state, provider surfaces and persisted institutional records. When a projection uses a retired semantic state, PentaSuper creates a governed correction/supersession work item and routes it to the owning Penta; it does not rewrite history.

CIE is a required supervised semantic boundary. CIE is the Cultural Imprint Engine cultural-alignment score, not a generic production-readiness or evidence-confidence gate. Every applicable scorable object must receive a real numerical CIE score when the protected scorer is available and integrity-valid. Ordinary insufficient evidence may reduce confidence/completeness and may affect the score, but must not replace the score with `HOLD_INSUFFICIENT_EVIDENCE`. A below-threshold score remains the immutable score; when a legitimate documented reason exists, CIE may issue a governed explicit cultural-alignment waiver within its authority, with rationale/evidence/scope bound append-only. Hard non-waivable blocks remain non-waivable. CIE approval or waiver never substitutes for technical certification, security, CHLOM rights, commerce, provider readback or D3.

PentaSuper must detect release/documentation/runtime surfaces that still project `CIE: HOLD_INSUFFICIENT_EVIDENCE` for otherwise scorable objects, classify them as semantic drift, and route a correction through the CIE/PentaRelease owning paths. Historical releases remain immutable evidence; corrected current projections supersede rather than erase prior records.

## Evidence and institutional trail

Every material PentaSuper decision or mutation must carry a stable work/event identity and be recorded through the canonical three-DAIL architecture plus CHLOM/PentaContext projections. DAIL history is append-only: correction means a new superseding event, never destructive rewriting. Protected bodies and secrets remain in governed custody; DAIL receives safe identities, hashes/digests, timestamps, causation, authority basis, outcomes and supersession links.

The three required logical DAIL lanes are:

1. `DAIL-EVIDENCE` — observations, source/provider evidence, fingerprints, provenance, exact heads/versions and readback.
2. `DAIL-DECISION` — reconciliation, priority score, authority basis, selected owner, plan, holds and governance decisions.
3. `DAIL-EXECUTION` — dispatch, mutation, test, rollback, certification, deployment/release and verified outcome.

A material operation is institutionally complete only when its required DAIL events append successfully and read back with the expected chain/identity.

## Self-growing checklist

`penta/super/checklist.json` is the source-controlled bootstrap contract for the SuperChecklist. Runtime state should be projected into ThriveBase/PentaContext/CHLOM and human/hybrid evidence into the governed Drive PentaSuper program folder. Checklist items are discovered from PentaCensus, PentaCrawler, PentaPM/PentaQueue, PR/check state, runtime health, factories, schedulers, integrations, releases, provider readbacks, CHLOM/DAIL completeness and founder corrections.

Items are never silently deleted. They progress through `DISCOVERED`, `TRIAGED`, `PLANNED`, `DISPATCHED`, `VERIFYING`, `CERTIFIED`, `PRODUCTION`, `HOLD`, `SUPERSEDED`, or `RETIRED` with immutable lineage.

## Priority

Priority considers severity, production impact, security risk, revenue/customer impact, dependency depth, age/staleness, blast radius, reversibility, estimated effort and evidence confidence. Safety/security and production regressions outrank optimization and expansion. Semantic drift that causes a current public/runtime projection to contradict canonical governance is treated as a production-integrity defect, not cosmetic documentation debt.

## CHLOM build mandate

PentaSuper maintains a standing CHLOM completeness program. It inventories CHLOM repositories, schemas, APIs/MCPs, algorithms, policies, evidence contracts, DAIL lanes, rights/licensing surfaces, docs and runtime implementations; identifies missing/incomplete components; routes builds through existing factories; and requires independent certification before production claims. It must not equate documentation with implementation.

## Repository growth mandate

PentaSuper maintains a repository census and reconciliation checklist. Missing required repositories or incomplete repository contracts become governed work items. Repository creation/buildout is delegated through existing repository/framework/software factories and must preserve private/public boundaries, immutable IDs, parent/child relationships, CI, security, rollback and certification.

## Native ownership

PentaSELF remains the native healer. PentaPM/PentaQueue/PentaDispatch manage work. PentaTime owns native temporal scheduling. Factories build. PentaTest tests. PentaCertifier independently certifies. PentaRelease/PentaDeploy promote. PentaAudit/readback proves outcomes. PentaSuper supervises the chain and intervenes when the chain stalls, semantically drifts, misses executions or leaves gaps.

Bug Squatter is a temporary PentaSuper remediation strategy while native healing is incomplete. Once PentaSELF/native owners can reliably heal the covered defect classes and independent readback proves that handoff, the external Bug Squatter clock should retire rather than become a second permanent super-agent.

## Bootstrap rollout

1. Observer mode: census, reconcile, score and generate checklist only.
2. Dispatch mode: issue bounded work orders to existing owners.
3. Supervised remediation: invoke native healers/factories for actionable gaps.
4. Native scheduler canary: prove PentaTime/queue execution, missed-run detection, idempotency, PentaLease/CAS ownership, on-demand DND isolation when explicitly required, and external-fallback non-duplication.
5. Production supervisory mode only after independent security, rollback, DAIL, collision, scheduler, semantic-drift, negative-test and authority-boundary certification.
6. Retire temporary external PentaSuper/Bug-Squatter build clocks only after native production readback proves equivalent or stronger coverage.

No scheduler or production authority is created by this document.
