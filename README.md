# CrownThrive Operating System 👑

**CrownThrive OS is CrownThrive's authoritative institutional source of truth.**

It records the current institutional generation, governance, stable identities, versions, evidence boundaries, component state, release lineage, corrections, archives, cultural doctrine, provider state, software factories, commercial systems, media systems, PentaDocs, CHLOM, Cultural Imprint Engine (CIE), ThriveBase, PentaGreen™, CrownThrive IO, APIs, MCPs, agents, automation, recovery, and the relationships that make CrownThrive operate as one convergent institution.

**Institutional generation:** **Phase 3 — Execute**  
**Institutional lifecycle:** **PENTA — Discover → Govern → Execute → Verify → Preserve**  
**Current OS release family:** **3.x**  
**Future institutional generations:** **Phase 4 — Verify; Phase 5 — Preserve**  
**Contact:** contact@crownthrive.com

> **Institutional rule:** If CrownThrive cannot discover it, govern it, execute it, verify it, and preserve it, the institutional loop is incomplete.

## Start here

1. **PENTA Doctrine** — [`docs/phase3/PENTA_DOCTRINE.md`](docs/phase3/PENTA_DOCTRINE.md)
2. **PENTA Phase Model** — [`docs/phase-model/PENTA_PHASE_MODEL.md`](docs/phase-model/PENTA_PHASE_MODEL.md)
3. **PENTA Dictionary & Glossary** — [`docs/phase3/PENTA_GLOSSARY.md`](docs/phase3/PENTA_GLOSSARY.md)
4. **Current Phase 3 State** — [`docs/phase3/CURRENT_STATE.md`](docs/phase3/CURRENT_STATE.md)
5. **Institutional Archive** — [`docs/archive/README.md`](docs/archive/README.md)
6. **PentaGreen** — [`PENTAGREEN.md`](PENTAGREEN.md)
7. **CHLOM** — [`chlom/overview.mdx`](chlom/overview.mdx)
8. **Cultural Imprint Engine** — [`doctrine/cultural-imprint-engine.mdx`](doctrine/cultural-imprint-engine.mdx)
9. **Developer Platform** — [`developers/overview.mdx`](developers/overview.mdx)
10. **COS V1 Convergence and Release Gate** — [`docs/COS_V1_CONVERGENCE_ARCHITECTURE.md`](docs/COS_V1_CONVERGENCE_ARCHITECTURE.md)

The reproducible COS V1 source gate is:

```bash
python3 -m pip install -r requirements/cos-v1-validation.txt
python3 scripts/validate_cos_v1.py --root .
```

It validates pinned schema dependencies, all GitHub Actions YAML, JavaScript syntax and tests, COS/Penta function contracts, provider-control contracts, and Python runtime tests. It does not mutate a provider or claim deployment/readback certification.

The protected `PentaFabric Production Canary` is the separate production proof lane. It remains disabled until external settings readback proves required reviewers, prevent-self-review, a main-only deployment policy, an environment-scoped write token, and `PENTAFABRIC_PRODUCTION_CANARY_ENABLED=true`. When authorized, it writes one runtime-assurance event and requires HMAC, exact source lineage, Vercel OIDC, and Supabase read-after-write evidence. Source-gate PASS alone never claims that production proof.

## PENTA: one doctrine, five institutional functions

The word **penta** derives from the Greek word for **five**. CrownThrive uses that meaning deliberately. PENTA is not a decorative prefix and it is not a collection of unrelated product names. It is the common operating grammar used to organize how the institution finds truth, applies authority, performs work, proves results, and preserves continuity.

### Discover

Discover what exists and what is real: providers, endpoints, repositories, assets, identities, participants, contracts, schemas, dependencies, versions, health, rights signals, risks, opportunities, history, and gaps.

Discovery does not manufacture authority. A discovered provider feature is not automatically configured. A reachable endpoint is not automatically a certified write path. An old document is not current merely because it is indexed.

### Govern

Govern what is allowed. Determine rights, rules, roles, credentials, policies, capability ceilings, cultural constraints, risk classes, licensing requirements, evidence requirements, approval rules, and continuity obligations.

