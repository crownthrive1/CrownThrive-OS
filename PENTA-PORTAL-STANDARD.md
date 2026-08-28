# Penta Portal & Guide Standard

**Applies to:** every registered CrownThrive Penta  
**Portal host/control plane:** CrownThrive IO  
**Documentation authority:** PentaDocs™

## Required CrownThrive IO structure

Family index: `/io/pentas`

Every Penta SHALL receive a dedicated route at `/io/pentas/{slug}`. The family index SHALL show canonical name, purpose, lifecycle state, current PentaStatus state, version, owner/escalation, critical dependencies, last heartbeat/readback, last release, open incidents/actions, and links to its portal and PentaDocs guide.

## Required per-Penta portal modules

1. **Overview** — mission, institutional class, boundaries, authority, owner, lifecycle, version.
2. **Operate** — only actions authorized for that Penta and current operator.
3. **Status** — live PentaStatus envelope, evidence timestamp, dependency health, SLO/SLA, freshness.
4. **Docs** — canonical PentaDocs documentation and changelog.
5. **Integrations** — dependencies, providers, APIs/MCPs, events, data stores, upstream/downstream systems.
6. **Access** — roles, grants, scopes, credential references, certification readiness; never plaintext secrets.
7. **Audit** — material actions, authority context, evidence/readbacks, changes, incidents.
8. **Releases** — versions, artifacts, checksums/evidence where applicable, deployment/readback, rollback/supersession.
9. **Incidents** — active/recent incidents, severity, blast radius, owner, recovery state.
10. **Costs** — relevant usage/resource/economic signals without manufacturing payment authority.
11. **Dependencies** — graph and readiness of required services, providers, policies, and credentials.

A Penta may add specialized modules, but it may not omit a required module when the underlying capability exists.

## Required comprehensive guide structure

Each PentaDocs guide SHALL include, proportionate to the subsystem:

- Charter & purpose
- Scope, boundaries, and non-authorities
- Users/operators/owners
- Architecture and dependencies
- Architectural layer assignment
- Job/function assignment
- Lifecycle participation
- Intended audiences
- When to use and when not to use
- Prerequisites and quickstart
- Inputs, outputs, events, and state model
- User guide
- Developer guide
- Owner/admin guide
- Operations runbook
- API/MCP/integration guide
- Provider adapter/binding guide
- Data model and retention
- Security, privacy, roles, and permissions
- PentaStatus/observability contract
- SLO/SLA/KPI definitions
- Failure modes, retry/idempotency and reconciliation behavior
- Incident, fail-closed, recovery, and rollback procedures
- Test matrix and production-certification evidence
- Release, version, migration, deprecation, and supersession
- Audit/evidence requirements
- Agent ingestion/decision procedure
- Examples, anti-patterns and troubleshooting
- Ownership, escalation and support
- FAQ and glossary
- Trademark/provider attribution

## Orthogonal operating taxonomies

The 15-family topology remains the institutional grouping and SHALL NOT be replaced by architectural layers or jobs/functions.

PentaDocs SHALL additionally classify each Penta across four orthogonal dimensions:

1. **Family** — where the Penta belongs institutionally.
2. **Architectural layer** — where the Penta sits in the technical/operational stack.
3. **Job/function** — what class of work the Penta performs and therefore what tasks may route toward it.
4. **Lifecycle stage** — when the Penta participates across discovery, design, build, verification, release, operation, observation, recovery, governance and evolution.

Audience classification SHALL identify whether the guide is intended for agents/Pentas, developers, operators, owners/admins, auditors/governance, or approved partners/integrators.

The canonical taxonomy source is `data/penta/operational-taxonomy.v1.json`. Classification provenance MUST distinguish registry/family-derived assignments from documentation inference or pending classification. Classification is discovery and routing metadata only; it never promotes maturity, execution eligibility, authority, credentials, provider permission, financial/rights authority or D3 authority.

## Registry-driven PentaDocs namespace

PentaDocs SHALL expose a dedicated top-level **Pentas** portal. The generated documentation surface is governed by `scripts/penta_portal_docs.py`, `scripts/penta_portal_finalize.py`, `scripts/penta_operational_knowledge.py`, and the corresponding registries/manifests and SHALL include:

- `/pentas` — portal home and census summary;
- `/pentas/all` — complete A–Z Penta namespace directory;
- `/pentas/canonical` — every canonical Penta OS registry identity;
- `/pentas/candidates` — aliases, governed extensions, founder-declared candidates, and unresolved references awaiting canonical disposition;
- `/pentas/families` — the 15-family institutional directory;
- `/pentas/families/{slug}` — one internally linked documentation page for each institutional family;
- `/pentas/operational` — the human/machine operating-model hub;
- `/pentas/layers` and `/pentas/layers/{slug}` — architecture-first discovery;
- `/pentas/jobs` and `/pentas/jobs/{slug}` — task/job-first discovery;
- `/pentas/lifecycle` and `/pentas/lifecycle/{slug}` — lifecycle-stage discovery;
- `/pentas/audiences` and `/pentas/audiences/{slug}` — audience-specific entry points;
- `/pentas/development` — development and extension standard;
- `/pentas/quickstarts` — common usage patterns;
- `/pentas/agents` — agent-ingestion and routing contract;
- `/pentas/integrations` — interoperability/provider integration patterns;
- `/pentas/runbooks` — operating, incident and recovery model;
- `/pentas/canonical/{slug}` — one dedicated guide for every canonical Penta; and
- `/pentas/candidates/{slug}` — one fail-closed guide for every noncanonical Penta reference.

