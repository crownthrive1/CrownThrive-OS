# PentaContext™ — Production Context & Memory Plane

**System key:** `penta.context`  
**Version:** `1.1.0`  
**State:** `PRODUCTION`  
**Authority ceiling:** `D2`  
**Public exposure:** `false`  
**Runtime:** `edge:penta-context@2;rpc:public.penta_context_query_v1;queue:public.penta_context_ingest_queue_v1`

## Purpose

PentaContext is CrownThrive's canonical scoped context, operational-memory, and retrieval plane. It ingests, normalizes, redacts, deduplicates, queues, retains, retrieves, and proves contextual information across approved Penta systems, brands, corridors, repositories, databases, provider adapters, documents, messages, events, and other sources.

PentaContext is **evidence and operational memory, never authority**. Context may inform routing, diagnostics, builds, certification packets, command-center views, and agent execution, but it never manufactures credentials, permissions, governance approval, legal authority, provider-write authority, money movement, or D3 effects.

## Automated production contract

PentaContext v1.1 provides:

- exact `scope_key` isolation;
- source provenance and trust tiering;
- `public`, `internal`, `confidential`, and `restricted` classifications;
- ingest-time and pre-queue email, SSN, bearer-token, API-key, password, token, and credential-like redaction;
- recursive secret-key redaction in JSON metadata;
- SHA-256 source/fingerprint hashes and idempotent record deduplication;
- durable idempotent ingest queue with priority;
- one-minute PentaMation queue worker;
- exponential retries capped at one hour and explicit dead-letter state;
- append-only enqueue/ingest/process/query/maintenance/dead-letter receipts;
- full-text + tags + importance + confidence + recency retrieval;
- bounded context packs with explicit character budgets;
- expiry and automated tombstoning every 15 minutes;
- queue/backlog health in the canonical health function;
- service-role-only database and Edge access;
- RLS with explicit deny policies for `anon` and `authenticated`.

## Acquisition boundary

PentaContext does **not** perform arbitrary URL/provider fetching. That would create an SSRF/credential/authority boundary inside the memory plane. External and provider acquisition remains the responsibility of governed **PentaFetch, PentaIngest, PentaSync, PentaCredentials, and certified provider adapters**. Those systems feed PentaContext through `enqueue` or bounded synchronous `ingest`.

This separation lets PentaContext remain continuously ingestible without becoming a second provider-control plane.

## Runtime surfaces

### Edge adapter

`penta-context` v2 accepts server-to-server `POST` requests only. The function performs an exact constant-time comparison against the Edge runtime `SUPABASE_SERVICE_ROLE_KEY`; ordinary public or authenticated-client credentials are rejected.

Allowed actions:

| Action | Backing RPC | Effect |
|---|---|---|
| `health` | `penta_context_health_v1()` | Records + queue operational health |
| `queue_status` | `penta_context_queue_status_v1(...)` | Scoped or aggregate queue state |
| `query` | `penta_context_query_v1(...)` | Build a bounded context pack |
| `ingest` | `penta_context_ingest_v1(...)` | Synchronous governed ingestion |
| `enqueue` | `penta_context_enqueue_v1(...)` | Durable automated ingestion path |

Worker execution and maintenance are intentionally not exposed through the Edge adapter; PentaMation/pg_cron owns those clocks.

### Database objects

- `public.penta_context_sources_v1`
- `public.penta_context_records_v1`
- `public.penta_context_receipts_v1`
- `public.penta_context_ingest_queue_v1`
- `public.penta_context_status_v1`
- `public.penta_context_ingest_v1(...)`
- `public.penta_context_enqueue_v1(...)`
- `public.penta_context_process_queue_v1(...)`
- `public.penta_context_query_v1(...)`
- `public.penta_context_queue_status_v1(...)`
- `public.penta_context_health_v1()`
- `public.penta_context_maintenance_v1()`

## Retrieval model

PentaContext v1 deliberately has no vector-extension dependency. Retrieval is deterministic and portable across the current Postgres runtime:

