# PentaDND Architecture

## Scoped maintenance state

```mermaid
stateDiagram-v2
    [*] --> REQUESTED
    REQUESTED --> PREFLIGHT
    PREFLIGHT --> REDUNDANCY_READY: identity + authority + topology pass
    PREFLIGHT --> ACTIVE: read-only planning when redundancy is not yet verified
    REDUNDANCY_READY --> ACTIVE: bounded execution allowed
    ACTIVE --> DRAINING
    ACTIVE --> FAILED_SAFE: invariant violation
    DRAINING --> VERIFYING
    VERIFYING --> RELEASED: readback pass
    VERIFYING --> HOLD: incomplete evidence
    HOLD --> PREFLIGHT: evidence or repair supplied
    FAILED_SAFE --> VERIFYING: repair receipt supplied
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

## Virtual network

```mermaid
flowchart LR
    IN[Provider / Penta / Persona / Factory / Site] --> EDGE[PentaEdge\nedge gateway]
    EDGE --> ROUTER[PentaRoute\nvirtual router]
    ROUTER --> SW1[PentaWire switch\nHOT]
    ROUTER --> SW2[PentaWire switch\nWARM]
    ROUTER --> SW3[PentaWire switch\nCOLD-A]
    ROUTER --> SW4[PentaWire switch\nCOLD-B]
    SW1 --> Q[PentaQueue\nlease + fencing]
    Q --> X[Bounded executor]
    X --> V[PentaCertify\nindependent readback]
    V --> DAIL[DAIL receipt]
    DAIL --> CENSUS[PentaCensus + Cookie]
    HEALTH[PentaSELF / PentaHealth] --> ROUTER
    LOAD[PentaLoad / PentaBalancer] --> ROUTER
    TIME[PentaTime / PentaCrons] --> Q
    DND[PentaDND] --> ROUTER
    DND --> Q
```

## Hourly convergence sequence

```mermaid
sequenceDiagram
    participant Clock as PentaCrons
    participant DND as PentaDND
    participant Discovery as PentaDiscovery
    participant Census as PentaCensus
    participant Planner as PentaPlanner
    participant Factory as PentaFactory/PentaVergence
    participant Certify as PentaCertify
    participant DAIL as DAIL
    participant Mail as PentaMailer

    Clock->>DND: begin(scope, TTL, context)
    DND->>DND: verify four-line state
    DND->>Discovery: read changes
    Discovery->>Census: discovery Pentas
    Census->>Planner: reconciled gaps/HOLDs
    Planner->>Factory: bounded closure objectives
    Factory->>Certify: artifacts + receipts
    Certify->>DAIL: independent evidence
    Planner->>DAIL: exact next_phase
    DAIL->>Mail: completion projection
    Mail-->>DAIL: delivery receipt
    DAIL->>DND: closure evidence
    DND->>Clock: release lease + cursor
```

## 3×3 view inside every line

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

These are views of one stable entity and one DAIL lineage, not nine sources of authority.

## Failure rules

- No ambiguous mutation automatically retries.
- No ordinary DND lease suppresses P0 security, health, evidence-integrity or economic-finality alerts.
- No lease exists without TTL, fencing, rollback and release verification.
- No redundancy line is promoted without health, authority and readback evidence.
- No run completes without an exact next phase and email disposition.
- No historical record is silently deleted or rewritten.
