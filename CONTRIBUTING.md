# Contributing to the CrownThrive Operating System

Contributions are welcome only when they preserve CrownThrive's institutional authority, intellectual property, source lineage, cultural alignment, privacy, and release discipline.

Read `AGENTS.md` before opening or modifying a branch, issue, or pull request.

## Contribution does not establish rights or authority

Submitting text, code, diagrams, data, prompts, research, translations, media, schemas, or configuration does not automatically establish:

- ownership or authorship share;
- assignment to CrownThrive;
- license scope;
- compensation, royalty, commission, equity, or credit;
- confidentiality;
- production acceptance;
- legal, security, rights, cultural, or governance approval.

Do not submit material unless you have the authority to do so. Material contributions may require a separate contractor, employment, assignment, contributor-license, NDA, or other written agreement before acceptance.

## Never submit restricted material publicly

Do not place these in issues, pull requests, comments, commits, or public documentation:

- credentials, tokens, keys, recovery codes, or secret values;
- customer, employee, contributor, child, payment, identity, legal, health, or journal records;
- private contracts, rights evidence, legal strategy, or privileged communications;
- unreleased masters, manuscripts, source media, or confidential datasets;
- exploit-enabling security details;
- private economic schedules or partner terms;
- proprietary CHLOM, Fingerprint, policy, model, or other trade-secret implementation details.

Use the private disclosure path in `SECURITY.md` for sensitive findings.

## Required contribution record

A material pull request should identify:

- governing issue, run packet, release, or decision;
- intended audience and visibility class;
- source and evidence references;
- current state and affected stable IDs;
- human phase/patch and machine release;
- pages, registries, policies, platforms, APIs, MCPs, data, rights, commerce, search, and support affected;
- public claims added or changed;
- legal, privacy, security, accessibility, cultural, theological, or rights implications;
- tests performed and results;
- rollback, correction, or migration path;
- unresolved items and the exact next-run baseline.

## Workflow

1. **Inspect the current source.** Do not begin from a stale copy, prompt summary, or old public page when the governing record is available.
2. **Define scope.** One coherent issue or tightly related release per branch where practical.
3. **Resolve authority.** Identify the applicable owner, reviewer, source, rights, policy, and approval class.
4. **Preserve identity.** Reuse stable IDs; add aliases, versions, corrections, or successors rather than creating duplicates.
5. **Edit for the intended audience.** Public, member, developer, operator, founder, legal, and machine projections may differ, but must resolve to the same governing record.
6. **Validate.** Run `python3 scripts/validate_docs.py` and any additional platform-specific tests.
7. **Review the diff.** Remove unrelated changes, template residue, secrets, unsupported claims, and accidental public/private boundary changes.
8. **Open the pull request.** Complete the repository template and request the necessary reviewers.
9. **Reconcile after acceptance.** Update release notes, ADRs, registries, redirects, search, support, and next-run records where applicable.

## Governed merge gate

Every pull request into `main` must pass the required GitHub status check `CrownThrive governed merge gate`. The check is fail-closed. It validates, at minimum:

- documentation governance (`scripts/validate_docs.py` and the homepage control-plane projection);
- security governance (`scripts/validate_security_governance.py` and repository governance enforcement state);
- specialist classification against the nine-domain registry in `developers/manifests/agent-sovereign-governance.v1.json`;
- trusted Git diff binding — the changed-file set is derived from the exact base and head SHAs, and any packet-supplied `changed_files` list must match that trusted set exactly.

The gate is defense-in-depth. It does not replace A/B/C/D/S sovereign voting, Agent D independence, specialist endorsements, D3 human authority, or rollback and documentation reconciliation. It exists so those authorities cannot be silently bypassed by an unclassified file, a stale workflow, or a mismatched diff.

## GitHub Actions runtime and supply-chain rule

Any change under `.github/workflows/` must comply with `/standards/github-actions-runtime-supply-chain-standard`:

- Node 24 is the runtime floor. Node 20 action runtimes are prohibited.
- Every remote `uses:` reference must be pinned to a full 40-character commit SHA from the approved action inventory, with the human-readable version kept as a comment beside the SHA.
- Mutable tags, moving majors, abbreviated SHAs, self-hosted runners without attestation, and runtime escape-hatch variables (`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`, `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION`) are not valid repairs.
- `scripts/validate_github_actions_runtime_policy.py` runs inside the governed merge gate and blocks drift.

