# PentaDND™ — Scoped Do-Not-Disturb and Redundancy Control

**Canonical system ID:** `ct.penta.dnd.v1`  
**Program:** `ct.cos.convergence.production.v1`  
**Protocol contract:** `ct.protocol.pentadnd.scoped-maintenance.v1`  
**Authority ceiling:** D2 autonomous; D3 remains human-reserved  
**Lifecycle:** implementation candidate pending independent certification and production readback

## Purpose

PentaDND is CrownThrive COS's scoped do-not-disturb control. It isolates one workstream, repository, provider, scheduler family, release lane, website surface, factory domain, or maintenance claim without unnecessarily placing the entire operating system into global maintenance mode.

PentaDND does not hide failures, manufacture authority, or discard work. It creates an evidence-bearing lease, routes non-critical work away from the protected scope, activates the applicable redundancy path, preserves critical institutional services, and restores normal routing only after independent readback.

## Mandatory preserved services

The following remain available during a scoped DND lease unless an independently approved emergency policy says otherwise:

- DAIL event preservation and checkpointing
- CHLOM identity, rights, policy and evidence evaluation
- PentaSELF, PentaHealth and PentaHeartbeat
- PentaTime, PentaClock, PentaTick, PentaCrons and PentaDispatch
- PentaWire, PentaRoute, PentaQueue, PentaRetry, PentaLoad and PentaBalancer
- PentaCertify, PentaCloser, PentaHelp and incident escalation
- economic finality evidence, credential liveness, security and P0 incident paths

PentaDND may defer ordinary work. It may not suppress P0 health, security, evidence-integrity, money-finality or authority violations.

## Operating states

```text
REQUESTED
   -> PREFLIGHT
   -> REDUNDANCY_READY
   -> ACTIVE
   -> DRAINING
   -> VERIFYING
   -> RELEASED

Any failed gate -> HOLD or FAILED_SAFE
```

Every transition requires a receipt. A DND lease is bounded by `scope_key`, owner identity, reason, TTL, authority ceiling, preserved-service policy, redundancy contract, rollback reference and next-action timestamp.

## Scoped modes

| Mode | Typical use | Effect |
|---|---|---|
| `workstream_isolation` | Long-running COS convergence or research pass | Prevents unrelated jobs from mutating the claimed workstream |
| `repository_isolation` | Migration, PR repair or exact-head certification | Deflects competing writes while reads and independent verification continue |
| `provider_isolation` | Adapter canary, credential repair or provider drift | Routes calls to warm/cold alternatives where certified |
| `scheduler_isolation` | Clock repair or duplicate-clock retirement | Pauses the affected clock family while PentaTime and health controls continue |
| `release_isolation` | Packaging, canary and readback | Freezes the release subject without freezing the entire OS |
| `read_only` | Evidence reconstruction and forensic review | Allows reads while denying scoped mutations |
| `full_maintenance` | Last resort | Requires explicit escalation and must not be the default |

## Four-line resilience topology

PentaDND institutionalizes four operational lines:

```text
HOT PRIMARY
   | normal execution
   v
WARM STANDBY / SHADOW
   | immediate bounded failover
   v
COLD-A LIVING RECOVERY
   | continuously verified, read-only, promotion-tested
   v
COLD-B DISASTER / IMMUTABLE
     delayed or logically isolated, dual-control recovery
```

The lines are representations of the same canonical identities and DAIL lineage. They do not create four sovereign truths.

### Line contracts

- **HOT:** active production execution; current certified state.
- **WARM:** near-current shadow/standby; can assume bounded work after route and health gates pass.
- **COLD-A:** living recovery replica; periodic restore tests; read-only by default; promotion requires verification.
- **COLD-B:** immutable disaster line; delayed, logically isolated or air-gapped where practical; dual-control restore.

## Virtual network primitives

PentaDND uses the existing Penta networking family instead of creating a competing network stack:

