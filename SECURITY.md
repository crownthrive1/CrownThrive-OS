# Security and Private Disclosure

CrownThrive treats security, privacy, rights integrity, evidence custody, payment integrity, and institutional continuity as release requirements.

## Report privately

Do not disclose a suspected vulnerability, credential, private record, exploit path, protected identity, rights evidence, or security-sensitive configuration in a public issue, discussion, pull request, screenshot, or social post.

Send reports to:

`contact@crownthrive.com`

Use the subject line:

`Private Security Report — <affected platform or repository>`

## Include

Provide only the minimum information needed to investigate:

- affected CrownThrive platform, repository, route, API, MCP server, integration, or vendor;
- environment and observed date/time;
- issue type and likely impact;
- reproducible steps using non-sensitive test data where possible;
- relevant request, correlation, event, release, or error identifiers;
- screenshots or logs with credentials and personal data removed;
- whether exploitation, data access, payment, rights, or service disruption occurred;
- safe contact information for follow-up.

Do not send passwords, private keys, full payment payloads, government identifiers, customer exports, private journals, unreleased masters, or unnecessary personal data by ordinary email. State that protected evidence exists and request a controlled transfer method.

## Priority classes

- **C0 — existential:** loss of institutional control, source/rights destruction, widespread secret compromise, or unrecoverable evidence loss.
- **C1 — critical:** unauthorized privileged access, material data exposure, payment/entitlement integrity failure, destructive agent action, or broad production compromise.
- **C2 — material:** scoped platform, role, data, availability, privacy, or supply-chain weakness with meaningful impact.
- **C3 — localized:** low-impact defect, hardening opportunity, or issue with an effective existing control.

CrownThrive may reclassify a report as evidence develops.

## Response process

The governing process is:

```text
Receive privately
→ preserve evidence
→ validate and classify
→ contain or place affected capability on hold
→ identify affected identities, data, money, rights and dependencies
→ correct or mitigate
→ test and reconcile
→ notify where required
→ restore
→ record incident/correction
→ update standards, tests and runbooks
```

CrownThrive does not mark a report resolved merely because a code change was proposed. Closure requires verified behavior, affected-state reconciliation, and a recovery or monitoring record.

## Research boundaries

Do not:

- access or retain data beyond what is necessary to demonstrate the issue;
- disrupt services, payments, communications, backups, or other users;
- perform social engineering, physical intrusion, extortion, credential stuffing, denial-of-service testing, or destructive testing;
- test production payment or entitlement paths with unauthorized accounts;
- publish before CrownThrive has had a reasonable opportunity to investigate and correct;
- use a report to claim ownership, license rights, bounty entitlement, partnership, or endorsement.

No bug bounty or compensation is promised unless a separate authorized written program or agreement applies.

## Supported source

Security fixes should target the current accepted branch or an explicitly supported release. Historical, research, draft, and superseded documentation may remain visible for lineage and does not necessarily represent a supported runtime.

## Sensitive repository content

This public repository must not contain:

- production secret values;
- private customer, contributor, employee, child, payment, legal, health, identity, or journal records;
- private rights evidence or contracts;
- unreleased source assets;
- privileged communications;
- exploit-enabling operational details;
- proprietary CrownThrive trade-secret implementations.

Suspected accidental exposure should be reported immediately and treated as an incident even if the file is later deleted, because Git history, caches, forks, indexes, and logs may retain copies.

## Contact

CrownThrive, LLC  
`contact@crownthrive.com`
