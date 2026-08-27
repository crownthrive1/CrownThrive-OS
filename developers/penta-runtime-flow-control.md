# Penta Runtime Flow-Control Capability Pack

`crownthrive.penta.runtime-flow-control.v1` version `1.0.0` is one nonvoting capability pack under the existing PENTA family. It is a provider-neutral, in-memory `CONTROLLED_TEST` reference. It has no durable-store binding, no external-effect adapter binding and no enabled external effects. It is not a ninth institutional framework, a new authority service, an independent certifier, a production runtime or a provider deployment claim.

The pack binds to the canonical component registry at `penta/registry/penta-component-registry.v1.json` version `1.5.0`; it does not redefine registry roles or axes:

| Runtime member | Canonical identity | Axis | Registry relationship and canonical role |
| --- | --- | --- | --- |
| PentaQueue | `penta.route` / `ct.penta.route.v3` | interoperation | `PentaQueue` primitive under PentaRoute, the routing and delivery umbrella governing distinct route primitives |
| PentaLoad | `penta.load` / `ct.penta.load.v1` | execution | Component for demand, capacity and utilization measurement |
| PentaBalancer | `penta.balancer` / `ct.penta.balancer.v1` | execution | Component for redundancy restoration, load shedding and bounded capacity growth |
| PentaCosts | `penta.costs` / `ct.penta.costs.v1` | authority | Component for cost-pressure detection and controlled recession recommendations without money movement |

PentaQueue therefore has no standalone `penta.queue` component identity. PentaCosts is the only cost-family component identity in this pack; the helper classes below are implementation members, not new registry identities. The institutional `penta.cost` / `PentaCost` system recorded in `data/penta/systems.extensions.operations-workforce.json` remains separate: this pack does not alias, supersede, replace or certify it.

The pack composes four bounded responsibilities:

| Member | Exact responsibility | Explicit non-responsibility |
| --- | --- | --- |
| PentaQueue | Bounded priority admission, immutable payload custody, idempotency, leases, fencing, retry and dead-letter state | Does not authorize or execute provider writes |
| PentaLoad | Freshness-gated capacity evidence and backpressure | Stale or absent observations never increase throughput |
| PentaBalancer | Deterministic selection among current eligible routes | Does not create route eligibility or provider authority |
| PentaCosts | Pre-lease internal estimate-unit ceilings, reservations and accounted-use status | No payment, settlement, pricing, transfer, treasury or accounting effect |

## Deterministic claim sequence

Each claim uses this fixed control order:

1. select due queued jobs by descending priority, admission time, sequence and job ID;
2. validate the worker-bound receipt for the job's exact scope and current time;
3. exclude missing, disabled, future-dated or expired load snapshots;
4. return backpressure if every fresh route is full;
5. select the least-utilized route, using a stable job/route hash only to break equal-load ties;
6. reserve the job's internal estimate units against the route ceiling;
7. reserve one fresh route-capacity slot;
8. create the lease and increment its fencing token.

Any failed precondition leaves the job unleased. If a later step fails, earlier runtime reservations are released before the failure returns.

## Authority and effect boundary

An authority receipt is an evidence pointer to authority resolved elsewhere. Registering it does not manufacture the authority. Every receipt has an exact subject, one or more exact scopes, a not-before time, an expiry, a durable evidence reference, an issuer ID and an environment ID. The receipt store accepts only its configured issuer allowlist and exact runtime environment.

The runtime calculates `evidence_binding_digest` over the receipt ID, subject, ordered scopes, validity bounds, evidence reference, issuer and environment. That digest detects field changes inside this reference runtime; it is not a signature, does not authenticate the issuer and does not provide production authority. Wildcard scope is not supported.

All time validity uses an exclusive upper bound: a receipt is valid only while `not_before <= now < expires_at`, a load snapshot only while `observed_at <= now < observed_at + ttl_seconds`, and a lease only while `now < lease_expires_at`. The effective lease expiry cannot exceed the receipt expiry. Revocation or expiry causes `PentaFlowControl.validate_claim` to fail closed.

