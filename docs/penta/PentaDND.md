# PentaDND™

**Canonical system:** `penta.dnd`  
**Protocol:** `ct.penta.protocol.dnd.v1`  
**Program:** `ct.program.cos-v1.hourly-convergence-dnd`  
**Runtime:** ThriveBase / Supabase schema `penta_dnd`  
**Lifecycle:** Production active with typed HOLDs  
**Authority ceiling:** D2; D3 remains human-reserved

## Purpose

PentaDND is CrownThrive COS V1's **scoped do-not-disturb isolation and continuity protocol**. It protects one bounded workstream from unrelated mutation while essential health, evidence, routing, certification, communications, backup and restore capabilities remain available.

PentaDND does **not** place the entire institution into maintenance mode. It does not manufacture authority. It does not suspend DAIL, PentaSELF, PentaWire, PentaRoute, PentaCertify, PentaMail, PentaBackup or PentaRestore.

Its current protected workstream is:

```text
ct.workstream.cos-v1.deep-discovery
└── ct.workstream.cos-v1.deep-discovery.pro-reasoning
```

The reasoning workstream is an OS-level isolated lane. It is **not a separately created ChatGPT conversation**.

## Core invariant

```text
bounded scope claim
  → DND lease
  → capability preflight
  → HOT/WARM/COLD-A/COLD-B activation
  → one convergence pass
  → signed Pentas
  → DAIL event
  → founder email
  → next phase persisted
  → lease closed
```

No historical record is silently deleted or overwritten. A newer state supersedes an older one through explicit lineage.

## Four-line continuity topology

```text
                              PentaDND
                                 │
                       PentaVRouter Failover
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
      HOT                      WARM                  DUAL COLD
        │                        │                 ┌──────┴──────┐
Live internal runtime      Provider/API          COLD-A       COLD-B
Pentas + DAIL + DB         webhook standby       immutable    independent
current-state readback     bounded failover      evidence     recovery export
```

| Line | Canonical system | Node | Function |
|---|---|---|---|
| HOT | `penta.vswitch.hot` | `node:cos.vswitch.hot` | Primary internal execution and current-state readback |
| WARM | `penta.vswitch.warm` | `node:cos.vswitch.warm` | Provider/API/webhook standby and failover |
| COLD-A | `penta.vswitch.cold-a` | `node:cos.vswitch.cold-a` | Immutable DAIL ledger-lineage checkpoint and exact readback |
| COLD-B | `penta.vswitch.cold-b` | `node:cos.vswitch.cold-b` | Independent broad recovery/export and restore-path validation |

COLD-A and COLD-B are not interchangeable. A broad midnight backup does not automatically satisfy an immutable DAIL ledger-lineage checkpoint.

## Hourly clock

PentaDND reuses the existing canonical founder-report clock. It did not create a duplicate scheduler.

```text
jobname:   penta-mail-state-architecture-hourly-v1
jobid:     832
schedule:  43 * * * *  (UTC)
command:   select public.penta_dnd_hourly_orchestrator_v1();
clock:     ct.clock.penta-dnd.hourly
```

The clock is registered and reconciled across:

- `cron.job`
- `integration_control.scheduler_desired_jobs_v2`
- `penta_self.required_jobs_v1`
- `penta_self.permanent_cron_desired_state_v1`
- `penta_self.critical_cron_state_v2`
- `penta_runtime.crons_v1`
- `pentatime.scheduler_registry`
- `pentatime.clock_registry_v1`
- `pentatime.dail_clock_bindings_v1`
- `integration_control.cos_scheduler_census_v1`

A legacy generation-2 desired-state contract pointed to `cos_v1_hourly_convergence_v1()`. It remains historical evidence. Generation 3 now points to PentaDND and may only be replaced by a later explicit generation.

## Hourly pass behavior

Each UTC hour has one idempotency key. A manual canary and the automatic clock cannot create two passes for the same hour.

Every pass must:

1. lock the hourly pass admission key;
2. resolve the current and next phase;
3. open a scoped DND lease;
4. materialize or refresh PentaDND topology;
5. read all four continuity lines;
6. run bounded convergence and classify failures as HOLDs;
7. emit Planner and isolated-reasoning Pentas;
8. emit continuity repair work when a line is not ready;
9. route pending Pentas;
10. append a chained PentaDND receipt;
11. append the DAIL pass event;
12. create the founder report;
13. enqueue and dispatch the email through PentaMail;
14. persist the following phase;
15. close the lease.

Unrelated failures are contained in the pass rather than leaving a global maintenance condition behind.

## Current phase cursor

Direct ThriveBase readback is authoritative:

```text
pass counter: 1
current phase: identity_alias_reconciliation
next phase:    chlom_did_fingerprint_binding
```

