---
title: "CHLOM Open Infrastructure Strategy"
description: "Open-first, provider-portable infrastructure architecture for local development, evidence, cryptographic anchoring, observability, and future scale."
---

# CHLOM Open Infrastructure Strategy

## Governing decision

CHLOM SHALL be developed open-first and locally first. Paid infrastructure providers are optional acceleration, redundancy, capacity, and managed-service partners; they SHALL NOT become CHLOM's institutional source of truth or an irreplaceable protocol dependency.

This page specifies target architecture and roadmap. It does not claim that every component below is already deployed or production-certified.

## Architectural principle

CHLOM owns its protocol, schemas, evidence formats, policy logic, adapters, cryptographic conventions, recovery procedures, and CrownThrive-specific intellectual property. Infrastructure vendors provide replaceable compute, storage, networking, RPC, observability, or managed operations.

```text
CrownThrive ID
      ↓
CrownThrive IO / MCP
      ↓
CHLOM Core
      ↓
DAIL + canonical event envelope
      ↓
Cryptographic Evidence Engine
  ├─ SHA-256 digests
  ├─ deterministic canonicalization
  ├─ signatures
  ├─ Merkle leaves / roots
  └─ evidence bundles
      ↓
Evidence Storage
  ├─ PostgreSQL / THIVEBASE operational records
  ├─ S3-compatible private evidence
  └─ IPFS/Kubo content-addressed public artifacts
      ↓
Anchor Router
  ├─ local development adapter
  ├─ Polkadot/Substrate adapter
  ├─ EVM adapter
  └─ future governed adapters
```

Sensitive source material, credentials, personal information, confidential contracts, and restricted evidence SHALL NOT be indiscriminately published on public chains or IPFS. Public anchors should normally contain cryptographic commitments and references sufficient for verification without exposing the protected payload.

## Open-source reference stack

Initial development SHOULD prefer:

- Polkadot SDK/Substrate for research, local development networks, runtime experimentation, and future CHLOM pallets where justified.
- Kubo/IPFS for content-addressed evidence artifacts, CIDs, DAGs, and portable proof distribution.
- PostgreSQL for authoritative operational records and transactional state.
- OpenBao for an open-governance secrets/key-management path and future reduction of single-vendor vault dependency.
- OpenTelemetry, Prometheus, and Grafana for telemetry, health, heartbeat, node, agent, API, and anchor monitoring.
- Docker/Compose for the local developer environment; Kubernetes only when operational scale justifies its complexity.
- Caddy, Nginx, or Traefik for local/self-hosted ingress and TLS as appropriate.
- S3-compatible object storage for evidence packages, exports, backup, and recovery.

Every dependency requires license, security, maintenance, version, SBOM, provenance, and upgrade review before production adoption. Open source does not mean zero operational cost or zero governance burden.

## Local-first build stages

### Stage L0 — workstation laboratory

Build a reproducible Docker-based CHLOM laboratory capable of generating canonical events, hashes, signatures, Merkle roots, evidence bundles, local persistence, and verification receipts without requiring a paid blockchain provider.

### Stage L1 — local development network

Add a local Polkadot SDK/Substrate development network and adapter tests. No token launch, validator economics, public-chain dependency, or production decentralization claim is implied.

### Stage L2 — controlled test environment

Move the exact reproducible stack to low-cost controlled compute. Add encrypted backups, secrets management, observability, restore drills, rate limits, incident handling, and multiple evidence-storage targets.

### Stage L3 — external anchor pilots

Test independently replaceable Polkadot and EVM anchor adapters. Measure latency, transaction cost, reliability, verification portability, and recovery behavior before selecting production routes.

### Stage L4 — redundant production infrastructure

Only after CHLOM Core is proven: introduce redundant RPC/node providers, CrownThrive-operated nodes where economically justified, multi-region evidence replication, stronger key custody, service-level objectives, capacity planning, and provider exit tests.

### Stage L5 — advanced CHLOM runtime

Evaluate CrownThrive-specific pallets/modules for assets, rights, licenses, provenance, authority, evidence, attestations, and remedies. Adoption requires a demonstrated advantage over conventional infrastructure and applicable legal/security review.

## Portability gate

No provider is certified as a foundational CHLOM dependency unless CHLOM can export its records, rotate credentials, replace the provider, restore from CrownThrive-controlled evidence, and independently verify historical commitments.

## Monetization boundary

CrownThrive may commercialize its original CHLOM services, schemas, adapters, workflows, managed deployment, verification, licensing automation, compliance tooling, templates, education, developer tooling, certification, support, and hosted offerings subject to applicable upstream licenses. Upstream open-source code SHALL retain required notices and license obligations. CrownThrive proprietary protocol/IP SHALL be clearly separated from upstream software.

## Phase alignment

Phase 2 documents, reconciles, and governs this architecture. Phase 3 builds the executable institutional core and local reference implementation. Phase 4 connects CrownThrive platforms through certified adapters. Phase 5 may introduce externally scalable licensing, developer products, advanced CHLOM infrastructure, and paid institutional-grade redundancy after the evidence supports it.