`validate_claim` validates controlled-test custody only and explicitly returns `effect_may_be_considered: false` and `external_effects_enabled: false`. It never authorizes an external effect. Any future provider operation would still need a separately governed, certified adapter, credentials, exact operation binding, effect-specific approval, read-after-write evidence and rollback or compensation evidence.

Failure and lease-expiry paths remain available to release runtime reservations and preserve evidence. They do not erase the original claim or authority lineage.

## Delivery, retry and fencing

The contract is at-least-once. Idempotency prevents the same admission key from silently describing different work, while a monotonically increasing per-job fencing token prevents an expired worker from completing a later claim. Admission deep-detaches and freezes the JSON payload; the claim exposes that same immutable payload custody rather than a mutable queue reference.

`priority`, `max_attempts`, timestamps and every internal-unit input reject Python booleans even though `bool` is an `int` subclass. Priority is `0..100`; `max_attempts` is `1..100`; every unit or quantity is `0..9223372036854775807`. Retry count is bounded at admission, and exhaustion moves the job to `dead_letter`.

An active claim must exactly reproduce the job ID, worker ID, selected route, fencing token, lease expiry, attempt, immutable payload, authority receipt ID and cost reservation ID stored for the lease. Its reservation must also exactly reproduce the reservation ID, job ID, fence, route and admitted estimate units. Any mismatch fails closed before completion or failure mutation.

Completion requires the exact active claim plus an immutable result mapping, an explicit operation, a bounded non-negative quantity, the exact immutable `PentaRate`, an explicit usage-evidence reference and the current time. The exact rate must contain the operation. The append-only usage record binds the operation, quantity and rate digest to the job, route, fencing token, reservation ID and result digest. An exact replay returns the immutable prior response; a replay that changes the claim, result or usage inputs is a conflict.

Rate books are configured before execution. Completion rejects an unconfigured digest, a conflicting object that reuses an existing rate-book ID/version, a future-effective rate, a completion timestamp before admission, or metered units above the active admitted reservation. A worker-supplied object cannot silently become configured rate evidence.

`implementation_verified` means only that the caller supplied a local result while the claim remained valid. It is not `certified`, `production`, `write_verified`, provider readback, release acceptance, a governance vote or a quorum contribution.

## PentaCosts family

The operational cost family uses non-negative signed 64-bit integer estimate units and fails closed on overflow:

| Member | Contract |
| --- | --- |
| PentaRate | Immutable versioned rate book mapping exact operations to integer units |
| PentaMeter | Bounded append-only, idempotent usage records bound to the exact rate-book digest, job, route, fence, reservation and result digest |
| PentaBudget | Atomic per-route ceiling, reservation, release and accounted-use status |
| PentaCostLedger | Append-only operational reservation entries; not accounting or treasury truth |
| PentaForecast | Advisory integer projection using a documented ceiling-mean method; never spend authority |

`PentaCosts` remains the compatibility facade for the existing `configure`, `reserve`, `finalize`, `release` and `status` API. It composes PentaMeter, PentaBudget, PentaCostLedger and PentaForecast behavior without changing current flow-control callers.

A route must have an explicit PentaBudget ceiling, including a zero ceiling where zero-cost execution is required. Estimated units are reserved before lease creation, released on retry/expiry and moved to accounted runtime-use status after valid completion. The budget readback exposes ceiling, reserved, accounted and available estimate units; these are operational status fields and never spend, accounting or treasury authority. Budget mutations and operational ledger appends are protected by runtime locks, and repeated reservation/usage/ledger keys must reproduce the same request or fail as conflicts.

PentaRate objects canonicalize their operation ordering, carry an exact version and evidence reference, and expose a stable digest. A prior rate object cannot be mutated. PentaMeter records quantity and the estimate produced by that exact digest; it does not claim a provider charge occurred.

PentaForecast uses integer ceiling-mean projection and returns `advisory_only: true` and `authorizes_spend: false`. It cannot call budget reservation, provider, pricing, payment or treasury surfaces.

