# PentaSELF Factory Continuity V6 — Production Evidence

**Status:** `CERTIFIED_PRODUCTION`  
**Certified scope:** CrownThrive software-factory continuity control plane  
**Incident date:** 2026-08-29  
**Authority:** D1 bounded, reversible; D3 remains human-reserved  
**Canonical contract:** `ct.penta.factory-continuity.v6`

## Incident

PentaSELF reported `recover_failed_required_job` for `cron:ct-software-factory-continuity-v5`.

| Field | Value |
|---|---|
| Original recovery receipt | `5363a4f9-f63e-4d1c-a93b-9cef198f4b0d` |
| Original cycle | `8bf4f4b0-1545-441a-8f85-703021f21640` |
| Original finding | `8014d0e8-71e7-42d6-baaf-8140449186ae` |
| PostgreSQL state | `40P01` |
| Failure class | Deadlock detected |
| Failed relation | `public.ct_factory_backlog_items` |
| Failure time | `2026-08-29T18:50:02Z` |
| Call chain | `ct_factory_reconcile_continuity()` → `ct_factory_continuity_cycle(integer)` |

PentaSELF's first bounded retry succeeded one minute later, but that recovery proved only that the failed cycle could be retried. It did not remove the concurrency defect.

## Root cause

The software-factory family had overlapping mutation clocks that could enter the same backlog, surface-binding, dispatch, and reconciliation records through different paths and lock orders. The active family included continuity, dispatch, a standalone factory tick, surface-binding synchronization, and internal generation.

Two stale desired-state authorities could also restore the pre-surgery raw commands after a live repair:

1. `integration_control.scheduler_desired_jobs_v2`
2. `penta_self.desired_state_contracts_v1`

PentaSELF V3 also lacked evaluator handlers for four already-registered permanent-repair classes:

- `factory_continuity_surgery`
- `factory_generator_surgery`
- `pentaod_lock_surgery`
- `locticians_provider_types`

That handler gap caused valid repairs to be reported as degraded instead of being independently verified.

## Permanent repair

The production repair converged the factory family behind one nonblocking PentaTime contention domain:

`ct:production-governance-write-lane`

Canonical guarded operations:

| Operation | Active clock command |
|---|---|
| `factory_continuity` | `select pentatime.execute_guarded_v3('factory_continuity');` |
| `factory_dispatch` | `select pentatime.execute_guarded_v3('factory_dispatch');` |
| `factory_internal_generate` | `select pentatime.execute_guarded_v3('factory_internal_generate');` |

Retired duplicate clocks remain registered for institutional history but are enforced inactive:

- `ct-software-factory-tick-v2`
- `ct-factory-surface-binding-sync-v4`

Additional controls now in production:

- `pentatime.executor_factory_dispatch_v3()`
- Factory recovery re-enters only through `pentatime.execute_guarded_v3(...)`.
- A bounded contention deferral is not mislabeled as a completed recovery.
- Lower-generation scheduler mutations are rejected.
- Same-generation behavior mutations are rejected.
- PentaSELF monotonic contracts supersede stale continuity and dispatch commands.
- Scheduler reconciliation uses `cron.alter_job` in place and preserves job identity, database, and username.
- Intentionally inactive desired jobs are continuously enforced inactive.
- `penta_self.reconcile_factory_continuity_v6()` performs targeted convergence.
- PentaSELF V4 evaluates all registered surgery classes and fails closed on an unknown handler.
- Recent successful execution plus zero failures remains valid across safe `DEFERRED_CONTENTION` outcomes.

## Production migrations

The following migrations were applied to CrownThrive production and mirrored into this repository under their original migration versions.

| Version | Migration | Lines | Bytes | Production SHA-256 |
|---|---|---:|---:|---|
| `20260829192450` | `pentaself_factory_continuity_v6_deadlock_elimination` | 299 | 16,948 | `856c4b7fb14b99c23120599f41717cae116c5c54c3b26e08dd250ffeaf5aba78` |
| `20260829193130` | `factory_continuity_v6_scheduler_generation_fence` | 163 | 8,650 | `809c4834251d38783c625725245faf2fb206392445f34b18b08bb769263b9dc6` |
| `20260829193230` | `pentaself_v4_permanent_repair_evaluator` | 207 | 13,247 | `ce5c73f3b9dc5a3bee551791886df474df9a79e7fd374c0ec8ee271a689690fc` |
| `20260829193504` | `factory_continuity_v6_monotonic_contracts_reconciler` | 141 | 8,845 | `1a0ab2dd01d8a12dd699062538f06cbb77c47bf75edf1f1423560a12daa62e9a` |
| `20260829193729` | `pentaself_v4_factory_continuity_v6_certification_semantics` | 189 | 11,098 | `57e2b35665233790008536559a82765b4d9e2f3e917bdd7da99de137312481fa` |
| `20260829193856` | `scheduler_permanence_v2_preserve_job_owner_fields` | 77 | 4,361 | `450841cedabfc8e879614c1bbb67ee6a0aefab054142873fac5ec38d207db561` |
| `20260829194019` | `scheduler_permanence_v2_enforce_inactive_desired_state` | 102 | 5,784 | `9af66c69bd8e82110263ebf815e21259f6f2f584f04ef5c2788f2bb41d529d6` |

