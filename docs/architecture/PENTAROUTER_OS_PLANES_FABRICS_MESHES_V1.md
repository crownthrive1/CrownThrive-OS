# PentaRouter OS Planes, Fabrics, Bridges, Meshes, and Redundancy Standard V1

**System:** `ct.os.pentarouter.v1`  
**Owner:** CrownThrive, LLC  
**Governance:** CHLOM  
**Commercial packaging:** PentaGreen  
**Economic activation:** ThriveEvergreen / ECAC  
**Source state:** `SOURCE_READY`  
**Production activation:** `HOLD_PENDING_MERGE_CI_INDEPENDENT_CERTIFICATION_AND_PROVIDER_READBACK`

## 1. Institutional whole

PentaRouter V1 is the shared routing and continuity layer above CrownThrive OS planes and below provider-specific adapters. It does not replace working runtimes. It standardizes how control, identity/authority, data, evidence, economic, delivery, and recovery planes exchange work through six fabrics, seven bridges, six meshes, three router nodes, and three support nodes.

The runtime is intentionally provider-neutral and dependency-free. Its output is a deterministic dispatch receipt, not a claim that a provider action occurred.

## 2. Route classes

### Hot

Hot is for low-latency, non-mutating reads, health, catalog resolution, and routing. It allows D0–D1 work, bounded caching, two attempts, and no provider mutation. Failure moves to warm only when the same exact subject and controls can be preserved.

### Warm

Warm is for buffered governed work: writes, rights requests, wallet intents, entitlements, package generation, publication requests, and other side-effect candidates. It requires a principal, idempotency, DAIL PASS, CHLOM PASS, exact source binding, lease/retry limits, rollback or compensation, and authoritative readback. D3 work also requires an exact human-authority reference.

### Cold

Cold is the durable reconciliation, archive, replay, refund/reversal, revocation, evidence, and recovery lane. It requires append-only evidence, independent verification, immutable subject binding, retention, diagnostics, and recovery criteria. A cold failure becomes `HOLD_FAIL_CLOSED`; it never silently moves upward.

## 3. Redundancy behavior

Selection is deterministic: healthy nodes precede degraded nodes, followed by configured priority, available capacity, and node ID. The path is hot → warm → cold → HOLD. Subject identity, source SHA, principal, idempotency, and evidence requirements survive failover. Money movement does not receive automatic fallback authority. Side effects are incomplete until provider readback is bound to the receipt.

## 4. Topology

The canonical machine-readable topology is `runtime/pentarouter/pentarouter-system.v1.json`. It declares:

- seven OS planes;
- six cross-plane fabrics;
- seven source, ledger, MCP, provider, documentation, and PentaGreen bridges;
- execution, data, evidence, commercialization, communications, and recovery meshes;
- primary, secondary, and recovery PentaRouter nodes;
- warm queue, cold ledger, and independent evidence observer nodes.

The existing commercialization mesh remains canonical for commercial operations and is now referenced as the commercial bridge rather than duplicated.

## 5. Contracts

- `contracts/penta/pentarouter-route.v1.schema.json`
- `contracts/penta/pentarouter-node.v1.schema.json`
- `contracts/penta/pentarouter-survival.v1.schema.json`

The survival contract closes the production-capability gap by requiring persistent identity/state, deterministic functions, queues, leases, recovery, evidence, authority enforcement, health behavior, model-off/model-replacement behavior, and restart behavior.

## 6. Runtime and certification

`scripts/pentarouter_runtime.py` validates the manifest, inventories topology, selects routes, rejects secret-bearing requests, exercises deterministic self-tests, and emits secret-free receipts. `.github/workflows/pentarouter-runtime-governance.yml` gates route-source changes with unit tests, manifest validation, and the embedded self-test.

No source artifact may self-certify production. Merge, exact-head CI, independent certification, applicable provider execution, and authoritative provider readback remain separate gates.

## 7. Commercialization

PentaGreen receives only three stable product-shaped assets: the Resilience Standard & Certification Kit, the Resilience Readiness Audit, and the Route Receipt SDK. Managed uptime, production provider execution, wallet execution, incomplete adapters, and unverified integrations are explicitly excluded. Pricing remains deterministic through PentaGreen research and ThriveEvergreen/ECAC; licensing remains CHLOM-controlled.
