# Penta Families™ — Family of Families Institutional Index

**Status:** Production institutional topology and portal contract  
**Parent:** Penta Family™  
**Owner:** CrownThrive, LLC  
**Control surface:** CrownThrive IO  
**Documentation surface:** PentaDocs  
**Machine registry:** `penta/registry/penta-families.v1.json`  
**Verifier/portal renderer:** `runtime/penta_families.py`

## Why a family-of-families exists

Penta Family has grown beyond a flat list of services. CrownThrive now has operating-system components, routing primitives, factories, security controls, continuity systems, workforce systems, media systems, economic systems, intelligence systems, institutional controls and reusable low-level capabilities that all use the Penta identity.

A flat census answers **what exists**. The family-of-families model answers the harder institutional questions:

- What larger mission does each Penta serve?
- Who are its closest operational relatives?
- Where should an operator enter the system?
- Which family owns the primary responsibility when multiple families participate?
- What evidence and authority boundaries survive a handoff?
- Which portal tells the complete story instead of forcing operators to reconstruct it from scattered files?
- What happens when a new Penta is named but not institutionalized?

The answer is a governed topology beneath Penta Family. Every discovered Penta receives exactly one **primary family**, may have explicit secondary/cross-family roles, keeps its independent maturity and authority state, and receives a family portal context.

## Canonical invariants

```text
PENTA FAMILY PRODUCTION ≠ EVERY PENTA PRODUCTION
FAMILY ASSIGNMENT ≠ AUTHORITY
FAMILY ASSIGNMENT ≠ MATURITY PROMOTION
PORTAL CONTRACTED ≠ FRONTEND DEPLOYED
INTEROPERABLE ≠ AUTHORIZED
READY ≠ PERMITTED
DOCUMENTED ≠ CERTIFIED
CONNECTED ≠ PROVIDER-WRITE ELIGIBLE
```

The family topology is deliberately **fail-closed**. `runtime/penta_families.py` discovers Penta identities from the machine family catalogs, the technical component registry, the institutional family registry and the PentaRoute primitive census. Any discovered identity with no unambiguous primary family makes the family verifier fail.

This means future expansion is automatically visible. A newly created Penta cannot silently live outside the institutional model.

## Portal architecture

Family index:

```text
/io/pentas/families
```

Per-family route:

```text
/io/pentas/families/{slug}
```

The route is a **portal contract**, not a claim that a frontend route is already deployed. CrownThrive IO may implement the route directly, while PentaDocs preserves the authoritative family story and operating contract.

Every family portal must provide:

**Story · Mission · Member Census · Member Status · Responsibilities · Inputs/Outputs · Authority Boundary · Cross-Family Handoffs · Operations · SOPs/SLAs · Evidence · API/MCP · Incidents/Recovery · Releases/Changelog · Roadmap · Support**

## The 15 institutional families

| Family | Primary mission | Canonical portal |
| --- | --- | --- |
| Penta System Architecture Family | OS structure, topology, planes, substrate, mesh and whole-system self-model | `/io/pentas/families/system-architecture` |
| Penta Routing & Interoperability Family | federation, MCP/API contracts, routing, bindings and interoperable handoffs | `/io/pentas/families/routing-interoperability` |
| Penta Transport & Capability Primitives Family | bounded requests, reads, mutations, queues, events and low-level route capabilities | `/io/pentas/families/transport-primitives` |
| Penta Automation & Agentic Family | workflows, agents, models, skills, tools, algorithms and orchestration | `/io/pentas/families/automation-agentic` |
| Penta Build, Certification & Release Family | factories, builds, tests, certification, PR/merge/release and execution evidence | `/io/pentas/families/build-release` |
| Penta Security, Identity & Trust Family | identity, credentials, privacy, compliance, risk, audit, adversarial assurance and secrets | `/io/pentas/families/security-trust` |
| Penta Resilience & Continuity Family | serialization, versions, schedules, readiness, maintenance, snapshots, rollback and succession | `/io/pentas/families/resilience-continuity` |
| Penta Observability & Organic Systems Family | error/log/trace/metric spine, institutional nervous system, body health, load and cost pressure | `/io/pentas/families/observability-organic` |
| Penta Knowledge, Semantics & Data Family | documentation, records, data, terminology, assets, maps, contracts and IP lineage | `/io/pentas/families/knowledge-semantics-data` |
| Penta Governance, Legal & Institutional Controls Family | policy, legal, contracts, licensing, ethics, procurement, vendors, capital and board oversight | `/io/pentas/families/governance-legal` |
| Penta Workforce & People Family | human/AI collaboration, stewardship, managers, directors, cohorts, HR and benefits | `/io/pentas/families/workforce-people` |
| Penta Intelligence, Research & Impact Family | sensing, analytics, research, scenario work and impact intelligence | `/io/pentas/families/intelligence-research` |
| Penta Communications & Service Family | mail, marketing communication, concierge fulfillment and service delivery | `/io/pentas/families/communications-service` |
| Penta Media, Studio & Publishing Family | media operations, studios, manuscripts, editions, canon and creative production | `/io/pentas/families/media-creative` |
| Penta Commerce & Economy Family | governed commerce, credits, payments/compensation and economic optimization | `/io/pentas/families/commerce-economy` |