The generator MUST fail on canonical-registry count drift, missing dedicated pages, duplicate documentation paths, unresolved taxonomy references, missing canonical layer/job classifications, agent-manifest drift, or navigation drift. Candidate pages MUST explicitly state that documentation is not a production claim. Registry-backed, family-derived and docs-inferred assignments MUST remain distinguishable.

The candidate/reference namespace is a preservation and canonicalization queue. A candidate may resolve to a distinct Penta, alias, primitive, subcomponent, engine, compatibility name, superseded name, or retired reference. Documentation alone SHALL NOT select that disposition.

## Machine-readable knowledge & agent ingestion

Human PentaDocs and agent knowledge SHALL derive from the same namespace and taxonomy sources. Penta agents MUST NOT depend on scraping prose as their primary routing contract.

The generated machine surfaces SHALL include:

- `data/penta/operational-knowledge.v1.json` — complete per-Penta operational/development knowledge records;
- `data/penta/agent-knowledge.v1.json` — compact machine routing manifest; and
- `data/penta/agent-knowledge.v1.jsonl` — one record per identity for indexing, retrieval, embeddings and streaming ingestion.

At minimum each machine record SHALL expose identity, namespace state, canonical machine key/target, family, layers, jobs/functions, lifecycle stages, audiences, classification provenance, role, maturity/risk/readiness projection, execution-eligibility projection, when-to-use/when-not-to-use guidance, prerequisites, routing actions, forbidden actions, dependencies, interface references, data-contract guidance, evidence paths, runbooks, agent decision instructions, escalation and freshness/hash metadata.

### Agent decision invariant

An agent SHALL:

1. match intent to job/function and architectural layer;
2. prefer a canonical identity;
3. verify current readiness, risk and execution eligibility;
4. resolve CHLOM/current authority and provider binding before material execution;
5. choose the narrowest canonical interface;
6. preserve idempotency/correlation and dependency context;
7. collect provider/runtime readback and DAIL-compatible evidence; and
8. route ambiguity/failure to the relevant observe/recover/govern lane instead of manufacturing PASS.

`DOCUMENTED ≠ ROUTABLE ≠ EXECUTION-ELIGIBLE ≠ AUTHORIZED ≠ CERTIFIED ≠ PRODUCTION`.

## Development contract

Every material Penta implementation SHALL expose explicit versioned contracts instead of relying on documentation inference. Development should define, where applicable, schemas for inputs/outputs/events/state, authority/permission requirements, provider bindings, idempotency and retry boundaries, timeout/failure semantics, observability, evidence/readback, migration and rollback.

Tests SHALL cover proportionate denied/degraded paths in addition to happy paths, including authorization denial, dependency failure, provider refusal, timeout, duplicate/idempotent replay, partial write/reconciliation, observability/evidence, migration and rollback/forward-fix.

New interfaces SHOULD reuse PentaRoute, PentaMCP, PentaEvent, PentaHook, PentaStream and other governed interoperability primitives rather than introducing undocumented point-to-point coupling.

## Portal readiness gate

A route is not `PRODUCTION` merely because a page renders. Production readiness requires: canonical registry match; authenticated/authorized surface; current PentaStatus adapter; live or explicitly non-live operational state; valid docs link; dependency inventory; audit instrumentation; release/version identity; escalation path; no exposed secret material; and provider readback for any capability that claims external execution.

## Documentation freshness gate

PentaStatus SHALL flag a Penta when the production version, portal behavior, provider inventory, access model, machine-readable knowledge record, or operating contract materially diverges from PentaDocs. Documentation/manifest drift is an institutional-health defect, not cosmetic debt.

## New-Penta creation contract

No future `Penta*` name is complete until PentaScribe registers its terminology/mark, the master Penta registry receives its identity and role, PentaDocs receives its guide, its family/layer/job/lifecycle/audience classifications are projected, the agent manifest receives its record, CrownThrive IO receives the dedicated route, PentaStatus receives a producer/status contract, accountable ownership/escalation exists, and the applicable build/certify/release/security/governance controls are bound.

Any newly registered canonical Penta or governed `data/penta/systems*.json` extension SHALL be picked up by the portal/operational generator on the next governed docs reconciliation. Other named Penta references MUST first enter the candidate namespace so they are preserved without silent authority or maturity promotion.
