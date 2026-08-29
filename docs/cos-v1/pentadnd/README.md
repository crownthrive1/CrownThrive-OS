# PentaDND™ — Scoped Do-Not-Disturb and Redundancy Control

**System:** `ct.penta.dnd.v1`  
**Program:** `ct.cos.convergence.production.v1`  
**Protocol:** `ct.protocol.pentadnd.scoped-maintenance.v1`  
**Durable context:** `ct.context.sol-ultra.pro-hourly.v1`  
**Authority:** A2 / D2; D3 remains human-reserved  
**Current release posture:** implementation candidate pending migration, canaries, independent certification and production readback

## Purpose

PentaDND protects an exact workstream, repository, provider, scheduler family, release subject, factory lane or website surface without placing the entire CrownThrive COS into maintenance mode. It creates a bounded, evidence-bearing lease; drains or deflects noncritical traffic; activates the best certified redundancy route for that scope; preserves critical institutional services; and releases only after readback.

PentaDND does **not** hide errors, grant authority, suppress P0 alerts, delete history or create a competing network stack.

## Preserved services

DAIL, CHLOM, PentaSELF, PentaHealth, PentaHeartbeat, PentaTime, PentaClock, PentaTick, PentaCrons, PentaDispatch, PentaWire, PentaRoute, PentaQueue, PentaRetry, PentaLoad, PentaBalancer, PentaCertify, PentaCloser, PentaHelp, PentaPay and PentaCosts remain observable during scoped DND. P0 security, evidence-integrity and economic-finality paths cannot be silenced by an ordinary lease.

## Lease states

```text
REQUESTED
  -> PREFLIGHT
  -> REDUNDANCY_READY
  -> ACTIVE
  -> DRAINING
  -> VERIFYING
  -> RELEASED

failed gate -> HOLD or FAILED_SAFE
TTL elapsed -> EXPIRED
```

Every lease carries a scope, owner, correlation ID, TTL, fencing token, authority ceiling, preserved-service policy, redundancy snapshot, rollback reference and release proof.

## Scoped modes

| Mode | Use | Default effect |
|---|---|---|
| `workstream_isolation` | Long-running Sol Ultra/COS convergence | Prevent unrelated writers from changing the claimed scope |
| `repository_isolation` | Migration, PR repair, exact-head certification | Deflect competing writes; preserve reads and verification |
| `provider_isolation` | Adapter canary or provider incident | Route through certified alternate lines |
| `scheduler_isolation` | Clock repair or duplicate-clock retirement | Pause only the affected clock family |
| `release_isolation` | Packaging, canary, production readback | Freeze the release subject, not COS |
| `read_only` | Discovery, evidence reconstruction, forensics | Permit observation and planning; deny scoped mutation |
| `full_maintenance` | Last resort | Requires explicit escalation and is never the default |

## Four operational lines

```text
HOT PRIMARY
    active certified execution
        |
        v
WARM STANDBY
    near-current shadow and bounded failover
        |
        v
COLD-A LIVING RECOVERY
    continuously verified, read-only by default, restore-tested
        |
        v
COLD-B DISASTER IMMUTABLE
    delayed/logically isolated, dual-control recovery
```

All four lines resolve to one COS identity graph, CHLOM lineage and DAIL history. Replication does not manufacture authority.

Each line also carries the existing 3×3 projection:

```text
HUMAN / MACHINE / HYBRID
        ×
C_CENTRALIZED / D_DECENTRALIZED / B_BRIDGE
```

## Virtual network ownership

PentaDND reuses and institutionalizes the existing Penta network family:

| Primitive | Owner | Function |
|---|---|---|
| Virtual switch | PentaWire / PentaMesh | Connect registered nodes inside each line |
| Virtual router | PentaRoute | Select by capability, health, authority, load, cost, locality and evidence age |
| Tunnel | PentaTun | Bounded cross-provider/cross-line transport |
| Edge gateway | PentaEdge | Ingress, egress, provider and data-class enforcement |
| Load observer | PentaLoad | Capacity and pressure measurement |
| Balancer | PentaBalancer | Redistribute admitted work |
| Queue/lease/fencing | PentaQueue | Collision-safe claims and deduplication |
| Retry | PentaRetry | Transport-safe retries only, within budget |
| Circuit/health | PentaSELF / PentaHealth | Classify repeated failure and open circuits |
| Time/clock | PentaTime / PentaCrons | Eligibility, cadence and clock ownership |

All switches, routers, gateways, links and lines are first-class COS Census entities with stable IDs, health, capacity, route address, authority, evidence age, DAIL lineage and repair route.

## Hourly Sol Ultra pass

The hourly job is `ct.job.cos-convergence.hourly.v1`.

Every pass must:

1. Acquire a collision-safe PentaDND lease for the exact claim.
2. Verify HOT, WARM, COLD-A and COLD-B state.
3. Read PentaDiscovery, PentaCensus, DAIL, CHLOM, PentaWire, PentaSELF, repositories, providers and governed Drive projections.
4. Discover and classify entities, aliases, contradictions and missing bindings.
5. Perform only reversible, independently verifiable D0–D2 repair; otherwise continue in read-only planning mode.
6. Archive or supersede; never silently delete or rewrite history.
7. Write a run receipt and an exact `next_phase` packet.
8. Append the pass to Sol Ultra and its machine ledger.
9. Queue and deliver one consolidated report to `contact@crownthrive.com` through PentaMailer.
10. Verify report disposition, Census/Cookie updates and closure evidence before releasing the lease.

The database PentaCrons clock is primary at minute 17. A GitHub Actions warm fallback checks at minute 23, delivers queued email, and runs only when the primary clock is stale.

## Completion email contract

Each report contains pass ID, claim, timestamps, sources/freshness, discoveries, repairs, archives/supersessions/HOLDs, four-line state, DAIL/CHLOM evidence, exact next phase and founder attention. Repeated noise is deduplicated. The email is a projection; the DAIL receipt remains authoritative.

## Isolated Pro execution context

Repository code cannot create a new ChatGPT conversation. COS therefore uses `ct.context.sol-ultra.pro-hourly.v1`: its own scope lease, queue, cursor, receipts and next-phase chain. A separate Pro chat may be opened manually and bound to that ID, but the COS context—not the chat window—is durable authority.

## Preservation and terminology

- No silent delete or overwrite.
- Prior states, failures and branches remain evidence with successor pointers.
- Current projections use **Melanated** instead of **Kulture**.
- Historical source-era Kulture wording remains verbatim in history/restricted records and points to the Melanated successor identity.
- Secrets, private keys, recovery codes and exploit bodies are represented by custody references, digests, rotation state and proof-of-possession—not copied into broad documentation.

## Promotion gates

PentaDND becomes production-active only after:

- COS UUID, CHLOM identity, DID and fingerprint binding;
- current PentaCookie, PentaRoute address and PentaWire connectivity;
- migration and append-only receipt verification;
- duplicate-clock proof;
- HOT/WARM/COLD-A/COLD-B provider/readback canaries;
- failover and restore drills;
- PentaMailer send and delivery/readback canary;
- signed DAIL evidence;
- independent PentaCertify result;
- rollback proof; and
- observed production state.

## Canonical flow

```text
observe -> claim -> DND preflight -> redundancy/read-only decision
-> Penta -> authorize -> route -> lease -> execute or plan
-> independent verify -> receipt -> exact next phase -> email projection
-> Census/Cookie update -> DAIL preserve -> release DND
```
