# Contributing to the CrownThrive Operating System 🤝

**Phase 3 edition — effective 2026-08-26**

Thank you for helping improve CrownThrive's public-safe institutional record. Contributions are welcome only when they preserve CrownThrive's institutional authority, intellectual property, source lineage, cultural alignment, privacy, security, rights, evidence discipline, archive integrity, and release continuity.

Before contributing, read:

- `README.md` — current Phase 3 orientation;
- `docs/phase3/CURRENT_STATE.md` — current institutional state vocabulary and boundaries;
- `AGENTS.md` — repository authority, evidence, state, and automation rules;
- `CODE_OF_CONDUCT.md` — community and collaboration expectations;
- `LICENSE` and `PHASE-3-LICENSING-AND-MACHINE-USE-ADDENDUM.md` — rights and machine-use boundaries;
- `docs/archive/README.md` — historical/supersession policy;
- `SECURITY.md` — private disclosure requirements;
- `SUPPORT.md` — support versus issue-routing guidance.
- `standards/pentadocs-audience-and-component-standard.mdx` — required audience, page-profile, structure, and Mintlify component semantics for navigated documentation.

## Current contribution baseline

CrownThrive is operating in **Phase 3 / OS 3.x**. Phase 3 is the institutional generation, not a blanket certification of every component. Contributors must preserve independent component state, version, provider authority, and evidence.

The public Help Center recovery/rebuild estate and earlier Phase 2.x work remain part of institutional history and continuing reconciliation. Do not reuse an old phase/status page as current truth merely because it is still accessible.

Work from current `main`, current effective registries/policies, and the governing evidence relevant to the change—not from an old screenshot, prompt summary, historical page, or model memory.

## Contribution does not establish rights or authority

Submitting text, code, diagrams, data, prompts, research, translations, media, schemas, configuration, tests, or machine-generated material does not automatically establish ownership, authorship share, assignment, license scope, compensation, royalty, commission, equity, credit, confidentiality, partnership, sponsorship, endorsement, production acceptance, certification, or legal/security/rights/cultural/economic/governance approval.

Do not submit material unless you have authority to do so. Material contributions may require a contractor, employment, assignment, contributor-license, NDA, invention assignment, media/data/model release, or other written agreement before protected or commercial incorporation.

## Never submit restricted material publicly

Do not place these in issues, pull requests, comments, commits, discussions, screenshots, or public documentation:

- credentials, tokens, keys, recovery codes, cookies, secret values, or private notification routes;
- customer, employee, contributor, child, payment, identity, legal, health, journal, or other private records;
- private contracts, rights evidence, legal strategy, privileged communications, or private economic schedules;
- unreleased masters, manuscripts, source media, confidential datasets, protected evaluations, private prompts, or protected evidence;
- exploit-enabling security details;
- proprietary CHLOM, CIE calibration, Fingerprint, policy, algorithm, model, economic, security, or other trade-secret implementation details.

Use the private disclosure path in `SECURITY.md` for sensitive findings.

## Required contribution record

A material pull request should identify:

- governing issue, run packet, release, ADR, standard, directive, or decision;
- intended audience and visibility class;
- source and evidence references;
- current state and affected stable IDs;
- institutional phase plus any applicable service/API/MCP/schema/content/policy/economic/deployment version;
- pages, registries, policies, platforms, APIs, MCPs, data, rights, commerce, search, support, archive, and recovery surfaces affected;
- public claims added, changed, removed, or superseded;
- legal, privacy, security, accessibility, cultural, theological, rights, or economic implications;
- tests and readbacks performed;
- rollback, correction, compensation, migration, or archival path;
- unresolved items and exact next-run baseline.

## Workflow

1. **Inspect current source.** Start from current `main` and governing records.
2. **Define one coherent scope.** Avoid unrelated cleanup in a material governance change.
3. **Resolve authority.** Identify owner, reviewer, rights, policy, and approval class.
4. **Preserve identity.** Reuse stable IDs; use aliases, versions, corrections, merges, splits, or successors instead of silent duplicates.
5. **Separate state dimensions.** Keep historical, current, proposed, candidate, controlled-test, hold, built-undepployed, provider-capable, write-verified, and production states distinct.
6. **Edit for the audience.** Public, member, developer, operator, founder, legal, and machine projections may differ but must resolve to the same governing record.
7. **Handle history deliberately.** If a page is stale but evidence-worthy, preserve and mark/move it under the archive model rather than rewriting history or deleting lineage.
8. **Validate.** Run `python3 scripts/validate_docs.py` and every scope-specific validator required by the changed area.
9. **Review the diff.** Remove unrelated changes, secrets, stale claims, template residue, unsupported promotion, broken links, and accidental visibility changes.
10. **Open a pull request.** Complete the repository template and request applicable review.
11. **Reconcile after acceptance.** Update releases, ADRs, registries, redirects, search, support, tests, evaluation fixtures, archive/supersession metadata, and next-run records where applicable.