These values are operational guardrails only. They are not currency, Crown Credits, invoices, prices, spend authorization, a general ledger or evidence that a provider charge occurred. The rate book, meter, budget, operational ledger and advisory forecast are implemented only as provider-neutral controlled-test contracts in this version.

## Bounded retention and consolidated exception reporting

Queue and idempotency history, route budgets, cost reservations, metered usage, operational ledger entries and exception evidence all have explicit retention ceilings. A full store raises `RetentionCapacityError` before accepting work that would drop or overwrite required history. Multi-item lease reaping preflights exception capacity for the entire batch. Retention rotation requires separate governed durable custody; this reference implementation never silently prunes evidence.

Raw exception evidence is append-only within the bounded reference ledger. The consolidated report first redacts bearer tokens, password-like values, email addresses and signed URL/query credentials, then normalizes volatile UUID, long hexadecimal and numeric fragments to calculate stable redundant-event fingerprints. It represents every retained input record, preserves exact raw and group counts, and emits SHA-256 digests of every original message and evidence reference. Reported values are redacted views; the unredacted values remain only in the bounded internal evidence record. Consolidation reduces notification repetition without replacing or leaking source evidence.

Exception class and code are also untrusted. Reports never emit their original values; they emit constant redacted labels plus SHA-256 digests. Runtime mappings and sequences remain immutable while using JSON-native container subclasses, and every schema-bound object exposes a detached `to_dict()` representation where applicable. CI validates actual emitted objects—not hand-written fixtures—against the Draft 2020-12 schema.

## Operational readback

`PentaFlowControl.report()` is an immutable operational projection, not a certification receipt. It reports:

- the exact `CONTROLLED_TEST` lifecycle and false durable-store, adapter, external-effect, issuer-authentication, certification, quorum, vote and money-movement flags;
- resident and retained queue counts, configured retention ceilings and state counts;
- load snapshot and local in-flight counts;
- the configured authority environment and issuer, receipt and revocation counts, while declaring no issuer authentication or production authority;
- route-budget, reservation-state, accounted-unit, reserved-unit, operational-ledger and usage-meter counts and ceilings; and
- redacted exception groups and one redacted record per retained exception, with original-value digests and retention capacity.

Absent readback or a full evidence/history store is a hold condition; neither is interpreted as success.

## Durability and provider adapters

The Python implementation is a deterministic reference module and controlled-test surface. Its in-memory state is not a multi-process durable production queue. A production adapter must preserve the same ordering, immutable payload custody, idempotency, issuer/environment receipt binding, exclusive validity intervals, freshness, full claim/reservation binding, cost-before-lease, usage binding, fencing, retry, dead-letter, retention and redacted-report invariants in a transactional durable store.

External providers remain replaceable. An adapter must declare its operation, credentials, rate ceiling, data class, idempotency behavior, retry behavior, readback, rollback/compensation and exact certification evidence. A provider response never changes the pack's authority boundary.

## Recovery

`PentaFlowControl.stop()` irreversibly pauses new admission for that runtime instance and returns an immutable stop receipt. Existing leased work may still use the bounded failure path, and expired leases may still be reaped, so reservations and evidence are not stranded. Restoring admission requires constructing the prior reviewed source version as a new isolated runtime; there is no in-place self-resume or external-effect path in this controlled-test version. Accounted estimate units and historical receipts are not rewritten to make a failed run appear successful.

The controlled-test SQL migration preserves the pre-change `penta.route` registry row and digest in `component_registry_rollback_v1` before reconciling legacy aliases to the canonical primitive model. It installs no cron or effect consumer. Any later activation must reference an immutable release baseline that binds exact head, migration, technical, security, independent-verifier and rollback evidence; every execution assertion rechecks GitHub-provider containment.

Canonical machine records:

- `developers/manifests/penta-runtime-flow-control.v1.json`
- `schemas/penta/runtime-flow-control.schema.json`
- `penta/runtime/flow_control/core.py`