A larger intermediate migration was rejected atomically because it attempted to record evidence under an unregistered capability key. PostgreSQL rolled back that transaction completely. No partial state from that attempt entered production.

## Execution proof

- Guarded dispatch completed successfully.
- Guarded continuity completed successfully.
- Internal generation safely returned `DEFERRED_CONTENTION` while the shared write lane was occupied instead of deadlocking.
- Continuity, dispatch, and generation each reported zero operation failures.
- The targeted factory reconciler returned `VERIFIED` / `ready=true`.
- Active guarded dispatch jobs: 1.
- Active duplicate factory jobs: 0.
- Shared write-lane operations: 4.
- Active raw factory jobs: 0.
- Scheduler permanence readback: 186 checked, 186 healthy, 0 failed.

## PentaSELF certification

| Field | Value |
|---|---|
| State | `CERTIFIED_PRODUCTION` |
| Ready | `true` |
| Certification receipt | `bfbf8527-608f-46d4-8e84-ae96aecdc14b` |
| Certification cycle | `681b3716-c101-4a14-990d-490a4b2b9b8d` |
| Evidence SHA-256 | `f3595c3b183feef21ab40c2d322dd6c71924c4587d5a2d1b3479b3fac21b78c0` |
| Baseline | `2026-08-29T19:35:04.062861Z` |
| Certified | `2026-08-29T19:41:03.738689Z` |
| Factory concurrency failures since baseline | 0 |
| PentaSELF V4 present | true |
| Factory permanent repairs verified | true |

All desired-state layers matched the guarded command at certification time:

- Institutional scheduler desired state
- PentaSELF required-job state
- PentaSELF critical-cron state
- PentaSELF permanent-cron state
- PentaSELF monotonic desired-state contract

## DAIL lineage

| Field | Value |
|---|---|
| Sequence | `287254` |
| Event ID | `0fd05e54-b52b-45b6-9303-137ea4bbdd09` |
| Event type | `pentaself.factory-continuity.v6.certified` |
| Entity | `self_certification:ct.penta.factory-continuity.v6` |
| Source system | `PentaSELF` |
| Entity version | `4.0.0` |
| Authority basis | `founder-directive:2026-08-29:fix-upgrade-self-certify` |
| DAIL payload SHA-256 | `c2b821d7378b1f81e3c1144e7fa67fbf96d33f0723da28fa19d15a2618381852` |
| DAIL event hash | `4c68a513973d330881b20563d19f311fff634b4fbbb399e330419892fb4bff66` |
| Anchor state | `unanchored` |
| Signature reference | `null` |
| Created | `2026-08-29T19:41:03.739383Z` |

The DAIL record is internally cryptographically hashed and chained. It is not represented as externally signed, chain-anchored, or legally notarized.

## Scope and separate conditions

This certificate covers the software-factory continuity control plane. It does not certify unlimited workload capacity or resolve every unrelated PentaSELF HOLD.

Observed separately during the incident:

- Factory workload pressure: 24 active builds against configured capacity 2, with a candidate queue of 107 and 6 held items.
- Other global PentaSELF conditions remained outside this repair, including a pending DAIL terminal projection, a Locticians exact-state mismatch, and a fail-closed PentaOFAC provider-async handler gap.

Those conditions do not invalidate the V6 continuity certificate, but they must not be silently represented as globally resolved.

## Source convergence

- Repository: `crownthrive1/CrownThrive-OS`
- Branch: `pentaself/factory-continuity-v6-20260829`
- Branch base: `3505e445f7c61d3e28a2226280a37234761ee6fd`
- Seven production migration bodies copied under their original versions
- Production migration line counts match the repository files: 299, 163, 207, 141, 189, 77, 102
- No credentials, secret values, or raw provider evidence are included in this packet
