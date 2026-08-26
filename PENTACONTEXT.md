# PentaContext™ — Production Context & Memory Plane

**System key:** `penta.context`  
**Version:** `1.0.0`  
**State:** `PRODUCTION`  
**Authority ceiling:** `D2`  
**Public exposure:** `false`  
**Runtime:** `edge:penta-context@1;rpc:public.penta_context_query_v1`

## Purpose

PentaContext is the canonical CrownThrive context, operational-memory, and retrieval plane. It gives the Penta mesh one bounded mechanism for ingesting, normalizing, redacting, deduplicating, retaining, retrieving, and proving contextual information across systems, brands, corridors, repositories, databases, provider adapters, documents, messages, events, and other approved sources.

PentaContext is **evidence and operational memory, never authority**. Retrieved context can inform routing, planning, diagnostics, build decisions, certification packets, command-center views, and agent execution, but it can never manufacture credentials, permissions, governance approval, legal authority, provider-write authority, money movement, or D3 effects.

## Production contract

PentaContext v1 provides:

- exact `scope_key` isolation;
- source provenance and trust tiering;
- `public`, `internal`, `confidential`, and `restricted` classifications;
- ingest-time email, SSN, bearer-token, API-key, password, token, and credential-like redaction;
- recursive secret-key redaction in JSON metadata;
- SHA-256 source and fingerprint hashes;
- idempotent deduplication by `(scope_key, fingerprint_sha256)`;
- append-only ingest/query/maintenance receipts;
- full-text + tag + importance + confidence + recency retrieval;
- bounded context packs with explicit character budgets;
- expiry and automated tombstoning;
- service-role-only database and Edge access;
- RLS with explicit deny policies for `anon` and `authenticated`;
- PentaMation workflow registration and a 15-minute maintenance clock;
- a security-invoker status projection for internal observability.

## Runtime surfaces

### Edge adapter

`penta-context` v1 accepts server-to-server `POST` requests only. Its custom authentication performs an exact comparison against the Edge runtime `SUPABASE_SERVICE_ROLE_KEY`; ordinary public or authenticated-client credentials are not accepted.

Allowed actions:

| Action | Backing RPC | Effect |
|---|---|---|
| `health` | `penta_context_health_v1()` | Read operational health |
| `query` | `penta_context_query_v1(...)` | Build a bounded context pack |
| `ingest` | `penta_context_ingest_v1(...)` | Normalize, redact, dedupe, persist, and receipt context |

Maintenance is intentionally not exposed through the Edge adapter. It is executed by the internal scheduler.

### Database objects

- `public.penta_context_sources_v1`
- `public.penta_context_records_v1`
- `public.penta_context_receipts_v1`
- `public.penta_context_status_v1`
- `public.penta_context_ingest_v1(...)`
- `public.penta_context_query_v1(...)`
- `public.penta_context_health_v1()`
- `public.penta_context_maintenance_v1()`

## Retrieval model

PentaContext v1 deliberately has no vector-extension dependency. Retrieval is deterministic and portable across the current Postgres runtime:

`score = 0.55(text) + 0.10(tags) + 0.15(importance) + 0.10(confidence) + 0.10(recency)`

The query path always enforces:

1. exact scope match;
2. active source;
3. not tombstoned;
4. not expired;
5. requested classification ceiling;
6. optional full-text and tag filters;
7. maximum record count and total character budget.

A future semantic/vector lane may be added as a ranking enhancement, but it must never weaken these hard boundaries or become a source of authority.

## Automation

PentaMation workflow: `penta.context.maintenance`  
Cron job: `penta-context-maintenance-v1`  
Schedule: `*/15 * * * *`

Each maintenance cycle:

1. tombstones expired context records;
2. emits an append-only maintenance receipt;
3. refreshes PentaContext health evidence in `penta_system_registry`;
4. leaves authority at `D1` for maintenance effects and never performs provider writes, money movement, or D3 effects.

## Security boundary

PentaContext is internal infrastructure. The three storage/receipt tables have RLS enabled, explicit client-deny policies, and no table access for `anon` or `authenticated`. RPC execution is withheld from those client roles. `service_role` is the only database runtime principal granted context execution/access.

The Edge function uses custom service-role authentication even though platform JWT verification is disabled for that function. This is intentional: the body performs the stronger exact secret match and rejects every credential that is not the runtime service-role secret.

Never put a service-role key, provider secret, bearer token, webhook secret, password, private key, or other credential in this repository or in PentaContext content. The redactor is defense in depth, not a replacement for secret custody.

## Canary and production evidence

The production canary verified all of the following on 2026-08-26:

- ingest succeeded;
- duplicate ingest collapsed to the original context ID;
- email and API-key-like content were redacted before retrieval;
- nested secret/token metadata values were redacted;
- full-text retrieval returned the expected provenance-backed record;
- a different scope returned zero records;
- a `public` classification ceiling returned zero `internal` records;
- receipt mutation was rejected by the append-only guard;
- all context foreign keys are indexed;
- the 15-minute cron job is active;
- `anon`/`authenticated` have neither context-table reads nor query-RPC execution;
- `authority_created=false` across the context path.

Production receipt SHA-256:

`1e47ec8fd0a190a663c0c6b1cf17490d87c798e3281022dc2d2553e2f090a01e`

Edge deployment artifact SHA-256:

`aad10bddf1dec0e00072b6bcfe90f111f1dae4d63af0ae8065974546ddb90585`

## Integration rules

All Penta systems may use PentaContext through an approved internal adapter. Callers MUST:

- supply their own exact scope;
- state the least classification ceiling needed;
- attach source provenance on ingest;
- avoid credentials and secrets in source content;
- treat retrieved records as context/evidence only;
- preserve the returned fingerprint/provenance when context is used in an evidence packet;
- use authoritative systems of record for writes and decisions that create external effects.

PentaRoute may route context requests; PentaQuery/PentaSearch/PentaRead may consume bounded query results; PentaIngest/PentaSync may feed approved observations; PentaCache may cache only within the original scope/classification boundary; PentaCertify may consume receipts as evidence; PentaReports/PentaNotifs may surface health and incidents; PentaDocs may document the contract; PentaNurture may maintain source freshness; PentaCredentials remains the credential authority and PentaContext must never replace it.

## Failure semantics

Fail closed when:

- a scope is absent or invalid;
- a classification ceiling is invalid;
- content exceeds the ingest limit;
- the caller is not service-role authenticated;
- the database RPC rejects an operation;
- provenance is insufficient for a downstream authority-bearing decision.

An empty query result is not an error and must never be replaced with cross-scope or higher-classification context.

## Rollback

Rollback is a controlled D2 operation:

1. disable `penta-context` consumers;
2. unschedule `penta-context-maintenance-v1`;
3. preserve/export production receipts and any required evidence;
4. revoke runtime access;
5. remove the Edge adapter;
6. drop PentaContext functions/view/tables only after dependent consumers are removed;
7. mark `penta.context` retired/rolled-back in `penta_system_registry` rather than deleting institutional history.

Do not delete production receipts during rollback.