## Family 1 — System Architecture

**Story.** This family defines the body plan. PentaOS provides the technical namespace; PentaTechture defines architecture; PentaPology defines topology; PentaPlanes separates control/data/execution/governance planes; PentaBase provides the institutional data/control substrate; PentaMesh/PentaFabric connect services; PentaControl coordinates governed intent; PentaVergence reconciles stale or divergent state; PentaSELF maintains bounded self-observation.

**Representative members:** PentaOS, PentaVergence, PentaTechture, PentaPology, PentaPlanes, PentaFabric, PentaMesh, PentaBase, PentaControl and PentaSELF.

**Boundary.** Architecture can describe, coordinate and reconcile capabilities. It cannot grant credentials, money movement, rights, legal authority or provider writes.

**Primary handoffs:** Routing & Interoperability; Governance & Legal; Observability & Organic Systems; Resilience & Continuity.

## Family 2 — Routing & Interoperability

**Story.** This is the institutional circulation/connection layer. PentaRoute resolves routes, PentaMCP exposes bounded machine capabilities, PentaFlex provides adaptable API/MCP framework behavior, PentaFederation preserves cross-system identities and trust boundaries, PentaInterOps manages compatibility/transforms, PentaWire carries events/transport and PentaBind records explicit bindings.

**Representative members:** PentaFederation, PentaInterOps, PentaFlex, PentaMCP, PentaRoute, PentaWire and PentaBind.

**Boundary.** A route is never permission. A successful connection never expands the caller's authority or a provider adapter's certified scope.

**Primary handoffs:** Transport Primitives; Automation & Agentic; Security & Trust; Resilience & Continuity.

## Family 3 — Transport & Capability Primitives

**Story.** This family contains the bounded low-level verbs that higher systems compose rather than reinvent: fetch/read/query/list/parse/resolve/transform/validate, GET/HEAD/OPTIONS, POST/PUT/PATCH/DELETE, queues/retries/events/streams, cache/sync/ingest/import/export, create/update/upsert, schedule/lock/reconcile, signatures/auth, test/compile/generate/deploy and other PentaRoute primitives.

**Representative members:** PentaTun, PentaBeata, PentaFetch, PentaGet, PentaHead, PentaOptions, PentaPost, PentaPut, PentaPatch, PentaDelete, PentaQuery, PentaSearch, PentaRead, PentaList, PentaParse, PentaResolve, PentaTransform, PentaValidate, PentaCache, PentaSync and PentaIngest, plus the complete current PentaRoute primitive census.

**Boundary.** A primitive exposes a capability contract. Higher-level systems still supply identity, authority, policy, idempotency, readback and provider certification.

## Family 4 — Automation & Agentic

**Story.** This family turns authorized intent into typed work. It covers orchestration, workflows, agents, LLM/model contracts, machine-learning lifecycle, plugins, reusable skills, tools, algorithms, scripts, agent laboratories and governed RFA intake.

**Representative members:** PentaOrchestrator, PentaMation, PentaFlows, PentaAgents, PentaLLM, PentaMCL, PentaBoxes, PentaSkills, PentaTools, PentaRithms, PentaScripts, PentaSuite and PentaRFA.

**Boundary.** Automation cannot self-authorize, self-certify consequential work or convert confidence into D3/human authority.

## Family 5 — Build, Certification & Release

**Story.** This is the software production line. PentaFactory produces governed candidates; PentaBuild packages software/adapters; PentaCertify proves exact capabilities; PentaAssure independently evaluates evidence; PentaQuality manages quality contracts; PentaPR/PentaMerge/PentaCloser converge source state; PentaRelease publishes governed versions; PentaRunners/PentaPunters/PentaActions/PentaResults provide execution-pool, dispatch and evidence rails.

**Representative members:** PentaFactory, PentaBuild, PentaCertify, PentaAssure, PentaQuality, PentaPR, PentaMerge, PentaCloser, PentaRelease, PentaRunners, PentaPunters, PentaActions and PentaResults.