CHLOM is the principal governance architecture for Rights, Rules, Roles, Revenue, Records, and Remedies. CIE governs cultural meaning, narrative coherence, representation, and imprint constraints within its scope. Vault, identity, certification, and evidence systems preserve the difference between technical possibility and institutional permission.

### Execute

Execute what is authorized through durable software: PentaRoute, PentaTun, Penta primitives, PentaFactory, CrownThrive Software Factory, schedulers, queues, provider-native adapters, internal services, publication systems, media systems, PentaGreen commerce/economic activation, and governed automation.

Execution remains bounded. PentaDelete does not imply universal delete. A generated artifact is not automatically accepted. A deployed endpoint does not automatically gain D3 authority.

### Verify

Verify what happened through provider readback, read-after-write checks, receipts, hashes, canaries, tests, signatures, reconciliation, heartbeats, release evidence, rollback checks, and independent proof surfaces.

A request being sent is not proof that the intended state exists.

### Preserve

Preserve what must survive: versions, provenance, archives, receipts, stable identities, rights context, executable runbooks, recovery packages, PentaGeneration handoffs, Cultural Imprint continuity, and the knowledge required for future participants to continue correctly.

## The canonical institutional phase model

CrownThrive's roadmap is now aligned directly to the PENTA doctrine:

| Phase | PENTA stage | Institutional question | State |
| --- | --- | --- | --- |
| **Phase 1** | **Discover** | What exists, what matters, and what is actually true? | Historical / consolidated |
| **Phase 2** | **Govern** | What may happen, under whose authority, and under what conditions? | Historical / consolidated |
| **Phase 3** | **Execute** | Can CrownThrive perform its work through durable governed software? | **Current** |
| **Phase 4** | **Verify** | Can CrownThrive independently and continuously prove correctness, authority, effect, and resilience? | Future |
| **Phase 5** | **Preserve** | Can CrownThrive survive provider, platform, repository, personnel, and generational change without losing itself? | Future |

This is now the only institution-wide phase taxonomy.

Historical Phase 2.5, 2.7, 2.8, 2.9, 2.95, 2.97, 2.98, 2.99, pre-entry convergence, and similar decimal labels are **retired as current roadmap language**. They remain preserved where historically accurate and resolve into the broader **Phase 2 — Govern** generation.

CrownThrive will not create new decimal institutional phases. Precision belongs in OS releases, component versions, maturity states, certification states, risk/authority classes, waves, sprints, cohorts, or milestones.

## Phase 3 — Execute: the current generation

Phase 3 converts CrownThrive's institutional knowledge, provider access, governance, cultural doctrine, products, content systems, commerce, media, documentation, publishing, APIs, MCPs, factories, schedulers, evidence, and continuity into durable executable software.

The objective is not simply 'more automation.' The objective is an institution that can continue performing priority work without requiring a founder, a single ChatGPT session, or one SaaS dashboard to manually push every recurring operation.

The Phase 3 execution fabric includes PentaRoute, PentaTun, PentaBeata, the wider Penta primitive family, PentaFactory, CrownThrive Software Factory, Penta Federation, PentaMedia, PentaBooks, PentaGeneration, PentaStudios, PentaDocs, PentaGreen, ThriveBase, CHLOM, CIE, CrownThrive IO, repository federation, provider-native adapters, queues, schedulers, proof surfaces, deployment lanes, publishing controls, and self-discovery/certification loops.

Phase 3 is not complete because a repository says `v3`, because an Edge Function exists, or because an agent generated code. Priority functions must execute durably, have known ownership and source-of-truth, operate within bounded authority, create evidence when they fail, support recovery, and produce enough independent proof for assurance to become the dominant objective of Phase 4.

## Phase 4 — Verify: the assurance refactor

Phase 4 changes the primary institutional question from **Can it run?** to **Can CrownThrive prove it ran correctly, under the correct authority, produced the intended result, and remained recoverable?**

Phase 4 will emphasize independent provider readback, cross-system proofs, conformance, reproducibility, red-team/adversarial testing, fault injection, provider-exit drills, rollback verification, security assurance, economic reconciliation, rights and licensing integrity, data quality, release provenance, certification renewal, and continuous drift detection.

