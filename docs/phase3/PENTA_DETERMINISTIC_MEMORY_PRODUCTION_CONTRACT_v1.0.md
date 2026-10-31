# Penta Deterministic Memory Production Contract v1.0

**Contract:** `ct.penta.deterministic-memory.v1`  
**Effective date:** 2026-08-31  
**Owner:** CrownThrive, LLC  
**Canonical OS:** `crownthrive1/CrownThrive-OS`  
**Durable state substrate:** ThriveBase project `tzajnzshmtzjenqulehq`

## 1. Decision

Every current governed Penta identity receives a durable memory namespace and an explicit deterministic survival contract. Memory is allocated according to maturity, family, workload, classification ceiling, and model dependency. The allocation never promotes maturity and never creates credentials, provider permission, certification, rights, financial authority, D3 authority, release authority, or permission to bypass CHLOM, DAIL, PentaAssure, PentaCertify, PentaMerge, PentaCloser, human/founder gates, independent certification, or authoritative provider readback.

“Literal memory” means durable database-backed state with a hard logical-byte quota and a bounded working-set budget. It is not a claim that dedicated physical RAM has been reserved for each Penta. Hidden model context is never accepted as durable institutional memory.

## 2. Two determinism levels

### Strict orchestration determinism

All Pentas use `strict-v1` for identity resolution, canonical input hashing, routing order, authorization inputs, state transitions, retry policy, idempotency, evidence ordering, receipts, replay comparison, checkpoint selection, and recovery behavior.

### Bounded semantic determinism

Pentas that synthesize language, analysis, media, communications, research, or agentic plans use `bounded-semantic-v1`. Their control path remains exact and replayable. Model output is not represented as bit-identical unless the provider contract guarantees that property. Any model-backed replay requires a pinned provider, provider version, model, model version, seed `0`, and temperature `0`. Consequential release still requires independent verification.

PentaBrain uses strict orchestration plus bounded semantic synthesis. This is deliberate: its health thresholds, evidence ordering, retrieval scope, dispositions, and receipts are deterministic, while optional model synthesis remains replaceable and non-authoritative.

## 3. Allocation policy

| Profile | Hard quota | Working set | Typical use |
|---|---:|---:|---|
| `cold-reserved-v1` | 8 MiB | 2 MiB | Specified, candidate, bootstrap, or otherwise non-implemented identities |
| `standard-v1` | 64 MiB | 16 MiB | General production/implemented Pentas |
| `security-v1` | 64 MiB | 16 MiB | Security, trust, governance, and legal evidence |
| `continuity-v1` | 128 MiB | 32 MiB | Recovery, resilience, immune, and surgical care |
| `observability-v1` | 128 MiB | 32 MiB | Health, logging, traces, metrics, body/nerves/spine |
| `knowledge-v1` | 256 MiB | 64 MiB | Context, knowledge, census, semantics, and data custody |
| `intelligence-v1` | 256 MiB | 64 MiB | Research and bounded analysis |
| `brain-v1` | 1 GiB | 256 MiB | PentaBrain institutional memory anchor |

Only `implemented` and `production` identities receive writable hot memory. Every other current identity receives a durable cold reservation and remains non-writable. A new hot identity with no live canonical family fails reconciliation closed. A new cold identity may remain `PROVISIONAL_UNASSIGNED`, but it cannot write memory.

The repository projection currently allocates the OS V1.5 canonical registry. The production reconciler dynamically allocates every current identity in `integration_control.penta_identity_registry_v1`, including canonical `penta.*` members and governed `ct.penta.*` protocol identities. The source registry remains authoritative; the memory fabric is a projection.

## 4. PentaBrain family mesh

PentaBrain remains the active, fail-closed anchor in **Observability & Organic Systems**. It receives read-only, non-authority-expanding family grants for:

1. `OBSERVABILITY_ORGANIC` — family observation and health state.
2. `KNOWLEDGE_DATA` — exact-scope, evidence-backed PentaContext retrieval.
3. `SECURITY_TRUST` — policy, classification, and trust guardrails.
4. `ROUTING_INTEROP` — governed addressability and route evidence.
5. `RESILIENCE_CONTINUITY` — checkpoints, replay, recovery, and cold routes.
6. `INTELLIGENCE_RESEARCH` — bounded analysis.
7. `AUTOMATION_AGENTIC` — bounded orchestration.
8. `SYSTEM_ARCHITECTURE` — topology, identity, and dependency state.
9. `BUILD_RELEASE` — independent verification and release evidence.

Cross-family writes are denied. Family routing remains coordination-only. PentaBrain cannot dispatch specialist work merely because it can read family memory, and memory does not change `specialist_execution_eligible` or PM execution eligibility.

## 5. Durable production objects

Schema: `penta_runtime`

