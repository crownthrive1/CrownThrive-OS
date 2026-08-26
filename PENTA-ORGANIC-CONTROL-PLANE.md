# Penta Organic Control Plane

**Version:** 1.0.0
**State:** production for deterministic assessment, routing, continuity evidence and Command Center projection

The organic control plane models CrownThrive OS as a resilient institutional body. It observes health, load, cost, capacity and redundancy; routes signals to the correct system; learns bounded operating trends; grows under demand; recedes safely under low utilization or cost pressure; and preserves a nonzero continuity reserve.

| System | Role |
| --- | --- |
| PentaBrain | Assesses weak, strong and broken organs and emits bounded dispositions. |
| PentaSpine | Maintains ordered, append-only, hash-chained event continuity. |
| PentaNerves | Ingests internal/external signals and routes them to the appropriate organ or governance branch. |
| PentaHealth | Classifies whole-system health and recovery need. |
| PentaLoad | Measures demand and utilization. |
| PentaBalancer | Restores redundancy, sheds load and recommends bounded growth. |
| PentaCosts | Detects cost pressure and recommends controlled recession; it cannot move money. |
| PentaBody | Produces the unified Command Center projection. |

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
- PentaSpine integrity failure is visible to the Command Center and blocks trustworthy continuity claims.

The Command Center contract is `ct.command-center.organic-health.v1`. It exposes only sanitized organ health, utilization, disposition, counts and evidence hashes.
