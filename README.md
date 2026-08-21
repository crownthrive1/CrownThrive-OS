# CrownThrive Operating System

This repository is the version-controlled, public-safe institutional knowledge and implementation map for **CrownThrive, LLC** and its Convergent Ecosystem.

It documents the governed relationship among CrownThrive doctrine, platforms, corridors, intellectual property, CHLOM, the Cultural Imprint Engine, the Thrive Flywheel, MM Suites, commerce, media, education, support, legal-policy architecture, data, APIs, MCP servers, automation, recovery, and future selective decentralization.

## Current maturity

- **Human program phase:** Phase 2.99 — private-core, machine-seed and hard-exit preparation
- **Current program state:** `phase_2_99_in_progress`
- **Phase 3 entry:** `blocked_pending_phase_2_99_hard_exit` / `NO-GO`
- **Accepted machine baseline:** release `2.7.9.1`, preserved at historical merge `52762bd4bd629ea8012fac6ceb3790d0955b0499`
- **Repository posture:** governed public-safe source projection with ruleset behavior verified; current head is derived from `main`, not the historical release SHA
- **Publication posture (observed August 21, 2026):** the active default Mintlify URL redirects to authentication, so public readback and indexing remain blocked pending an intentional access decision
- **Next gate:** complete and accept every Phase 2.99 hard-exit predicate before Phase 3

This repository is **not** the Phase 3 runtime, the private evidence vault, a production secrets store, or proof that every documented service is deployed. A page may be accepted institutional architecture while its corresponding capability remains `research`, `specified`, `build`, `legal_review_required`, `unverified`, or `production` in a separate state dimension.

## Institutional operating rule

> Platforms perform the work. Corridors organize the work. CHLOM governs the work. The institutional record proves what happened.

CrownThrive uses stable IDs, effective-dated versions, source authority, evidence classes, explicit rights, role-based access, approval gates, append-only corrections, DAIL events, tested recovery, and audience-specific projections.

A website sentence, product card, historical prospectus, generated file, vendor dashboard, model output, or chat message does not independently establish current production, ownership, permission, legal status, payment, entitlement, registration, or audited fact.

## Knowledge projections

The target architecture is one governed knowledge control plane with multiple projections:

1. **Public-safe institutional documentation** — this repository and its Mintlify projection.
2. **Public customer Help Center** — task-oriented support and adopted public policies when released.
3. **Authenticated role knowledge** — member, creator, affiliate, partner, developer, church, operator, and staff guidance.
4. **Restricted institutional knowledge** — private strategy, contracts, evidence, confidential IP, security, legal, and financial records.
5. **Machine interfaces** — versioned APIs, MCP resources/tools, policy records, and registry projections.

Private material must be protected by real authentication and authorization. Hidden navigation, obscure URLs, `robots.txt`, or frontend-only role checks are not security controls.

## Core architecture

```text
Doctrine + Portfolio Stewardship
          ↓
CrownThrive ID
          ↓
CrownThrive IO / API / MCP Federation
          ↓
CHLOM
Rights · Rules · Roles · Revenue · Records · Remedies
          ↓
OpsOasis + Collab Portal + Automation Control Plane
          ↓
CrownThrive Support + Institutional Knowledge
          ↓
CrownLytics + CrownPulse + CrownInsights + ThrivePush
          ↓
CrownRewards + Affiliates + Ambassadors + Distribution
          ↓
Operating Corridors, Platforms, Imprints, Universes and MM Suites
```

The diagram describes institutional responsibility. It does not claim every integration is universally deployed.

## Repository map

- `standards/` — non-negotiables, records, versioning, corrections, evidence, IP, AI/ML, autonomy, MCP/API, search/SEO, run-packet, cleanup, and program standards.
- `doctrine/` — Convergent Ecosystem, Thrive Flywheel, Hybrid Incubator, Cultural Imprint Engine, founder doctrine, canon, frameworks, and operating spine.
- `chlom/` — CHLOM functions, papers, components, DLA/DAIL/LEX, rights/evidence, remedies, service contracts, use cases, and engineering decomposition.
- `platforms/` — platform-specific institutional registries, beginning with Virality Music and KJV Visualized / The Sermon Toolkit.
- `portfolio/` — entity, asset, priority, vendor, domain, brand, imprint, universe, and platform-state registers.
- `technology/` — identity, data, private core, cloud, security, release control, MCP topology, SEO fleet, backup, and Phase 3 architecture.
- `developers/` — API federation, endpoint discovery, adapters, SDK/sandbox, identity bridge, role surfaces, and builder governance.
- `support/` — Help Center architecture, Legal Depot, policy applicability, SOPs, support operations, and lifecycle/sunset controls.
- `automation/` — command structure, agent registry, permissions, evaluations, work queues, and control-plane design.
- `workflows/` and `runbooks/` — governed execution and incident procedures.
- `knowledge/` — source authority, recovery, contradictions, adjudications, metrics, corrections, restricted sources, and cumulative audits.
- `changelog/` — effective-dated phase history, release records, and architecture decisions.

## Development and validation

The project uses Mintlify-compatible MDX and `docs.json` navigation.

Run the repository governance validator before submitting changes:

```bash
python3 scripts/validate_docs.py
```

For a local Mintlify preview, use a supported Mintlify CLI workflow from the repository root after installing the required tooling:

```bash
mint dev
```

The CI workflow runs the governance validator on pull requests and protected-branch updates. A navigation route must resolve to substantive MDX content. Template residue, obvious credential patterns, empty pages, duplicate navigation entries, and missing frontmatter are release failures.

## Change-control expectations

Every material change must:

- preserve stable IDs and lineage;
- state whether it is current, historical, proposed, research, restricted, superseded, or unverified;
- identify the governing source or decision;
- use the correct human phase and machine release namespaces;
- preserve prior records through corrections, amendments, or supersession;
- respect public, community, internal, restricted, strategic, and machine-only boundaries;
- identify affected platforms, policies, rights, APIs, data, commerce, search, support, and recovery paths;
- include validation evidence and a next-run handoff.

Read `AGENTS.md` before any automated or human-assisted repository work.

## Intellectual property and third-party material

CrownThrive-specific original documentation, architecture, frameworks, registries, diagrams, policies, and research summaries are protected under the repository's all-rights-reserved notice unless a file explicitly states otherwise.

Repository access does not grant rights to use CrownThrive, CHLOM, the Cultural Imprint Engine, the Thrive Flywheel, MM Suites, platform names, imprints, universes, characters, source assets, confidential methods, or other CrownThrive intellectual property.

Third-party templates, software, icons, services, and dependencies remain subject to their own licenses and terms. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.

Use of `™` identifies a claimed brand identity; it does not represent a verified registration. Use of `®` requires a current verified registration record.

## Security and responsible disclosure

Do not place credentials, private contracts, customer data, payment data, private journals, security details, unreleased masters, or restricted evidence in public issues, pull requests, documentation, or source files.

Report suspected security or privacy issues privately to `contact@crownthrive.com`. See `SECURITY.md`.

## Ownership and contact

**Institutional owner:** CrownThrive, LLC  
**Founding Member:** Kavonte Jones Sr.  
**Contact:** `contact@crownthrive.com`  
**Primary ecosystem:** `https://crownthrive.com`
