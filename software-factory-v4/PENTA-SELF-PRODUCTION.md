# PentaSELF™ Production Autonomy and Resilience Plane

Status: **Phase 3 / Production**  
Owner: CrownThrive, LLC  
Stable contract: `ct.penta.self.v1`

## Canonical placement

The production execution hierarchy is:

`Founder/Reserved Authority -> CHLOM -> PentaFabrics™ -> PentaSELF™ -> PentaMeshes™ -> Cultural/Convergent Intelligence -> PentaAgentic -> Jobs/Crons -> PentaFactory -> PentaSecure -> Vault/Evidence/Continuity`

PentaSELF is therefore below the PentaFabrics orchestration plane and immediately above the PentaMeshes interoperability/routing plane. It is not a replacement for either. PentaFabrics composes institutional execution; PentaSELF protects and repairs that execution; PentaMeshes select and carry bounded routes after PentaSELF health and authority checks.

## Production rule

Phase 3 is production. `PentaFabric` and `PentaMesh` are production lifecycle records, and the PentaSELF plane is production software. Controlled-test terminology may still appear in historical evidence or provider-specific certification states, but it is not the lifecycle state of the Phase 3 control plane.

## PentaSELF responsibility

PentaSELF owns the self-* behaviors required for CrownThrive to behave as a living, self-healing software system while preserving governance boundaries. The capability registry includes:

- SelfAwareness, SelfObserve, SelfMonitor, SelfDiscovery, SelfDiagnose
- SelfHeal, SelfRepair, SelfReconcile, SelfRecover, SelfRestart, SelfRollback, SelfRebind
- SelfRoute, SelfTest, SelfVerify, SelfCertify, SelfNurture, SelfSecure, SelfQuarantine
- SelfClose, SelfRefresh, SelfSync, SelfScale, SelfOptimize, SelfPrioritize, SelfSchedule, SelfBalance
- SelfAudit, SelfLearn, SelfAdapt, SelfClean, SelfArchive, SelfBackup, SelfRestore, SelfMigrate
- SelfVersion, SelfDeploy, SelfRelease, SelfUpdate, SelfDocument, SelfPreserve
- SelfFailClose, SelfEscalate, SelfResume, SelfDegrade
- SelfGovern, which is explicitly human-reserved for D3 authority

The registry is extensible: a newly required self-* behavior is added as a typed capability with a handler, action mode, maximum risk class, reversibility rule, and verification rule rather than being implemented as unbounded autonomous code.

Every registered Penta member also has the governed software-gap route defined by `data/penta/self-build.contract.json`: typed gap through PentaRFA, PentaFactory candidate, acceptance/negative/stress tests, independent PentaCertify/PentaAssure evidence, governed release/PR/merge, provider readback and preservation. This creates institution-wide software-building capability without allowing the requesting member or PentaFactory to self-certify or self-promote.

## Self-healing cycle

`penta_self.tick_v1()` is the canonical production healing loop. It acquires a concurrency lock and then performs:

1. required scheduler reconciliation;
2. allowlisted recovery of failed required jobs;
3. PentaFabric/PentaSELF/PentaMesh topology reconciliation;
4. Phase 3 provider/capability self-discovery;
5. bounded legacy ThriveBase self-heal compatibility;
6. provider certification-evidence activation;
7. PentaBuild software-quality sweep;
8. PentaNurture runtime nursing;
9. PentaRoute autonomy/recovery;
10. PentaSecure cycle;
11. independent health snapshot and immutable-style action/cycle receipts.

A failed scheduler is not merely marked healthy. PentaSELF first restores missing/inactive/drifted cron definitions. If the latest required run failed, PentaSELF invokes only an explicit allowlisted recovery handler and writes a recovery receipt. Health treats the failure as recovered only when that bounded recovery succeeds after the failed run.

## Required production schedules

PentaSELF supervises the critical production set, including:

