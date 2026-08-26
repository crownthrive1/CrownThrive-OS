# PentaGeneration™ — Seven-Generation Continuity System

**System ID:** `ct.pentageneration.v1`  
**Version:** `1.0.0`  
**Canonical owner:** CrownThrive, LLC  
**Runtime state:** operational in ThriveBase as of 2026-08-26  
**Purpose:** preserve CrownThrive institutional truth, rights, culture, recoverability, stewardship context, and succession readiness across a seven-generation horizon.

PentaGeneration is a bounded CrownThrive continuity subsystem. It does not manufacture legal, ownership, founder-reserved, economic, security, or destructive authority. It records and evaluates continuity evidence so future stewards can determine what is current, what is historical, what changed, why it changed, and under whose authority.

## Seven-generation model

| Generation | Code | Stewardship focus | Required continuity outcome |
|---|---|---|---|
| 1 | `G1-ORIGIN` | Origin & Founder Intent | Purpose, authority, canon, provenance, and operating truth are captured outside oral-only memory. |
| 2 | `G2-TRANSFER` | Transfer Readiness | Qualified successors can understand roles, runbooks, decisions, and dependencies. |
| 3 | `G3-RESILIENCE` | Operational Resilience | Critical functions survive founder absence, provider failure, turnover, and platform drift. |
| 4 | `G4-CULTURE` | Cultural Continuity | Cultural Imprint Engine intent, narrative context, community obligations, and ethical boundaries persist. |
| 5 | `G5-ASSETS` | Rights, Capital & Asset Stewardship | IP provenance, licensing, archives, financial rails, and asset custody remain discoverable and governable. |
| 6 | `G6-ADAPTATION` | Adaptive Governance | New technology, markets, and leadership can evolve the institution without severing lineage. |
| 7 | `G7-LEGACY` | Legacy & Regeneration | Future stewards can prove what changed, why, under whose authority, and which invariants were preserved. |

## Continuity assets

The v1 continuity registry tracks these primary asset classes:

- canon and doctrine;
- source code and release history;
- runtime state and recovery evidence;
- rights and intellectual-property lineage;
- Cultural Imprint Engine context;
- institutional documentation and archives;
- PentaBooks publishing canon and edition lineage;
- provider and integration bindings.

Protected evidence, credentials, restricted rights records, private data, and secret implementation details remain outside public documentation.

## Runtime software

ThriveBase contains the PentaGeneration v1 state model:

- `penta_generation_system_state`
- `penta_generation_horizons`
- `penta_generation_assets`
- `penta_generation_bindings`
- `penta_generation_events`
- `penta_generation_handoffs`
- `penta_generation_proofs`

The database also exposes bounded internal evaluators:

- `penta_generation_evaluate_v1(jsonb)`
- `penta_generation_status_v1()`

The authenticated Edge Function `penta-generation` exposes the service contract `ct.pentageneration.v1` and requires JWT verification.

## Continuity score contract

PentaGeneration evaluates seven independent dimensions from `0–100`:

1. governance;
2. archives;
3. succession;
4. rights;
5. operations;
6. culture;
7. recovery.

Classification:

- `90–100`: `continuity_ready`
- `75–89.99`: `bounded_ready`
- `60–74.99`: `at_risk`
- below `60`: `continuity_failure`

A score is evidence about continuity readiness. It is not legal approval, authority, ownership proof, or permission to execute a destructive action.

## Interoperability

PentaGeneration is designed to bind without replacing:

- **ThriveBase** — runtime state, ledgers, proofs, and machine-readable continuity records;
- **CHLOM** — rights, governance, evidence, licensing, provenance, and remedies;
- **Cultural Imprint Engine (CIE)** — cultural meaning, contextual integrity, community obligations, and narrative continuity;
- **PentaBooks** — manuscript, edition, source, and publishing-canon inheritance;
- **PentaFactory** — software-production and framework/version continuity, subject to independent runtime certification;
- **PentaDocs** — current-state documentation, archived superseded states, and machine-readable doctrine;
- **GitHub repository family** — versioned source, review, release, and recovery history.

`declared`, `registered`, and `verified` are distinct binding states. A named integration must not be represented as verified without current evidence.

## Handoff doctrine

A generational handoff is not a transfer of CrownThrive ownership by default. It is a continuity event that must preserve the applicable entity authority, ownership, licensing, rights, governance, and founder-reserved constraints then in force.

Each consequential handoff should carry, at minimum:

- canonical-source proof;
- authority map;
- asset and rights lineage;
- current operating and recovery runbooks;
- archive integrity evidence;
- provider and dependency map;
- continuity evaluation;
- explicit unresolved risks and holds;
- correction and rollback paths.

Corrections append. Superseded doctrine remains discoverable as history. Current truth must never be silently rewritten.

## Completion standard

PentaGeneration considers a continuity transition complete only when the receiving generation can independently locate the governing records, reproduce required recovery procedures, identify rights and authority boundaries, distinguish current from historical state, and validate the required evidence without relying on undocumented personal memory.
