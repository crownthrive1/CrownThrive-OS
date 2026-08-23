# Security and Private Disclosure 🔐

CrownThrive treats security, privacy, rights integrity, evidence custody, payment integrity, software-supply-chain integrity and institutional continuity as release requirements.

## Current security posture

As of the **August 23, 2026** public snapshot, CrownThrive is executing **Phase 2.99 — Private Core and Machine Seed Program** and Phase 3 entry remains `blocked_pending_phase_2_99_hard_exit`.

Public documentation may describe specified, controlled-test, recovered, historical, or target-state security architecture. That documentation must not be interpreted as production certification. Controlled-test bindings, provider readbacks, API contracts, workflow success, or a public payment surface do not independently prove that a production capability is authorized, fully hardened, rights-cleared, or ready for unrestricted use.

## Report privately

Do not disclose a suspected vulnerability, credential, private record, exploit path, protected identity, rights evidence or security-sensitive configuration in a public issue, discussion, pull request, screenshot or social post.

Send reports to:

`contact@crownthrive.com`

Use the subject line:

`Private Security Report — <affected platform or repository>`

## Include

Provide only the minimum information needed to investigate:

- affected CrownThrive platform, repository, route, API, MCP server, integration or vendor;
- environment and observed date/time;
- issue type and likely impact;
- reproducible steps using non-sensitive test data where possible;
- relevant request, correlation, event, release or error identifiers;
- screenshots or logs with credentials and personal data removed;
- whether exploitation, data access, payment, rights or service disruption occurred;
- safe contact information for follow-up.

Do not send passwords, private keys, full payment payloads, government identifiers, customer exports, private journals, unreleased masters or unnecessary personal data by ordinary email. State that protected evidence exists and request a controlled transfer method.

## Priority classes

- **C0 — existential:** loss of institutional control, source/rights destruction, widespread secret compromise or unrecoverable evidence loss.
- **C1 — critical:** unauthorized privileged access, material data exposure, payment/entitlement integrity failure, destructive agent action or broad production compromise.
- **C2 — material:** scoped platform, role, data, availability, privacy or supply-chain weakness with meaningful impact.
- **C3 — localized:** low-impact defect, hardening opportunity or issue with an effective existing control.

CrownThrive may reclassify a report as evidence develops.

## Continuous Security Governance

`CT-ADR-GOV-011` establishes a dedicated **Security & Resilience Sentinel (`ct.relay.agent-s`)** in the institutional agent relay. Security is therefore evaluated continuously rather than only after a release is built.

The repository security control plane combines the `Security Governance` workflow with independent provider-managed security capabilities:

- deterministic CrownThrive security-policy validation;
- GitHub CodeQL **default setup** when applicable, operated by GitHub rather than duplicated as an advanced CodeQL job inside CrownThrive's workflow;
- pull-request dependency review;
- provider secret-scanning/push-protection evidence when enabled and available;
- weekly scheduled CrownThrive policy revalidation in addition to change-triggered runs.

The initial PR #63 security run proved that GitHub CodeQL default setup was already enabled because a duplicate advanced CodeQL initialization was rejected. CrownThrive therefore removed the conflicting duplicate advanced job while retaining the requirement to consume actual provider CodeQL findings as independent evidence. A compatibility job now fails if an advanced CodeQL action is reintroduced while default setup remains the registered provider mode.

GitHub security products are valuable evidence and defense-in-depth, but GitHub is not CrownThrive's sovereign merge authority. CrownThrive's coded agent policy requires a failed applicable critical/high security control to block automatic merge even if GitHub repository settings would technically permit it.

The current Phase 2.99 readiness record also treats verified fail-closed repository enforcement as a separate gate. A workflow that runs is not automatically equivalent to a platform ruleset that prevents an unsafe merge.

## Agent security gate

An automatic D0–D2-eligible repository promotion requires, as applicable:

- deterministic Security Governance validation passed;
- no unresolved critical/high security finding;
- CodeQL/dependency/secret-scan evidence passed or explicitly documented `not_applicable`/unavailable with a risk decision;
- no credential or restricted-data exposure;
- security specialist endorsement for auth, secrets, APIs, workflows, crypto/blockchain, dependencies or production security changes;
- minimum `85/100` governed risk score;
- 4-of-5 agent quorum plus independent Agent D approval;
- rollback/recovery evidence.

D3 security decisions—credential rotation, privileged-access change, destructive/high-risk production migration, security-policy exception, key-custody change and equivalent actions—remain human/reserved authority. Agent quorum cannot substitute.

## Self-healing security controls

Self-healing means fixing the cause and proving the control passes afterward. It never means suppressing the finding.

Permitted patterns include:

- deterministic low-risk dependency/configuration repair;
- restoring a known-good non-secret configuration;
- bounded idempotent retry after a provider/transient failure;
- quarantining a vulnerable/uncertain capability;
- reverting a failed low-risk change;
- regenerating an approved artifact from an unchanged trusted schema;
- opening an incident and degrading to read-only/fail-closed;
- rerunning the original failing security control and full institutional suite;
- independent post-repair verification.