**Boundary.** A green build is not certification; certification is not business authority; merge is not deployment; deployment is not a rights/economic approval.

## Family 6 — Security, Identity & Trust

**Story.** This family protects the perimeter and internal trust fabric: authority bounds, system security, identities, credentials, privacy, compliance, risk, audit, sanctions controls, secret custody, authentication/signatures and the defensive/adversarial assurance loop.

**Representative members:** PentaBound, PentaSecure, PentaSecurity, PentaCredentials, PentaIdentity, PentaPrivacy, PentaCompliance, PentaRisk, PentaAudit, PentaOFAC, PentaVault, PentaAuth, PentaSign, PentaImmune, PentaEVIBuilder, PentaBlue, PentaRed and PentaHoneyPot.

**Boundary.** Security evidence does not waive legal/rights/business controls. Credentials prove possession/readiness, not permission. PentaRed remains sandbox/range bound; PentaImmune cannot manufacture PASS or D3 authority.

## Family 7 — Resilience & Continuity

**Story.** This family keeps CrownThrive alive through drift, incidents, version changes and generations. It owns resilience planning, snapshots, rollback, maintenance, serialized/tombstoned lineage, versions/formats, SOP/SLA continuity, temporal policy, status/readiness/liveness, and intergenerational succession.

**Representative members:** PentaLiency, PentaSnapshot, PentaRollback, PentaNurture, PentaGeneration, PentaSerialized, PentaVersion, PentaFormat, PentaSOPs, PentaSLAs, PentaTime, PentaStatus, PentaOD, PentaHeartbeat and PentaBeata.

**Boundary.** Recovery restores authorized intended state; it cannot revive retired authority, bypass D3 or silently rewrite history. HOT means ready within authority—not unrestricted access.

## Family 8 — Observability & Organic Systems

**Story.** CrownThrive models the OS as a living institutional body. PentaError/Logger/Trace/Metric form the observability spine. PentaSpine preserves ordered evidence, PentaNerves routes signals, PentaBrain assesses health and learning trends, PentaBody produces whole-system projection, PentaHealth classifies organs, PentaLoad measures demand, PentaBalancer manages capacity and PentaCosts senses economic pressure.

**Representative members:** PentaError, PentaLogger, PentaTrace, PentaMetric, PentaBrain, PentaSpine, PentaNerves, PentaBody, PentaHealth, PentaLoad, PentaBalancer and PentaCosts.

**Boundary.** Observation is not authority. Learning is advisory until separately governed. Cost pressure cannot initiate money movement by itself.

## Family 9 — Knowledge, Semantics & Data

**Story.** This family keeps CrownThrive's institutional memory coherent. PentaDocs projects governed knowledge, PentaScribe maintains language/glossaries, PentaData governs data semantics and lineage, PentaRecords governs authoritative records/retention, PentaNotes preserves feedback/lessons, PentaSets manages asset/corpus sets, PentaMaps visualizes topology, PentaStars preserves formal contracts and PentaIP governs IP/provenance metadata.

**Representative members:** PentaDocs, PentaScribe, PentaData, PentaRecords, PentaNotes, PentaSets, PentaMaps, PentaStars and PentaIP.

**Boundary.** Documentation and data records may state policy/evidence but do not create deployment, legal, rights or economic authority.

## Family 10 — Governance, Legal & Institutional Controls

**Story.** This family coordinates board/directive governance and institutional control work beneath CHLOM/DAIL and human-reserved authority. It covers policy, legal operations, contracts, licenses, ethics, capital, procurement and vendors.

**Representative members:** PentaBoard, PentaPolicy, PentaLegal, PentaContracts, PentaLicense, PentaEthics, PentaCapital, PentaProcure and PentaVendor.

**Boundary.** These systems administer workflows and evidence. They do not impersonate counsel, signatories, regulators, investors, owners or fiduciaries and cannot manufacture legal sufficiency or binding authority.

## Family 11 — Workforce & People

**Story.** This family governs the human + digital workforce: directors and managers, cohort structures, capability acceleration, triage, HR/benefits, alumni stewardship and human/AI handoffs.

**Representative members:** PentaDirectors, PentaManagers, PentaWorkforce OS, PentaCohorts, PentaAccelerator, PentaTriage, PentaHR, PentaBenefits, PentaAlumni and PentaHybrid.

**Boundary.** Role assignment, cohort membership or workforce status never creates sovereign or D3 authority beyond the underlying charter/delegation.

## Family 12 — Intelligence, Research & Impact

