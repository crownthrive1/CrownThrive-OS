# PentaRouter V1 Master Ledger

**Ledger ID:** `ct.ledger.pentarouter.v1`  
**Effective date:** 2026-09-02  
**Canonical source:** `crownthrive1/CrownThrive-OS`  
**System ID:** `ct.os.pentarouter.v1`

## Asset register

| Asset | Canonical path | State | Gate |
|---|---|---:|---|
| OS topology manifest | `runtime/pentarouter/pentarouter-system.v1.json` | SOURCE_READY | Merge, CI, independent certification |
| Deterministic runtime | `scripts/pentarouter_runtime.py` | SOURCE_TESTED | Exact-head CI |
| Route contract | `contracts/penta/pentarouter-route.v1.schema.json` | SOURCE_READY | Contract review |
| Node contract | `contracts/penta/pentarouter-node.v1.schema.json` | SOURCE_READY | Contract review |
| Survival contract | `contracts/penta/pentarouter-survival.v1.schema.json` | SOURCE_READY | Independent survival certification |
| Runtime skill | `skills/pentarouter-runtime/SKILL.md` | SOURCE_READY | PentaDocs projection |
| Survival skill | `skills/pentarouter-survival/SKILL.md` | SOURCE_READY | PentaDocs projection |
| PentaGreen handoff skill | `skills/pentagreen-stable-product-handoff/SKILL.md` | SOURCE_READY | PentaDocs projection |
| Commercial mesh bridge | `commercialization/routing/mesh-routing.v1.json` | EXISTING + LINKED | Exact-head tests |
| Stable product handoff | `commercialization/pentagreen/pentarouter-stable-product-handoff.v1.json` | PACKAGE_READY / ACTIVATION_HOLD | Rights, pricing, release, fulfillment, entitlement, provider readback |
| CI governance | `.github/workflows/pentarouter-runtime-governance.yml` | SOURCE_READY | GitHub execution |

## Gap closure register

1. **OS-wide hot/warm/cold standard:** closed at source by a single route manifest and deterministic fallback rules.
2. **PentaRouter identity:** closed at source with primary, secondary, and recovery router nodes.
3. **Planes/fabrics/bridges/meshes inventory:** closed at source with machine-readable topology.
4. **Survival contract:** closed at source; production remains gated until exercised and independently certified.
5. **Secret-safe routing:** closed at source with recursive secret-field rejection.
6. **Authority preservation:** closed at source with DAIL, CHLOM, D3 human, wallet, idempotency, and provider boundaries.
7. **Commercial bridge:** linked to the existing COS commercialization mesh; no duplicate commercial router created.
8. **Stable product selection:** closed at package-design level; unstable and provider-dependent offers remain excluded.

## Evidence register

- Local dependency-free unit test suite: `tests/test_pentarouter_runtime.py` — 17/17 passing before branch publication.
- Embedded runtime validation: `python scripts/pentarouter_runtime.py validate --manifest runtime/pentarouter/pentarouter-system.v1.json`.
- Embedded failover self-test: `python scripts/pentarouter_runtime.py self-test --manifest runtime/pentarouter/pentarouter-system.v1.json`.
- GitHub exact-head CI: pending workflow execution after branch publication.
- Independent certification: pending.
- Provider runtime/readback: not asserted by this source package.

## Projection register

| Destination | Disposition |
|---|---|
| GitHub canonical source | Publish through one reviewable PR; no direct-main mutation |
| Google Drive governed master ledger | Append an additive 2026-09-02 entry and preserve prior history |
| ThriveBase runtime registry | Queue after merge and exact-head evidence; do not manufacture provider state |
| PentaDocs/Mintlify | Queue documentation projection after merge |
| PentaGreen | Accept stable-product handoff; activation remains HOLD until economic and provider gates close |

## Commercial candidates

| Product | Stable scope | Excluded claim | Activation |
|---|---|---|---|
| PentaRouter Resilience Standard & Certification Kit | Versioned standards, contracts, manifest, tests, checklist | Managed uptime or provider execution | HOLD |
| PentaRouter Resilience Readiness Audit | Deterministic assessment and evidence report | Certification without independent proof | HOLD |
| PentaRouter Route Receipt SDK | Dependency-free source and contracts | Live provider integration or money movement | HOLD |

This ledger records source production, not production-provider completion. A queued packet, branch, PR, or passing local test is not provider readback and cannot be represented as a live activation.
