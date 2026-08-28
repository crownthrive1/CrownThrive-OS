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
- Inputs, outputs, events, and state model
- User guide
- Owner/admin guide
- Operations runbook
- API/MCP/integration guide
- Provider adapter/binding guide
- Data model and retention
- Security, privacy, roles, and permissions
- PentaStatus/observability contract
- SLO/SLA/KPI definitions
- Incident, fail-closed, recovery, and rollback procedures
- Release, version, migration, deprecation, and supersession
- Audit/evidence requirements
- FAQ and glossary
- Trademark/provider attribution

## Registry-driven PentaDocs namespace

PentaDocs SHALL expose a dedicated top-level **Pentas** portal. The generated documentation surface is governed by `scripts/penta_portal_docs.py` and `data/penta/namespace-census.v1.json` and SHALL include:

- `/pentas` — portal home and census summary;
- `/pentas/all` — complete A–Z Penta namespace directory;
- `/pentas/canonical` — every canonical Penta OS registry identity;
- `/pentas/candidates` — aliases, governed extensions, founder-declared candidates, and unresolved references awaiting canonical disposition;
- `/pentas/families` — the 15-family institutional directory;
- `/pentas/families/{slug}` — one internally linked documentation page for each institutional family;
- `/pentas/canonical/{slug}` — one dedicated guide for every canonical Penta; and
- `/pentas/candidates/{slug}` — one fail-closed guide for every noncanonical Penta reference.

The generator MUST fail on canonical-registry count drift, missing dedicated pages, duplicate documentation paths, or navigation drift. Candidate pages MUST explicitly state that documentation is not a production claim. Registry-backed and docs-inferred family assignments MUST remain distinguishable until the canonical family registry resolves them.

The candidate/reference namespace is a preservation and canonicalization queue. A candidate may resolve to a distinct Penta, alias, primitive, subcomponent, engine, compatibility name, superseded name, or retired reference. Documentation alone SHALL NOT select that disposition.

## Portal readiness gate

A route is not `PRODUCTION` merely because a page renders. Production readiness requires: canonical registry match; authenticated/authorized surface; current PentaStatus adapter; live or explicitly non-live operational state; valid docs link; dependency inventory; audit instrumentation; release/version identity; escalation path; no exposed secret material; and provider readback for any capability that claims external execution.

## Documentation freshness gate

PentaStatus SHALL flag a Penta when the production version, portal behavior, provider inventory, access model, or operating contract materially diverges from PentaDocs. Documentation drift is an institutional-health defect, not cosmetic debt.

## New-Penta creation contract

No future `Penta*` name is complete until PentaScribe registers its terminology/mark, the master Penta registry receives its identity and role, PentaDocs receives its guide, CrownThrive IO receives the dedicated route, PentaStatus receives a producer/status contract, and the applicable build/certify/release/security/governance controls are bound.

Any newly registered canonical Penta or governed `data/penta/systems*.json` extension SHALL be picked up by the portal generator on the next governed docs reconciliation. Other named Penta references MUST first enter the candidate namespace so they are preserved without silent authority or maturity promotion.
