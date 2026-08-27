# Penta Organic Control Plane

**Version:** 1.1.0<br />
**Deterministic source state:** finite assessment, tri-directional routing, duplicate/freshness rejection, fsync JSONL hash-chain replay, bounded learning, and sanitized projection logic are implemented and controlled-tested<br />
**Current branch state:** repository convergence and unit-failover behavior is implemented and controlled-tested; provider acceptance/readback remains pending<br />
**Live cross-repository Actions binding:** `HOLD` pending provider execution and readback<br />
**Live Command Center deployment:** `HOLD` pending deployment and readback<br />
**Infrastructure failover certification:** `HOLD` pending restoration, cutover, and failback evidence

The organic control plane models CrownThrive OS as a resilient institutional body. It observes health, load, cost, capacity and redundancy; routes signals to the correct system; learns bounded operating trends; grows under demand; recedes safely under low utilization or cost pressure; and preserves a nonzero continuity reserve.

| System | Role |
| --- | --- |
| PentaBrain | Assesses weak, strong and broken organs and emits bounded dispositions. |
| PentaSpine | Maintains an ordered, append-only fsync JSONL hash chain and rejects corrupted replay; external backup/replication remains separately governed. |
| PentaNerves | Ingests identified internal/external signals, rejects stale/future/duplicate input, and routes it to the appropriate organ or governance branch. |
| PentaHealth | Classifies whole-system health and recovery need. |
| PentaLoad | Measures demand and utilization. |
| PentaBalancer | Restores redundancy, sheds load and recommends bounded growth. |
| PentaCosts | Detects cost pressure and recommends controlled recession; it cannot move money. |
| PentaBody | Produces the sanitized Command Center projection payload; payload generation is separate from live Command Center deployment. |

## State separation

The organic control plane keeps implementation, test, persistence, provider binding, deployment, and failover certification as independent facts.

| Dimension | Current public-safe state |
| --- | --- |
| Deterministic assessment and routing | Implemented; controlled positive, negative, load, finite-value, freshness and idempotency tests pass on the exact candidate revision. |
| Runtime event integrity | Hash-chain verification and tamper rejection are implemented. |
| Durable PentaSpine continuity | Local fsync JSONL persistence and restart replay are controlled-tested; external replication, backup custody and deployed consumption remain `HOLD`. |
| Repository convergence and unit failover | Implemented and controlled-tested; authenticated provider binding and child readback remain `HOLD`. |
| Cross-repository GitHub Actions identity/credential binding | `HOLD` pending live provider execution and exact readback. |
| Command Center payload generation | Deterministic sanitized payload contract present. |
| Live Command Center deployment | `HOLD` pending deployment and consumption readback. |
| Cold infrastructure recovery and silent emergency failover | `HOLD`/unknown publicly until exact restoration, cutover, and failback evidence exists. |

A unit test, generated payload, configured route, public fallback, repository merge, or green workflow proves only that exact surface. None of them independently certifies infrastructure failover or creates authority.

## Identity amendment

Institutional routing uses `vault_id` plus a `sha256` public-key fingerprint. IP addresses are transport metadata, never identity. Private keys, mnemonics, passwords, raw secrets and raw signature bodies are prohibited from public source, signals, evidence and Command Center projections. Cryptographic signing and key custody remain external Vault/PentaCredentials responsibilities.

## Governance routing

- amendment candidates → PentaLegislature;
- adjudication cases → PentaJudicial;
- authorized execution → PentaExecutive;
- system health → PentaBrain;
- capacity/load → PentaBalancer;
- cost pressure → PentaCosts;
- security events → PentaSecure.

Unknown governance signal types fail closed. Routing does not equal approval; each destination applies its own authority and evidence rules.

## Survival and learning rules

- no critical organ may recede below the configured reserve-capacity floor;
- redundancy below two becomes a restoration disposition;
- broken organs are quarantined and recovered instead of silently ignored;
- learning is observational and cannot self-authorize code, governance, provider writes, training-data reuse or money movement;
- every promotion of a learned rule or model requires separate testing and certification;
- PentaSpine integrity failure is included in the sanitized projection and blocks trustworthy continuity claims; live Command Center visibility requires separate deployment/readback.

The Command Center payload contract is `ct.command-center.organic-health.v1`. It exposes only sanitized organ health, utilization, disposition, counts and evidence hashes.

## Repository convergence integration

Repository information moves in three bounded directions:

- **upward:** sanitized repository observations enter through PentaNerves, are ordered through PentaSpine, assessed by PentaBrain, and summarized by PentaBody;
- **downward:** an independently authorized disposition may enter the PentaRoute/PentaFactory/pull-request path for the exact repository scope; and
- **lateral:** repositories exchange versioned contracts, attestations, compatibility results, and readback receipts through PentaFederation/PentaInterOps.

“Caught up” means required contract and policy alignment plus exact-node validation/readback. It does not mean duplicating the authority repository's complete tree, exposing restricted implementation, bypassing repository-native review, or allowing a child to self-activate.

See [Repository Convergence Control Plane](/automation/repository-convergence-control-plane), [Repository Family and Federation](/technology/repository-family-and-federation), and [Repository Resilience and Failover](/technology/repository-resilience-and-failover).

Private repository coordinates, private heads, credentials, recovery storage locations, and silent emergency-route details do not belong in this public record.