`score = 0.55(text) + 0.10(tags) + 0.15(importance) + 0.10(confidence) + 0.10(recency)`

Every query enforces exact scope, active source, non-expired/non-tombstoned records, classification ceiling, optional full-text/tags, maximum result count, and character budget. A future semantic/vector ranker may enhance scoring but may never weaken those hard boundaries.

## Automation

| Workflow | Schedule | Purpose |
|---|---|---|
| `penta.context.ingest-worker` | `* * * * *` | Process up to 50 queued context jobs; retry/dead-letter failures |
| `penta.context.maintenance` | `*/15 * * * *` | Tombstone expiry and refresh health evidence |

Queue jobs transition through `queued -> processing -> completed`, or `retry -> ... -> dead_letter`. Queue content and metadata are redacted **before persistence**, so retries do not retain the original sensitive material.

## Security boundary

PentaContext is internal infrastructure. Context storage, queue, and receipt tables have RLS enabled, explicit client-deny policies, and no table access for `anon` or `authenticated`. Context RPC execution is withheld from those roles. `service_role` is the database runtime principal granted context execution/access.

The Edge function uses custom service-role authentication even though platform JWT verification is disabled for that function. This is intentional: the function body requires the exact service-role bearer value and rejects every other credential.

Never place real provider secrets, private keys, passwords, or credentials in PentaContext. Redaction is defense in depth; PentaCredentials/PentaVault remain the credential custody authority.

## Production evidence

### v1.0 base canary

Verified synchronous ingest, dedupe, content/metadata redaction, retrieval, cross-scope isolation, classification ceiling, append-only receipts, client denial, and indexed foreign keys.

Production receipt SHA-256: `1e47ec8fd0a190a663c0c6b1cf17490d87c798e3281022dc2d2553e2f090a01e`

### v1.1 automation canary

Verified durable enqueue, duplicate enqueue collapse, redaction at queue persistence, worker completion on attempt 1, zero retry/dead-letter, provenance-backed retrieval, zero pending backlog, and active one-minute scheduler.

- Queue job: `d7b68b25-af01-4cab-8207-c91051397646`
- Context record: `f9652520-aac3-4ecb-99cb-74da8a025c65`
- Fingerprint: `e2cab0771d685af3258ff7cd040838aa64a8e86c123cd3b7ba7475d5394beb50`
- Query output SHA-256: `0caae31cbbdd52f8b925cf342ac87c3772796876c170c04341f4dd4f79a363b0`
- Production receipt SHA-256: `b05577014efc06fa2f07f7ea9c175e14b5d43f2b45b3c61cd464a2cad2579dd5`
- Edge v2 artifact SHA-256: `4b8902e1d639e9a80d3e9f028cac2bb26662658ff5a547af210514f76fc3d212`

## Integration rules

All Pentas may consume PentaContext through an approved internal adapter. Callers must provide exact scope, least-needed classification ceiling, source provenance, and preserve returned fingerprints/provenance in evidence packets. High-throughput/event-driven producers SHOULD use `enqueue`; bounded interactive workflows MAY use synchronous `ingest`.

PentaRoute routes context requests; PentaQuery/PentaSearch/PentaRead consume bounded query results; PentaIngest/PentaSync feed observations; PentaCache preserves original scope/classification; PentaCertify consumes receipts; PentaReports/PentaNotifs surface health/incidents; PentaDocs documents the contract; PentaNurture maintains source freshness; PentaCredentials remains credential authority.

## Failure semantics

Fail closed for invalid scope/classification/source, unauthenticated callers, invalid content/budget, RPC rejection, or insufficient provenance for an authority-bearing downstream decision. An empty query is valid and must never be filled using cross-scope or higher-classification context.

## Rollback

Rollback is D2 and receipt-preserving: stop consumers, unschedule queue/maintenance clocks, preserve evidence, revoke runtime access, remove Edge only after consumers detach, and mark the registry rolled back. Do not delete production receipts or institutional history.