| Primitive | Canonical owner | Function |
|---|---|---|
| Virtual switch | PentaWire / PentaMesh | Connects registered nodes and moves bounded traffic between certified lanes |
| Virtual router | PentaRoute | Selects destination by capability, health, authority, queue pressure, cost and locality |
| Tunnel | PentaTun | Provides bounded cross-provider or cross-line transport |
| Edge gateway | PentaEdge | Enforces ingress/egress policy and provider boundaries |
| Load observer | PentaLoad | Measures pressure and available capacity |
| Balancer | PentaBalancer | Redistributes admitted work |
| Queue and lease controller | PentaQueue | Owns claims, leases, fencing and deduplication |
| Retry controller | PentaRetry | Retries transport-safe operations within a budget |
| Circuit breaker | PentaSELF / PentaHealth | Opens a circuit after classified repeated failure |
| Time and schedule authority | PentaTime / PentaCrons | Resolves when work is eligible and which clock owns it |

The virtual switch, router, gateway, line and node records are first-class COS Census entities with stable IDs, health, capacity, authority, current route, evidence age, DAIL lineage and repair route.

## Hourly Sol Ultra convergence pass

The governed hourly pass is `ct.job.cos-convergence.hourly.v1`.

Each pass must:

1. acquire a collision-safe PentaDND lease for its exact claim;
2. verify HOT/WARM/COLD-A/COLD-B readiness for the claimed scope;
3. read PentaDiscovery, PentaCensus, DAIL, CHLOM, PentaWire, PentaSELF, repositories, providers and governed Drive projections;
4. discover and classify new entities, aliases, contradictions and missing bindings;
5. perform only bounded D0-D2 repair that is independently verifiable;
6. preserve old versions and failures; archive or supersede rather than silently delete;
7. write a run receipt and a precise `next_phase` work packet;
8. append the pass to the Sol Ultra guide and machine ledger;
9. queue an email report to `contact@crownthrive.com` through PentaMailer;
10. verify the report and next-phase handoff before releasing the DND lease.

The pass may continue planning when a provider, business-time or authority gate prevents execution. It must not remain idle merely because outbound sending or publishing is gated.

## Email completion contract

Every pass produces one consolidated report containing:

- pass ID and claim
- start and finish timestamps
- sources consulted and their freshness
- entities discovered or changed
- repairs executed
- items archived/superseded/held
- current redundancy state
- DAIL and CHLOM evidence references
- exact next phase
- blockers requiring founder action

Repeated noise is deduplicated. The email is a projection; the DAIL receipt remains authoritative.

## Isolation from interactive chat

A ChatGPT conversation cannot be created or protected by repository code. COS therefore provides an internal isolated execution context:

`ct.context.sol-ultra.pro-hourly.v1`

That context has its own claim, queue, DND lease, evidence lineage, next-phase cursor and completion receipt. It prevents interactive conversation interruptions from changing the machine workstream. A separate Pro chat may be opened manually and bound to that context, but the system context—not the chat window—is the durable authority.

## No-delete and terminology policy

- Historical artifacts are never silently deleted or rewritten.
- Superseded objects retain stable IDs, aliases, dates, evidence and forward pointers.
- Current public terminology uses **Melanated** rather than **Kulture**.
- Historical source-era uses of Kulture remain verbatim inside restricted/history records and are linked to the current Melanated successor identity.
- Secrets, private keys, recovery codes and exploit bodies are represented by custody references and fingerprints, not copied into broad documents.

## Promotion gates

PentaDND is not production-active merely because this contract exists. Promotion requires:

- stable system/component/protocol identities
- CHLOM identity and fingerprint
- PentaCookie and PentaRoute address
- PentaWire connectivity and node registry
- schema and migration review
- scheduler ownership and duplicate-clock proof
- HOT/WARM/COLD-A/COLD-B canaries
- failover and restore drill
- email completion canary
- DAIL receipts and signed evidence
- independent PentaCertify readback
- rollback test
- release provenance and observed production state

## Canonical workflow

```text
observe
  -> claim
  -> PentaDND preflight
  -> redundancy ready
  -> Penta packet
  -> authorize
  -> route
  -> lease
  -> execute or plan
  -> verify
  -> receipt
  -> next phase
  -> email projection
  -> Census/Cookie update
  -> DAIL preserve
  -> release DND
```
