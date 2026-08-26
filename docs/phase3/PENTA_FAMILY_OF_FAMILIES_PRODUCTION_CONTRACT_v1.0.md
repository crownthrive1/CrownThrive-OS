# Penta Family of Families™ Production Contract v1.0

**Owner:** CrownThrive LLC  
**Effective:** 2026-08-26  
**Status:** Production institutional-topology control plane  
**Parent:** Penta Family™  
**Machine registry:** `penta/registry/penta-families.v1.json`

## 1. Contract purpose

This contract institutionalizes the Penta Family as a **family of governed operating families**, rather than a flat collection of names. It establishes deterministic discovery, primary-family ownership, cross-family roles, family portals, future-growth enforcement and source-of-truth boundaries.

The contract is additive. It does not replace the machine Penta Family registry, individual child contracts, PentaRoute interoperability, PentaStatus/PentaOD readiness, PentaSerialized continuity, CHLOM, DAIL or human-reserved authority.

## 2. Source reconciliation

The family topology is composed from three independent sources:

1. **Machine family catalogs** — `data/penta/family.registry.json`, every catalog it declares, and every `data/penta/systems*.json` extension exposing a `systems` array.
2. **Technical component registry** — `penta/registry/penta-component-registry.v1.json`, including PentaRoute primitives.
3. **Institutional identity/portal registry** — `PENTA-FAMILY-REGISTRY.md`.

A Penta present in only one layer is still discoverable and therefore must be institutionalized. Presence in a documentation or technical registry does not manufacture machine maturity.

## 3. Identity reconciliation

Penta display forms are normalized by removing trademark marks, punctuation, whitespace, hyphens and underscores and then applying case folding. This reconciles display variations such as `Penta Federation` and `PentaFederation`.

Normalization is not permission to merge semantically distinct identities. `PentaSecure` and `PentaSecurity`, for example, remain separate unless a governing correction explicitly says otherwise.

## 4. Primary-family invariant

Every discovered Penta must resolve to **exactly one primary family**.

Primary-family assignment establishes:

- canonical family portal/story ownership;
- mission context;
- closest operational peers;
- expected family-level handoffs; and
- accountability for documentation/topology completeness.

Primary-family assignment does not alter child maturity, permissions, rights, credentials, provider authority, economic authority, certification or human authority.

A Penta may also have explicit **secondary family roles**. Secondary roles do not create joint ownership of the same decision and do not alter the child's exact authority contract.

## 5. Current family census

The v1 topology establishes fifteen institutional families:

1. Penta System Architecture Family;
2. Penta Routing & Interoperability Family;
3. Penta Transport & Capability Primitives Family;
4. Penta Automation & Agentic Family;
5. Penta Build, Certification & Release Family;
6. Penta Security, Identity & Trust Family;
7. Penta Resilience & Continuity Family;
8. Penta Observability & Organic Systems Family;
9. Penta Knowledge, Semantics & Data Family;
10. Penta Governance, Legal & Institutional Controls Family;
11. Penta Workforce & People Family;
12. Penta Intelligence, Research & Impact Family;
13. Penta Communications & Service Family;
14. Penta Media, Studio & Publishing Family; and
15. Penta Commerce & Economy Family.

The family count is versioned topology. Future families may be added through governed source changes when the estate grows, but existing children are not silently moved without an explicit topology change and continuity evidence.

## 6. Portal contract

Canonical family index:

`/io/pentas/families`

Canonical family route:

`/io/pentas/families/{slug}`

A family portal must expose the registry-defined story, mission, census, status, responsibilities, authority boundary, handoffs, operations, SOP/SLA context, evidence, API/MCP context, recovery, release history, roadmap and support information.

`portal_state=contracted` means the institutional route/payload is defined. It does not prove that a specific frontend has deployed that route.

Individual system portals remain under the existing CrownThrive IO Penta portal standard.

## 7. Future-growth fail-closed rule

A new Penta identity added to any canonical inventory source creates a family-classification obligation.

The family verifier must fail when:

- a discovered Penta has no primary family;
- one Penta has multiple explicit primary families;
- a machine-category fallback matches multiple families;
- a family references an unknown family handoff;
- a required parent family source is missing; or
- portal invariants are invalid.

The failure disposition is `hold_fail_closed`.

This mechanism prevents a new subsystem, recovered historical Penta, capability primitive or technical component from silently entering production architecture without documentation/topology ownership.

## 8. Transport primitive rule

PentaRoute primitives are distinct Penta identities, not aliases of PentaRoute. When a primitive does not have a stronger explicit primary-family assignment, it belongs to the Penta Transport & Capability Primitives Family.

Cross-cutting primitives such as PentaVault, PentaAuth, PentaSign, PentaSnapshot, PentaRollback, PentaCertify, PentaAudit, PentaRelease and PentaBind may have explicit stronger primary-family assignments while retaining their primitive role in PentaRoute.

## 9. Maturity boundary

Machine maturity remains governed by the applicable child system registry. The family topology may report the observed maturity but cannot change it.

Only the parent Penta Family execution rules determine whether a child is execution eligible. Family portal inclusion is not an execution gate bypass.

Technical component state such as `active` is also kept separate from machine-family maturity such as `specified`, `implemented`, `certified` or `production`.

## 10. Cross-family handoff boundary

Cross-family handoffs use exact child machine keys and the Penta interoperability envelope. A family name itself is not a provider action endpoint.

Consequential execution remains subject to, as applicable:

- registered source and target;
- child maturity;
- PentaOD/readiness and heartbeat freshness;
- CHLOM/DAIL authority trace;
- PentaHybrid/human gate;
- PentaCredentials binding;
- PentaCertify/PentaAssure evidence;
- legal, security, privacy, compliance, rights and economic controls;
- provider-specific certification;
- idempotency/rollback/compensation; and
- exact readback/evidence preservation.

## 11. Documentation and story boundary

`PENTA-FAMILIES.md` is the human family index and story. `penta/families/README.md` is the portal/operating implementation guide.

Family narratives explain institutional purpose. They do not overwrite child facts. When a narrative and machine evidence diverge, the machine/source evidence remains authoritative for the exact operational state and the documentation must be corrected.

## 12. Verification

The canonical verifier is `runtime/penta_families.py`.

CI must prove:

- registry/schema JSON parse;
- runtime/test compilation;
- complete multi-source discovery;
- zero unclassified Pentas;
- exactly one primary family per discovered identity;
- representative family assignments;
- registry-layer identity merging;
- no maturity promotion caused by family assignment;
- future unknown Penta rejection;
- duplicate primary-family rejection; and
- complete required family portal sections.

## 13. Production invariant

The canonical invariant is:

> **Penta Family is the umbrella. Penta Families organize the estate. Individual Pentas keep their own truth, maturity, authority and evidence.**

The family-of-families layer exists to improve coherence, discoverability, accountability and scalability. It may never make an unfinished or unauthorized child look more operational than its evidence supports.

## 14. Change control

Changes to inventory sources, family IDs, primary-family membership, fail-closed classification, portal sections or authority invariants are production topology changes and require normal CrownThrive source governance, PentaSerialized continuity where applicable, CI, exact-head review and merge/readback evidence.