The target is an assurance-first institution in which material operational claims can be independently checked rather than accepted from the component that generated them.

## Phase 5 — Preserve: continuity and inheritance

Phase 5 asks whether CrownThrive can survive change without losing its institutional identity, authority, evidence, culture, rights, or operating knowledge.

This phase centers PentaGeneration, seven-generation continuity, archives, succession, provider portability, repository portability, durable identities, rights custody, dependency replacement, data migration, provider exit, recovery packages, executable institutional memory, and knowledge inheritance.

A mature CrownThrive should be able to replace a provider, lose a platform, change personnel, onboard a successor, or reconstruct a subsystem while preserving the information and authority required to continue.

## PENTA is cyclical even though the phase model is sequential

The institution progresses through five dominant generations, but every provider, asset, workflow, product, document, release, and participant may continuously run the PENTA loop inside any phase.

A provider added during Phase 3 may be discovered, governed through CHLOM, executed through PentaRoute, verified through PentaBeata/readback, and preserved through receipts while the institution remains in Phase 3. The phase identifies the dominant institution-wide objective; it does not disable the other four functions.

## Source-of-truth hierarchy

1. **CrownThrive OS canonical records** — current phase, stable identity, effective policy, governance, releases, versions, corrections, and archive dispositions.
2. **OS-bound operational evidence** — ThriveBase state, CHLOM/DAIL evidence, certified provider readbacks, exact Git/release receipts, and other incorporated evidence.
3. **Component repositories** — CHLOM, CIE, and other component packages are authoritative within their exact scope while remaining subordinate to OS institution-wide state.
4. **PentaDocs** — public-safe institutional knowledge projection. Mintlify is the current underlying documentation provider, not the institutional authority.
5. **Websites, storefronts, media surfaces, and help centers** — downstream projections that may lag.
6. **Archive/history** — evidence of what was previously true, planned, attempted, released, or operated; never current merely because it remains accessible.

A downstream projection can create a reconciliation task. It cannot independently redefine institutional truth.

## Institutional architecture

### CrownThrive OS

The OS is the institutional control and truth layer. It distinguishes phase, version, maturity, authority, evidence, current state, historical state, and public projection.

### CHLOM

**Compliance Hybrid Licensing and Ownership Model** governs Rights, Rules, Roles, Revenue, Records, and Remedies. CHLOM controls capability and authority boundaries; it does not manufacture cultural truth.

### Cultural Imprint Engine

CIE governs cultural meaning, narrative continuity, representation, imprint identity, aesthetics, canon/audience constraints, and responsible reuse. It interoperates with CHLOM without inheriting CHLOM's rights authority.

### ThriveBase

ThriveBase is CrownThrive's durable operational state, workflow, queue, evidence, registry, scheduling, and automation substrate.

### PENTA execution family

PENTA provides the shared human-and-machine vocabulary for institutional execution. PentaRoute, PentaTun, PentaBeata, PentaFetch, PentaGet, PentaQuery, PentaSearch, PentaQueue, PentaRetry, PentaBind, PentaVault, PentaAuth, PentaAudit, PentaTest, PentaDeploy, PentaReconcile and the wider primitive family make previously implicit software responsibilities explicit and governable.

### PentaFactory and CrownThrive Software Factory

Factories generate, validate, package, bind, test, and deploy governed software/framework candidates through provider-native adapters. Generation is not acceptance; acceptance is not provider authority; provider authority is not D3 authority.

### Penta Federation

Penta Federation carries identities, bindings, events, proofs, routes, and cross-system/repository continuity without forcing each subsystem to maintain a competing copy of canonical state.

### PentaGreen™

PentaGreen is CrownThrive's governed commerce and economic activation authority, with ThriveEvergreen retained as a legacy read-compatible alias where required for provenance and migration. PentaGreen may optimize within authority; it may not manufacture authority.

### PentaDocs

PentaDocs is the institutional knowledge layer. It must explain the architecture to humans and project machine-readable doctrine, current state, glossary terms, histories, and successor links.

### PentaGeneration