## Documentation rules

Every navigated MDX page requires valid frontmatter, unique title/description, substantive content, material state, public-safe language, source discipline, correct internal links, and no unsupported production/legal/provider/economic claims.

Every new or materially changed navigated page must conform to the PentaDocs Audience and Component Standard. Record `standard_version`, `primary_audience`, `page_type`, and `content_state`; begin the body with the page-type audience guide; use frontmatter as the page H1; and select Mintlify components for their documented meaning rather than decoration. `CardGroup` is deprecated in new work; use responsive `Columns` with `Card` elements. Historical and superseded pages require a visible boundary and a current successor when one is known.

Run `python3 scripts/pentadocs_quality.py --check` directly when developing documentation. `python3 scripts/validate_docs.py` invokes the same gate in the normal repository validation path. A quality PASS proves source-format and corpus-contract conformance only; it does not prove provider deployment, independent review, institutional acceptance, or runtime certification.

Recovered historical bodies must not be rewritten to manufacture present-day authority. Preserve history and add a current overlay, disposition, correction, or successor record.

A current page must not claim that an interface, legal structure, registration, payment, entitlement, SSO connection, API, MCP, provider relationship, service, write path, or deployment is active without the evidence required for that specific claim.

## Version and correction rules

Keep separate namespaces for:

- institutional program phase / OS umbrella release;
- audit/remediation patch where one exists;
- service/API/MCP/schema/content/policy/rights/economic/model/deployment versions;
- source version and effective period.

Phase 3 does not force a valid v1/v2 component contract to become v3. Renumber only when that component itself materially changes under its version policy.

Corrections append. Preserve the original statement, effective period, source, reason, affected records, corrected value, approval, and propagation state.

## Claims and metrics

A metric should identify metric ID/definition, population and inclusion/exclusion rules, source system, period/as-of date, deduplication method, evidence class, owner, refresh/expiration rule, and approved public wording.

Do not transform records into members, projections into revenue, generated assets into released works, product cards into active SKUs, provider capability into write authority, successful payment UI into settlement/entitlement, or historical plans into current capability without the governing reconciliation.

## AI, agent, API, MCP, factory, and integration contributions

Do not invent endpoints, tools, credentials, providers, integrations, capabilities, approvals, certifications, releases, or deployment state.

Record exact provider/product/version, environment, base URL, documentation source, authentication method, scopes, rate/budget limits, data classes, events/webhooks, errors, retries, support/export path, health, replacement path, and evidence state when known.

Tool contracts must identify side effects, data classification, autonomy class, approvals, version, rollback/compensation behavior, and independent verification requirements.

An agent or contributor must not approve its own consequential output where separation of duties is required. Factory scale never creates additional authority.

## Review ownership

Required reviewers depend on impact:

- doctrine, portfolio, reserved decisions — founder/governance;
- rights, provenance, licensing, evidence authority — CHLOM/rights stewardship;
- culture, representation, imprints, universes, canon — Cultural Imprint Engine stewardship;
- legal-policy status — authorized policy owner and qualified professional review where required;
- security, privacy, identity, secrets — security/privacy stewardship;
- money, pricing, payouts, credits, commerce activation — finance/commerce/ThriveEvergreen authority;
- API/MCP/data/deployment/provider writes — engineering/platform authority;
- public content/search/accessibility — publishing, SEO, and accessibility review;
- ministry/Scripture content — authorized theological/editorial review.

## Acceptance standard

A contribution is accepted only when applicable evidence shows that the governed output exists, validation passes, rights/source/audience/status/versions are recorded, required approvals exist, public claims match evidence, downstream records are reconciled or an explicit delta is opened, failures/limitations remain visible, rollback/correction exists where required, and the next run can inherit state without rediscovery.

A merged documentation change does not independently certify corresponding runtime, legal, security, rights, economic, provider-write, or production state.

## Questions

For contribution authority or public-safe repository questions, see `SUPPORT.md` or contact **contact@crownthrive.com**. For sensitive security/privacy findings, follow `SECURITY.md` and do not open a public issue.