Agents must not self-heal by:

- weakening, removing or disabling the failing validator/security scan;
- dismissing a critical/high finding solely to permit merge;
- reconstructing, exposing or committing a secret;
- automatically rotating production credentials without D3 authority;
- silently expanding privileges or tool scopes;
- deleting evidence or rewriting incident history;
- self-approving the material change that created the finding.

## Payment, Stripe, and public funding surfaces

Public Stripe-hosted Payment Links may be intentionally published when they are approved for public use. The public URL is not a secret. The following remain private or restricted unless a governing record explicitly says otherwise:

- Stripe secret/API keys and restricted keys;
- webhook signing secrets;
- Dashboard session data and privileged account links;
- private customer/payment records;
- private dispute, payout, balance, tax, identity, or banking records;
- internal economic schedules or settlement instructions;
- credentials or privileged runtime references used by CrownThrive services.

Never paste a Stripe secret into a GitHub issue, pull request, documentation page, screenshot, code sample, or client-side application.

A Stripe payment success, Payment Link checkout, webhook delivery, provider receipt, or balance event is provider evidence. It does **not** independently create CrownThrive license rights, ownership, governance authority, entitlement, settlement, payout, revenue-recognition truth, charitable status, tax deductibility, or institutional approval. Those states require the applicable CHLOM/ThriveEvergreen and institutional reconciliation.

If a public Payment Link is suspected of tampering, misrouting, unauthorized replacement, credential compromise, or incorrect economic behavior, report it privately and treat affected downstream state as `HOLD` until reconciled.

## Response process

The governing process is:

```text
Receive/detect privately
→ preserve evidence
→ validate and classify
→ contain or place affected capability on hold
→ identify affected identities, data, money, rights and dependencies
→ activate required specialist gate
→ correct or mitigate within authority
→ rerun original failed control
→ run full institutional/security validation
→ independent verification / quorum where eligible
→ notify where required
→ restore
→ record incident/correction
→ update standards, tests and runbooks
```

CrownThrive does not mark a report resolved merely because a code change was proposed. Closure requires verified behavior, affected-state reconciliation and a recovery/monitoring record.

## AI/agent security

AI/ML/LLM and agent workflows are treated as privileged software operators when they can read sensitive state or invoke tools. Security review covers:

- prompt/rule injection and untrusted-data boundaries;
- tool scope and least privilege;
- secret/data exposure;
- model/provider/version changes;
- authorization separate from model confidence;
- independent verification for consequential actions;
- audit/DAIL evidence;
- rollback and kill-switch/fail-closed behavior;
- supply-chain and dependency posture;
- model/prompt/evaluation drift.

A model's confidence, output quality or quorum vote does not create legal or D3 authority.

## Cryptography / blockchain / token security

CHLOM's advanced cryptographic, blockchain, poly-chain and token concepts remain gated target architecture unless separately activated through the required institutional gates. Before production activation, the security package must address at least key custody/recovery, wallet/role separation, smart-contract review, oracle/bridge threats, upgrade authority, replay/idempotency, chain reorganization/finality assumptions, incident response, reversibility/exit, privacy and public-data boundaries.

Security readiness does not substitute for legal, securities, money-transmission/BSA-AML, sanctions, tax/accounting or jurisdiction-specific review.

## Notification and mailbox safety

Project-management Gmail notifications must never contain credentials, private evidence bodies or unnecessary restricted data. The public repository stores logical notification-recipient references, not private routing values. Private fallback mailboxes and ticket-ingress addresses remain runtime routing data unless explicitly approved for publication.

## Research boundaries

Do not:

- access or retain data beyond what is necessary to demonstrate the issue;
- disrupt services, payments, communications, backups or other users;
- perform social engineering, physical intrusion, extortion, credential stuffing, denial-of-service testing or destructive testing;
- test production payment or entitlement paths with unauthorized accounts;
- publish before CrownThrive has had a reasonable opportunity to investigate and correct;
- use a report to claim ownership, license rights, bounty entitlement, partnership or endorsement.

No bug bounty or compensation is promised unless a separate authorized written program or agreement applies.

## Supported source

Security fixes should target the current accepted branch or an explicitly supported release. Historical, research, draft and superseded documentation may remain visible for lineage and does not necessarily represent a supported runtime.

## Sensitive repository content

This public repository must not contain:

- production secret values;
- private customer, contributor, employee, child, payment, legal, health, identity or journal records;
- private rights evidence or contracts;
- unreleased source assets;
- privileged communications;
- exploit-enabling operational details;
- proprietary CrownThrive trade-secret implementations;
- private notification/ticket-ingress routing addresses unless explicitly approved for publication.

Suspected accidental exposure should be reported immediately and treated as an incident even if the file is later deleted, because Git history, caches, forks, indexes and logs may retain copies.

## Contact

CrownThrive, LLC  
`contact@crownthrive.com`