**Story.** This family converts approved evidence into strategic understanding. PentaSignal senses weak signals, PentaAnalytics analyzes governed data, PentaInstitute performs research/scenarios and PentaImpact evaluates impact/effectiveness.

**Representative members:** PentaSignal, PentaAnalytics, PentaInstitute and PentaImpact.

**Boundary.** Research, analytics, forecasts and impact scores are evidence/recommendation layers. They do not independently authorize consequential action.

## Family 13 — Communications & Service

**Story.** This family handles institutional communication and customer/operator service delivery. PentaMail owns governed email delivery, PentaConcierge handles bounded service requests and PentaMarketer governs campaign/message packaging and marketing evidence.

**Representative members:** PentaMail, PentaConcierge and PentaMarketer.

**Boundary.** A delivery rail cannot redefine message truth or business authority. Consent, identity, provider certification, spend and outbound policy remain independent gates.

## Family 14 — Media, Studio & Publishing

**Story.** This family operates CrownThrive's creative production assets from media channels through studio production to books/editions, while preserving canon, contributor, rights, provider and release lineage.

**Representative members:** PentaMedia, PentaStudios and PentaBooks.

**Boundary.** An asset existing does not clear rights, canon, licensing, distribution, monetization or public release.

## Family 15 — Commerce & Economy

**Story.** This family activates authorized economic opportunities. PentaGreen is the commerce/economic activation authority; PentaCredits governs internal credits/value representations; PentaPay coordinates authorized payment/compensation workflows; PentaCost governs cost/resource visibility and controls.

**Representative members:** PentaGreen, PentaCredits, PentaPay and PentaCost.

**Constitutional rule:** **PentaGreen may optimize within authority. It may never manufacture authority.** Provider capability, checkout UI, a balance, a price candidate, a payment attempt or an ECAC candidate does not independently authorize money movement, rights or entitlement.

## Cross-family handoffs

Primary family ownership avoids ambiguity; secondary family roles preserve reality. Examples:

- PentaStatus is primarily Resilience & Continuity but also supports Observability and Communications.
- PentaHealth is primarily Observability & Organic Systems while also serving Workforce and Resilience.
- PentaAssure is primarily Build/Certification/Release while also serving Security and Governance.
- PentaCertify is primarily Build/Certification/Release while also serving Security and Resilience.
- PentaData is primarily Knowledge/Data while feeding Intelligence.
- PentaCapital is primarily Governance/Legal while participating in Commerce/Economy.
- PentaImmune is primarily Security/Trust while participating in Resilience and Observability.
- PentaTime is primarily Resilience/Continuity while providing temporal policy to Automation.

A secondary role never creates a second owner of the same decision. The exact child contract and authority trace determine who can act.

## Discovery and census enforcement

Run:

```bash
python runtime/penta_families.py --root . --portal-index
python runtime/penta_families.py --root . --family system-architecture
python tests/test_penta_families.py
```

The runtime discovers from:

1. `data/penta/family.registry.json` and all declared/system extension catalogs;
2. `penta/registry/penta-component-registry.v1.json` and its PentaRoute primitives;
3. `PENTA-FAMILY-REGISTRY.md` canonical institutional identities and registered primitive family.

Aliases and display variants are normalized into one identity. If a future Penta is added to any of those sources without a family classification, CI returns `hold_fail_closed`.

## Institutionalization standard for a new family/member

A new Penta identity must not stop at a name. The required lifecycle is:

```text
need discovered
→ stable Penta identity
→ primary family assignment
→ optional secondary family roles
→ machine/member registry
→ portal contract
→ PentaDocs story/guide
→ dependencies + authority boundary
→ status/readiness contract
→ tests/evidence
→ PentaCertify/PentaAssure as applicable
→ release/readback
→ PentaSerialized/PentaGeneration preservation
```

If any required layer is absent, the gap remains visible and the child remains at its evidence-backed maturity.

## Source of truth

- Parent family: `data/penta/family.registry.json`
- Institutional census: `PENTA-FAMILY-REGISTRY.md`
- Technical component census: `penta/registry/penta-component-registry.v1.json`
- Family-of-families registry: `penta/registry/penta-families.v1.json`
- Family portal/runtime verifier: `runtime/penta_families.py`
- Portal implementation guide: `penta/families/README.md`
- Versioned contract: `docs/phase3/PENTA_FAMILY_OF_FAMILIES_PRODUCTION_CONTRACT_v1.0.md`

The family-of-families model is additive to the Penta Family control plane. It organizes the estate; it does not replace child registries, PentaRoute interoperability, PentaStatus, PentaOD, CHLOM, DAIL, PentaCredentials, PentaCertify, PentaAssure or PentaHybrid.
