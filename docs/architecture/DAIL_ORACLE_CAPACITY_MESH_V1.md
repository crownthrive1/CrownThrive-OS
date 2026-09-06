# DAIL Oracle Capacity Mesh v1

**Status:** Production verified  
**System key:** `ct.dail.oracle-capacity-mesh.v1`  
**Contract:** `ct.contract.dail.oracle-capacity-mesh.v1`  
**Scheduler:** `ct-dail-oracle-capacity-mesh-v1`  
**Assignment:** `ct.assignment.dail-oracle-capacity-mesh-v1`  
**Assignment ID:** `b5728fd9-6f45-4e14-9b5b-c04ec7214adf`

## Architecture decision

The Oracle Capacity Mesh adds local execution capacity around the existing Four-Part DAIL Cursor. It does not create another ledger, chain, canonical writer, permission system, or authority source.

```text
One canonical CHLOM DAIL chain
            |
     Four-Part DAIL Cursor
            |
   500K Continuity Lock
            |
 Head / Continuity / Archive
            |
 PentaGas + PentaBalancer
            |
 +----------+-----------------------+
 |          |                       |
Cursor      Demo Sandbox donor      Oracle Capacity Mesh
MeshAssist                          (five bounded identities)
                                       |
                         signed cookie + attributed append
                                       |
                           one canonical append fabric
```

The oracles read bounded local state and append attributed terminal evidence through the existing canonical DAIL function. They do not write directly around that function.

## Oracle identities

| Oracle | Oracle ID | Penta node | Primary donation class |
|---|---|---|---|
| PentaDAIL Evidence Oracle | `ct.oracle.penta-dail` | `ct.penta.dail` | Verification |
| PentaCertify Oracle | `ct.oracle.penta-certify` | `ct.penta.certify` | Verification, then route fallback |
| PentaWire Oracle | `ct.oracle.penta-wire` | `ct.penta.wire` | Route |
| PentaCensus Oracle | `ct.oracle.penta-census` | `ct.penta.census` | Route |
| PentaDiscovery Oracle | `ct.oracle.penta-discovery` | `ct.penta.discovery` | Route |

Native oracle work always preempts donation. One hundred percent means one hundred percent of verified idle capacity, not one hundred percent of provider CPU or total oracle capacity.

## Activation and release

- Activate at `100,000` pending DAIL routes.
- Enter `LOCK_OVERCLOCK` at `500,000` or more.
- Operate in `RECOVERY_OVERCLOCK` from `100,000` through `499,999`.
- Release at `80,000` or fewer.
- Keep the scheduler installed as a dormant monitor after release.

The lower release threshold creates hysteresis and prevents rapid activation/deactivation oscillation.

## Idle-donation formula

```text
DonationPct = 100
when NativeQueue = 0
and Health = healthy
and HeartbeatAge <= 900 seconds
and CapacityAvailable > 0
and OracleState = active
and PendingRoutes >= 100000
otherwise DonationPct = 0
```

## Verification-aware route throttle

```text
RouteBase = 600 in LOCK_OVERCLOCK
RouteBase = 300 in RECOVERY_OVERCLOCK

VerificationFactor =
  0.25 when VerificationLag >= 100000
  0.50 when VerificationLag >= 20000
  1.00 otherwise

OracleRouteLimit =
  floor(min(RouteBase, CapacityAvailable * 12) * VerificationFactor)
```

This protects sequential verification as route throughput rises.

## Per-cycle bounds

- Scheduler: every 20 seconds.
- Maximum oracle donors: 5.
- Maximum route donors: 4.
- Maximum verification donors: 1.
- Maximum route limit per oracle: 600.
- Maximum verification limit per oracle: 5,000.
- Maximum PentaBalancer pressure score: 45.
- Maximum session use: 60%.
- Maximum lock waiters: 1.
- Maximum running jobs: 12.
- Core network hops: 0; the mesh is local to ThriveBase.
- Canonical writers: exactly 1.

## Reader-writer contract

Each successful oracle slice:

1. Reads bounded route, continuity, verification, health, queue, heartbeat, and capacity state.
2. Creates a compact execution-decision digest. This is operational evidence, not hidden reasoning.
3. Executes one bounded route or verification slice.
4. Publishes a signed Penta cookie with oracle, node, run, slice, work class, digest hash, and result counters.
5. Appends an oracle-attributed terminal DAIL event through the canonical append function.
6. Reads back the exact event ID, sequence, event hash, and evidence SHA-256.
7. Rolls back the affected slice when PentaGas settlement, cookie signing, or terminal readback fails.

## Production proof

Production deployment event:

- Event ID: `13a60111-008a-44a3-90b6-b1dd86333ff9`
- Sequence: `2,585,930`
- Event hash: `fd47af9c4a2baf4ed2f6ed7212019923f5e371102d1b539b5528ac3de914fc37`
- Payload SHA-256: `27afb927293dbbd04f6852bd7c06d2ebc62cc13bc247ce1354fd1143eea26236`

Production canary evidence SHA-256:

`4debcb290ac052a403a9a0d867c37a98346e962914969ce71408e110900968f5`

Representative bound run:

- Run ID: `2bf54fd9-074d-412b-a012-eeddc6d3fc37`
- Four route donors and one verification donor.
- 1,200 routes delivered.
- 5,000 events verified.
- Five signed cookies.
- Zero route failures.
- Terminal DAIL event: `c67c7c25-14fe-4220-ae41-2bbfa1f2fcfe`.
- Terminal sequence: `2,583,126`.

## Initial observation

Whole-stack movement from the deployment observation window:

- Pending routes: `509,644` to `495,744`, a reduction of `13,900`.
- Verification lag: `48,913` to `35,492`, a reduction of `13,421`.
- Five-minute route net: `-6,273`.
- Fifteen-minute route net: `-13,652`.
- One-hour route net: `-42,762`.

Direct Oracle Mesh attribution during that window:

- 3,000 routes delivered.
- 15,000 events verified.
- 13 signed cookies.
- Zero route failures.

The whole-stack movement includes Cursor, local MeshAssist, Demo Sandbox donor, Oracle Mesh, new arrivals, and concurrent workers. Only the direct Oracle Mesh counters are attributed to Oracle Mesh.

## Observability corrections

This release also corrected three status defects:

- MeshAssist separates latest attempt, scheduler wrapper state, and latest completed material run.
- Cursor separates latest attempt, no-op, pressure/contention deferral, material run, and bound-complete run.
- Continuity status separates stored exact count, exact observation time, exact staleness, current estimate, estimate source, estimate time, and estimate staleness.

## Authority boundary

The Oracle Capacity Mesh has no permission to create a license, payment, token, customer entitlement, rights grant, business approval, or independent institutional truth. PentaGas remains nonfinancial internal capacity accounting. Available gas never substitutes for authority.