- `ct-penta-self-v1` — every 2 minutes
- `ct-phase3-self-discovery-v3` — every 5 minutes
- `ct-penta-certify-v3` — every 2 minutes
- `ct-penta-provider-evidence-bridge-v1` — every 2 minutes
- `ct-penta-build-quality-v1` — every 5 minutes
- `ct-penta-nurture-v1` — every 5 minutes
- `ct-pentatime-reconcile-v1` — every 5 minutes
- `ct-pentaroute-autonomy-v3` — every 5 minutes
- `ct-software-factory-continuity-v5` — every 2 minutes
- `ct-software-factory-dispatch-v3` — every minute
- the existing bounded ThriveBase self-diagnostic/self-heal compatibility schedule

PentaSELF repairs missing schedules and safe schedule drift through `cron.schedule` / `cron.alter_job`; it does not execute arbitrary scheduler SQL supplied by runtime data.

## PentaFabrics™ software

PentaFabrics is a production orchestration plane, not just a label. Its runtime exposes:

- `penta_runtime.penta_fabrics_status_v1()`
- `penta_runtime.penta_fabric_cycle_v1()`
- service-role public RPC wrappers
- JWT-protected `penta-fabric` Edge Function with `status`, `health`, `cycle`, and `orchestrate` actions

A Fabric cycle invokes PentaSELF directly in the database control plane, then verifies PentaMeshes. It reports healthy only when the self-healing plane is healthy or already locked by another live healing cycle and the mesh remains production.

## PentaMeshes™ software

PentaMeshes is the production routing, redundancy, federation and provider-edge plane. Its runtime exposes:

- `penta_runtime.penta_meshes_status_v1()`
- existing `penta_runtime.penta_mesh_select_route_v1(jsonb)` bounded route selector
- service-role RPC wrapper `public.penta_mesh_select_route_v1(jsonb)`
- JWT-protected `penta-mesh` Edge Function with `status`, `health`, and `route` actions

The route selector rejects unresolved identity and routes that imply provider writes, money movement or rights grants. It chooses only a bounded resolved route and explicitly does not inherit or manufacture authority.

## PentaSELF API

The JWT-protected `penta-self` Edge Function is service-role-only and exposes:

- `status` / `health`
- `tick` / `heal` / `reconcile`

It calls database RPC directly. It does not recursively invoke other Edge Functions, keeping the healing path deterministic and avoiding nested-function network dependence.

## Guardrails

PentaSELF may automatically repair reversible D0-D2 system state only through predeclared handlers and certified paths. It may not:

- manufacture authority;
- manufacture or expose credentials;
- self-grant provider certification;
- bypass PentaCertify;
- perform an uncertified provider write;
- move money without explicit existing authority;
- grant rights;
- perform universal delete;
- auto-promote D3 decisions;
- erase evidence to make health appear green.

D3 remains human/governance-reserved.

## Production acceptance proof

The initial production cycle deliberately returned degraded when the new PentaSELF scheduler was not yet registered. PentaSELF repaired that scheduler and a later verification cycle returned healthy with all required schedules aligned.

A subsequent Fabric acceptance cycle encountered a real failed `ct-phase3-self-discovery-v3` cron run caused by a database deadlock. PentaSELF detected the failed required job, ran the explicit bounded recovery handler successfully, recorded the recovery receipt, and returned **HEALTHY** with zero unrecovered required-job failures. This is the acceptance condition for self-healing: detect -> repair/recover -> verify -> receipt -> healthy.

Provider certification backlog is not hidden by PentaSELF. Certified, readback-needed, write-canary-needed, adapter-needed, and governance-blocked states remain visible and continue through PentaBuild/PentaCertify/PentaCredentials/PentaNurture.

## Security posture

PentaSELF tables are private fail-closed stores. RLS is enabled, public/anon/authenticated table privileges are revoked, and service-role access is used for the internal control plane. The absence of public RLS policies is intentional for these private tables.

The public RPC wrappers are service-role-only. The Edge Functions require Supabase JWT verification and additionally require the JWT role to be `service_role` before invoking control-plane RPCs.

PentaSELF™, PentaFabrics™, and PentaMeshes™ are CrownThrive names presented with common-law trademark notice; this document does not represent a claim of federal registration.