- `penta_memory_namespaces_v1` — one current allocation per live identity, quotas, determinism profile, and survival contract.
- `penta_memory_records_v1` — append-only, hash-chained memory index/payload records.
- `penta_execution_replays_v1` — append-only replay comparison receipts.
- `penta_lifecycle_events_v1` — append-only allocation, append, context, quota, replay, recovery, retirement, and rollback events.
- `penta_memory_family_grants_v1` — PentaBrain’s read-only support-family mesh.
- `penta_memory_census_receipts_v1` — hash-stable allocation snapshots and counts.
- `penta_memory_status_v1` — quota and namespace readback.
- `penta_brain_memory_mesh_status_v1` — family activation/certification readback.

All tables have RLS enabled. `anon` and `authenticated` are explicitly denied. `service_role` receives table `SELECT` only; mutations occur through bounded security-definer functions. Direct service-role inserts, updates, and deletes are revoked.

## 6. PentaContext binding

PentaContext remains the canonical evidence-backed semantic content store. A Penta memory namespace is the exact PentaContext scope key. New durable semantic content must enter through `penta_memory_remember_v1`, which:

1. Locks the target namespace.
2. Verifies self-write, hot maturity, active fail-closed state, classification ceiling, and working-set budget.
3. Ingests through `penta_context_ingest_v1` using exact scope and existing redaction/sanitization.
4. Adds a quota-counted memory record bound to the returned context ID and source SHA-256.
5. Rolls the PentaContext write back if the namespace quota cannot accept the record.
6. Emits hash-chained lifecycle evidence only on the first successful append.

Direct out-of-contract service writes to PentaContext are not considered Penta memory and must not be used to bypass quota or namespace custody.

## 7. Runtime APIs

- `penta_memory_reconcile_v1()` — idempotently allocates all current identities, verifies PentaBrain/family prerequisites, updates metadata, and projects both census planes.
- `penta_memory_append_v1(...)` — self-only append with hard quota, working-set, classification, hash-chain, and full-envelope idempotency checks.
- `penta_memory_remember_v1(...)` — atomic PentaContext ingest plus quota-counted memory binding.
- `penta_memory_read_v1(...)` — self-read, plus PentaBrain read-only access to explicitly granted families.
- `penta_memory_context_query_v1(...)` — exact-scope PentaContext retrieval with classification ceilings and query receipt.
- `penta_deterministic_replay_record_v1(...)` — records `RECORDED`, `MATCH`, or `MISMATCH`; rejects request-hash collisions with a different deterministic envelope.
- `penta_memory_health_v1()` — exact counts, quota violations, coverage, PentaBrain readiness, support-family holds, census convergence, and allocation snapshot SHA-256.

## 8. Census and institutional convergence

Every namespace is projected into:

- `integration_control.penta_census_entities_v1` as `PENTA_MEMORY_NAMESPACE`.
- `pentamocracy.universal_penta_census_v1` as `NONCITIZEN_PENTA_ENTITY` with source kind `penta_memory_namespace`.

The source identity remains the citizen/canonical Penta. Its memory namespace is a noncitizen governed entity and cannot vote, authorize, certify, or act independently. Identity and family registry metadata receive the memory contract, namespace/profile, allocation digest, mesh role, and explicit `authority_expansion=false` markers.

The repository emits `data/penta/deterministic-memory-census.v1.json`, whose content is deterministic and excludes wall-clock fields. It binds source-file SHA-256 values, every canonical assignment, quota, survival contract, and a manifest SHA-256.

## 9. Activation and release truth

The migration requires PentaBrain to already be current, active, implemented/production, and present as `active` in `public.penta_runtime_activations`. It updates that existing activation record; it never inserts or manufactures activation.

Successful migration, health `PASS`, and deterministic canaries establish runtime activation and exact readback. They do **not** establish independent production certification. The health contract therefore always returns:

- `production_certified: false`
- `independent_certification_required: true`

PentaCertify/PentaAssure and the governed release topology remain responsible for current-head independent certification. Provider readback remains evidence, not authority.

## 10. Required acceptance

A release candidate is acceptable only when all of the following are true:

- Repository unit and SQL-contract tests pass.
- Generated repository census has no drift.
- Migration is present in Supabase migration history.
- Current identity count equals current namespace count.
- No current identity is uncovered.
- Writable + cold-reserved counts equal total current identities.
- PentaBrain is `brain-v1`, 1 GiB, active fail-closed, bounded-semantic, version-pinned, and not PM-executable through memory.
- Exactly nine current read-only family grants exist; no cross-family write or authority expansion exists.
- Both census projection counts equal namespace count.
- No quota violation exists.
- Append retry returns `IDEMPOTENT_REPLAY` with the same record digest.
- Replay retry returns `MATCH` for the same result.
- Replay envelope collision is rejected.
- RLS and explicit client-deny policies are present.
- Rollback artifact preserves evidence and removes write capability.

## 11. Containment rollback

`supabase/rollbacks/20260831094500_penta_deterministic_memory_v1.rollback.sql` is non-destructive. It revokes reconcile/write/replay RPCs, appends a rollback lifecycle event, moves all current namespaces to `ROLLBACK_HOLD`, disables family grants, marks census projections held, removes active metadata bindings, and preserves every allocation, record, PentaContext item, receipt, and lifecycle event for recovery and independent assessment.