The current 16-phase production catalog is:

1. Identity and alias reconciliation
2. CHLOM DID and fingerprint binding
3. DAIL lineage checkpointing
4. Pentas cookie and route reconciliation
5. Penta roster and component reconciliation
6. Agentic, persona and workforce reconciliation
7. Repository and source-control reconciliation
8. Provider, adapter, API and MCP reconciliation
9. Site, domain and projection reconciliation
10. Product, commerce and entitlement reconciliation
11. Media, music, television and radio reconciliation
12. CIE and cultural-governance reconciliation
13. Factory, framework and release reconciliation
14. Security, policy and authority reconciliation
15. Drive HOT/WARM/COLD mirror reconciliation
16. COS V1 release certification

Older phase catalogs remain historical implementation evidence and are not rewritten to look current.

## First production pass

Pass 1 proved:

- scoped DND without global maintenance;
- all four virtual lines were routable;
- the lease closed and no active lease remained;
- signed Pentas were emitted;
- DAIL recorded the pass;
- the founder email dispatched with provider HTTP 200;
- the automatic 22:43 execution replayed the existing hour instead of duplicating it;
- the next phase was persisted.

Pass state was `complete_with_holds`, not a false unconditional PASS.

## Current typed HOLDs

### COLD-A ledger-lineage freshness

The signed DAIL checkpoint fabric is current and passing. The independent Drive-custodied `ledger_lineage` export is older and requires refresh.

**Route:** `PentaBackup → PentaRestore → PentaCertify`  
**Closure:** fresh export, manifest, byte count, SHA-256, provider/Drive readback and restore-path proof.

### Bootstrap source export

Supabase retained all exact PentaDND migration statements in `supabase_migrations.schema_migrations`. Their byte lengths and SHA-256 values are recorded in the machine manifest.

**Route:** `PentaFactory → PentaRelease → PentaCertify`  
**Closure:** export every exact migration body into repository custody and verify each file against the provider-ledger hash.

Until then, `20260829230000_penta_dnd_provider_ledger_guard_v1.sql` fails closed if the provider ledger is missing or altered. It is not represented as the original bootstrap source.

## Security boundary

PentaDND data is internal:

- forced RLS on all PentaDND tables;
- append-only delete/truncate guards;
- schema/table/function privileges limited to `postgres` and `service_role`;
- generic `anon` and `authenticated` execution removed from all three public wrappers;
- explicit function search paths;
- no raw credential export;
- no money movement;
- no D3 or destructive restore authority.

Public documentation may expose purpose, interface, states and evidence summaries. It must not expose private keys, credentials, protected implementation bodies, raw exploit material or private evidence bodies.

## Runtime tables

```text
penta_dnd.phase_catalog_v1
penta_dnd.programs_v1
penta_dnd.leases_v1
penta_dnd.passes_v1
penta_dnd.line_profiles_v1
penta_dnd.line_state_v1
penta_dnd.receipts_v1
```

## Principal functions

```text
penta_dnd.ensure_topology_v1()
penta_dnd.open_lease_v1(...)
penta_dnd.preflight_v1(...)
penta_dnd.activate_redundancy_v1(...)
penta_dnd.next_phase_v1(...)
penta_dnd.close_lease_v1(...)
penta_dnd.hourly_pass_v1()
penta_dnd.status_v1()
```

Internal public-schema wrappers exist for scheduled/service-role execution only:

```text
public.penta_dnd_hourly_orchestrator_v1()
public.penta_dnd_status_v1()
public.penta_dnd_preflight_v1(...)
```

## Recovery procedure

1. Verify the migration hashes in `docs/penta/manifests/penta-dnd.v1.json`.
2. Run `20260829230000_penta_dnd_provider_ledger_guard_v1.sql` against the current provider ledger.
3. Export exact source with `scripts/export_penta_dnd_migration_ledger.sql`.
4. Rebuild only from byte-verified migration bodies.
5. Confirm the eight systems/nodes and four line profiles.
6. Confirm the hourly job points to PentaDND and all desired-state registries agree.
7. Confirm generation 3 is the latest monotonic clock contract.
8. Confirm anonymous/authenticated execution is false.
9. Run one idempotent canary in a fresh hour.
10. Verify DAIL, Pentas, email, next-phase persistence and lease closure.
11. Verify both COLD paths independently.

## Source-control state

```text
repository: crownthrive1/CrownThrive-OS
base SHA:   9ad01190507f86d0267bf08a4e7322f263fa1ffb
branch:     build/penta-dnd-hourly-convergence-v1-r2-20260829
```

The original empty reservation branch `build/penta-dnd-hourly-convergence-v1` is preserved and was not force-moved or deleted.