PentaGeneration is the long-horizon handoff, succession, continuity, proof, and seven-generation stewardship layer and becomes increasingly central as CrownThrive approaches Phase 5.

## Maturity is not phase

Institutional phase and component maturity are different dimensions. A Phase 3 component may be `CANDIDATE`, `CONTROLLED_TEST`, `ACTIVE`, `PRODUCTION`, `WRITE_VERIFIED`, `RESERVE`, `HISTORICAL`, `SUPERSEDED`, or `RETIRED`.

Similarly, a v1 or v2 API may remain the correct active component contract during OS 3.x. The PENTA phase model does not force-renumber every schema, API, migration, function, protocol, or runtime.

## Authority is not phase

A higher phase never creates legal, economic, provider, destructive, or D3 authority by itself.

No phase label, document, AI output, generated artifact, successful HTTP response, repository merge, deployment, payment link, provider capability, or public statement independently creates ownership, licensing rights, entitlement, settlement, or universal mutation authority.

## Archive and retirement

CrownThrive now uses the rule:

> **Preserve the evidence. Retire the obsolete instruction. Link to the successor.**

Old phase timelines, stale roadmaps, superseded versions, renamed systems, duplicate architecture paths, and obsolete guidance are removed from active canon when a successor is established. Historical evidence remains available for provenance, audit, recovery, and institutional history.

See [`docs/archive/README.md`](docs/archive/README.md) and [`docs/archive/PENTA_PHASE_RETIREMENT_MANIFEST.json`](docs/archive/PENTA_PHASE_RETIREMENT_MANIFEST.json).

## Repository family

The current canonical public-safe repository family includes `crownthrive1/CrownThrive-OS`, `crownthrive1/chlom-protocol`, and `crownthrive1/CrownThrive-CIE`, with other repositories and providers federated through the OS and PENTA control fabric according to their exact scope.

## Licensing, intellectual property, and machine use

Public visibility does not make CrownThrive proprietary material open source by default. CrownThrive reserves applicable rights in proprietary code, schemas, taxonomies, ontologies, methods, brands, documentation, prompts, agents, CIE, CHLOM, PENTA architectures, ThriveBase specifications, PentaGreen, factories, interfaces, and institutional knowledge.

Repository visibility does not create permission to clone, resell, impersonate, commercialize, bulk-extract, reconstruct protected methods, or represent an implementation as CrownThrive-certified.

## Seven-generation continuity

CrownThrive uses a seven-generation planning horizon for stewardship, architectural lineage, rights preservation, succession, portability, recoverability, and institutional memory. It is a governance and planning framework rather than an automatic legal transfer mechanism.

## The forward baseline

CrownThrive no longer needs an endless staircase of decimal phases to describe where it is going.

**Discover what is real. Govern what is allowed. Execute what is authorized. Verify what happened. Preserve what must outlive us.**

That is PENTA. That is the institutional lifecycle through Phase 5. Every future platform, provider, participant, agent, acquisition, framework, brand, corridor, or system should be able to locate itself inside that model without creating a competing roadmap.

---

**Impact. Legacy. Cultural advancement. Governed convergence. PENTA. 👑**

<!-- pentarelease:managed-release-surface:start -->
## Latest PentaRelease — v3.81.0.0

- **Official release:** https://github.com/crownthrive1/CrownThrive-OS/releases/tag/v3.81.0.0
- **Release title:** CrownThrive OS 3.81.0.0 — Autonomous PentaRelease
- **Who:** PentaRelease / provider actor github-actions[bot]
- **Why:** new executable capability or runtime delta
- **Changed paths:** 10
- **Provider actual cost:** $0.00 USD
- **Recognized release exposure:** $0.00 USD
- **Direct usage calculation:** `not_available`
- **CIE:** **PASS — 100/100**
- **CIE dimensions:** brand_safety=20, identity_fit=20, legacy_impact=20, community_value=20, story_alignment=20
- **Evidence:** `b89356534e6dc8c50974c9ce038b705bd2ec749ff71e2145ef1645590a8060ef`

PentaRelease maintains this bounded block. Content outside the markers remains under its existing ownership and editorial authority.
<!-- pentarelease:managed-release-surface:end -->
