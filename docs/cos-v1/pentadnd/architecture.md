# PentaDND Architecture

## Human view

PentaDND protects one exact scope while the rest of COS keeps operating. It is a bounded maintenance lease, not a global silence switch.

```text
                         FOUNDER / GOVERNANCE
                                 |
                        CHLOM + PentaPolicy
                                 |
             +-------------------+-------------------+
             |                                       |
        PentaDND lease                         PentaSELF health
             |                                       |
             +-------------------+-------------------+
                                 |
                     PentaRoute / PentaWire
                                 |
          +----------------------+----------------------+
          |                      |                      |
      normal path          protected scope        critical path
          |                      |                      |
       execute             drain / defer /         never silenced
                             fail over
```

## Machine view

```mermaid
stateDiagram-v2
    [*] --> REQUESTED
    REQUESTED --> PREFLIGHT
    PREFLIGHT --> REDUNDANCY_READY: identity + authority + topology pass
    PREFLIGHT --> HOLD: failed prerequisite
    REDUNDANCY_READY --> ACTIVE: scope lease acquired
    REDUNDANCY_READY --> HOLD: no safe alternate path
    ACTIVE --> DRAINING: work complete or TTL reached
    ACTIVE --> FAILED_SAFE: invariant violation
    DRAINING --> VERIFYING
    VERIFYING --> RELEASED: independent readback pass
    VERIFYING --> HOLD: readback incomplete
    FAILED_SAFE --> VERIFYING: repair receipt available
    HOLD --> PREFLIGHT: evidence or repair supplied
    RELEASED --> [*]
```

## Four-line resilience

```mermaid
flowchart TD
    H[HOT Primary\nactive certified execution] -->|continuous shadow + readback| W[WARM Standby\nnear-current bounded failover]
    W -->|governed snapshots + evidence| C1[COLD-A Living Recovery\nread-only, restore-tested]
    C1 -->|delayed immutable checkpoint| C2[COLD-B Disaster Immutable\ndual-control restore]

    R[PentaRoute] --- H
    R --- W
    D[PentaDND] --- R
    S[PentaSELF] --- H
    S --- W
    S --- C1
    S --- C2
    L[DAIL lineage] --- H
    L --- W
    L --- C1
    L --- C2
```

All four lines resolve to one COS UUID graph, CHLOM identity lineage and DAIL history. A replica or backup cannot create authority merely by existing.

## 3×3 projection inside each line

```text
LINE
├── HUMAN
│   ├── C_CENTRALIZED
│   ├── D_DECENTRALIZED
│   └── B_BRIDGE
├── MACHINE
│   ├── C_CENTRALIZED
│   ├── D_DECENTRALIZED
│   └── B_BRIDGE
└── HYBRID
    ├── C_CENTRALIZED
    ├── D_DECENTRALIZED
    └── B_BRIDGE
```

The 3×3 projections are presentation and operating views of the same underlying entity, never nine competing records of authority.

## Virtual network model

```mermaid
flowchart LR
    IN[Provider / Agent / Factory / Site] --> EDGE[PentaEdge\nvirtual edge gateway]
    EDGE --> ROUTER[PentaRoute\nvirtual router]
    ROUTER --> SW1[PentaWire switch\nHOT]
    ROUTER --> SW2[PentaWire switch\nWARM]
    ROUTER --> SW3[PentaWire switch\nCOLD-A]
    ROUTER --> SW4[PentaWire switch\nCOLD-B]
    SW1 --> Q[PentaQueue\nlease + fencing]
    Q --> X[Bounded executor]
    X --> V[PentaCertify\nindependent readback]
    V --> DAIL[DAIL receipt]
    DAIL --> CENSUS[PentaCensus + Cookie update]
    HEALTH[PentaSELF / PentaHealth] --> ROUTER
    LOAD[PentaLoad / PentaBalancer] --> ROUTER
    TIME[PentaTime / PentaCrons] --> Q
    DND[PentaDND] --> ROUTER
    DND --> Q
```

## Hourly Sol Ultra pass

```mermaid
sequenceDiagram
    participant Clock as PentaTime/PentaCrons
    participant DND as PentaDND
    participant Discovery as PentaDiscovery
    participant Census as PentaCensus
    participant Planner as PentaPlanner
    participant Factory as PentaFactory/PentaVergence
    participant Certify as PentaCertify
    participant DAIL as DAIL
    participant Mail as PentaMailer

    Clock->>DND: begin(scope, TTL, context)
    DND->>DND: verify HOT/WARM/COLD-A/COLD-B
    DND->>Discovery: read current changes
    Discovery->>Census: discovery Pentas
    Census->>Planner: reconciled gaps/holds
    Planner->>Factory: bounded closure objectives
    Factory->>Certify: artifacts and execution receipts
    Certify->>DAIL: independent result evidence
    Planner->>DAIL: exact next_phase packet
    DAIL->>Mail: completion projection
    Mail-->>DAIL: sent/failed receipt
    DAIL->>DND: closure evidence
    DND->>Clock: release lease + next cursor
```

## Isolation boundary

The durable execution context is `ct.context.sol-ultra.pro-hourly.v1`. A user may work in a separate interactive Pro conversation, but the conversation itself is not the scheduler, queue, lock or source of truth. The context ID, DND lease, Pentas correlation chain and DAIL receipts preserve continuity across chat interruptions.

## Failure rules

- No ambiguous mutation is retried automatically.
- No DND lease suppresses P0 security, health, evidence-integrity or economic-finality alerts.
- No lease is accepted without a TTL and release/verification path.
- No failover line is promoted without current health, authority and readback evidence.
- No completed hourly run is valid without an exact next phase and email-outbox disposition.
- No historical record is silently rewritten or deleted.