New or updated actions require an entry in the approved inventory before the pin can pass validation.

## Specialist endorsement domains

Material contributions are classified against nine specialist domains. Endorsements from every applicable domain are required for automatic D0–D2 promotion; unknown endorsement IDs fail closed. The domains are:

1. Security & Privacy
2. Legal / Regulatory
3. Operations / SRE
4. Blockchain / Cryptographic Protocol
5. AI / ML / LLM TEVV
6. IP / Rights / Licensing
7. Finance / Tax / Treasury
8. Accessibility / Consumer Protection
9. Regional / Global Localization

The set of required specialists is derived from a per-file classification of the trusted Git diff, not from a caller-supplied domain list. Known sensitive surfaces (workflows, the sovereign merge engine and manifest, governance validators, CHLOM policy/authority/evidence/rights/economics/API contracts) carry deterministic minimum-domain requirements. A documentation-only change may classify as neutral `documentation` when no specialist pattern matches. D3 changes remain authorized-human authority and cannot be produced by agent quorum.

See `/standards/autonomy-operating-constitution` and the `CT-ADR-GOV-011` amendment for the full authority contract.

## Pull request template fields

The repository template records the change's institutional reach. Two impact fields govern propagation:

- `docs_impact` — one of `docs_updated`, `docs_no_change`, or `docs_delta_opened`. Use `docs_delta_opened` when a documentation change is required but tracked as a follow-up, and link the follow-up.
- `homepage_impact` — one of `updated`, `no_change`, or `delta_opened`. Set `updated` whenever a headline institutional claim, primary control state, source census, ruleset posture, or primary navigation path changes. `scripts/validate_homepage_control_plane.py` runs inside the governed merge gate and blocks stale homepage state.

Both fields are read alongside the propagation checklist. A `no_change` selection must be defensible against the actual diff.

## Documentation rules

Every navigated MDX page requires:

- valid frontmatter;
- a unique, meaningful title and description;
- substantive body content;
- current/historical/proposed/research status where material;
- public-safe language and source discipline;
- correct internal links;
- no frontmatter-only placeholder state;
- no claim that an interface, legal structure, registration, payment, entitlement, SSO connection, API, or service exists without evidence.

## Version and correction rules

Use separate namespaces:

- human program phase;
- human audit patch;
- institutional machine release;
- service/API/MCP/schema/content/policy/rights/economic/model/deployment versions.

Corrections append. Preserve the original statement, effective period, source, reason, affected records, corrected value, approval, and propagation state.

Do not rewrite historical sources to sound current. Add a current overlay or supersession record.

## Claims and metrics

A metric must identify:

- metric ID and definition;
- population and inclusion/exclusion rule;
- source system;
- period or as-of date;
- deduplication method where applicable;
- evidence class;
- owner and refresh/expiration rule;
- approved public wording.

Do not transform records into members, projections into revenue, generated assets into released works, product cards into active SKUs, or historical plans into current capability.

## API, MCP, and integration contributions

Do not invent endpoints or integration state. Record the exact provider, product/version, environment, base URL, docs, authentication, scopes, rate limits, data classes, webhooks/events, errors, retries, support, export, health, and replacement path.

New production MCP designs target the `2026-07-28` protocol profile. Tool contracts must identify side effects, data classification, autonomy class, approvals, version, and rollback/compensation behavior.

## Review ownership

Required reviewers depend on impact:

- doctrine, portfolio, reserved decisions — founder/governance;
- rights, canon, provenance, licensing — CHLOM/rights steward;
- culture, representation, imprints, universes — Cultural Imprint Engine stewardship;
- legal-policy status — authorized legal/policy owner and qualified review where required;
- security, privacy, identity, secrets — security/privacy owner;
- money, pricing, payouts, credits — finance/commerce authority;
- API/MCP/data/deployment — engineering/platform owner;
- public content/search/accessibility — publishing, SEO, and accessibility review;
- ministry/Scripture content — authorized theological/editorial reviewer.

An agent or contributor must not approve its own consequential output.

## Acceptance standard

A contribution is accepted only when:

- the governed output exists;
- validation passes;
- rights, source, audience, and status are recorded;
- required approvals exist;
- public claims match evidence;
- downstream records are reconciled;
- failures and limitations remain visible;
- rollback/correction exists;
- the next run can inherit the state without rediscovery.

## Contact

Questions about contribution authority or private material: `contact@crownthrive.com`
