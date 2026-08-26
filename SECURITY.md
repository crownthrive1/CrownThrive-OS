# Security and Private Disclosure 🔐

**Phase 3 edition — effective 2026-08-26**

CrownThrive treats security, privacy, rights integrity, evidence custody, payment integrity, software-supply-chain integrity, rollback, recovery, and institutional continuity as release requirements.

## Current security posture

CrownThrive is operating in **Phase 3 / CrownThrive OS 3.x**. The former `blocked_pending_phase_2_99_hard_exit` description is historical and must not be reused as current security posture.

**CrownThrive OS is the institutional source of truth.** Security state is recorded in the OS and its bound evidence: accepted repository state, ThriveBase operational records, CHLOM/DAIL evidence, current component records, exact release/workflow receipts, and verified provider evidence within scope.

Mintlify, websites, dashboards, screenshots, provider pages, and other public/projection surfaces do not independently establish security authority or current institutional state. They may surface drift or evidence that must be reconciled into the OS.

Phase 3 does not imply every subsystem is production-certified. Controlled-test bindings, provider capability, API/MCP contracts, workflow success, a public payment surface, or a generated artifact do not independently prove unrestricted production authority, complete hardening, rights clearance, or commercial activation.

## Report privately

Do not disclose a suspected vulnerability, restricted access material, private record, exploit path, protected identity, rights evidence, or security-sensitive configuration in a public issue, discussion, pull request, screenshot, or social post.

Send reports to **contact@crownthrive.com** with subject:

`Private Security Report — <affected platform or repository>`

Provide only the minimum information necessary to investigate. If protected evidence exists, state that fact and request a controlled transfer method.

## Include

Where possible provide:

- affected CrownThrive stable platform/component ID, repository, route, API/MCP surface, integration, or provider;
- environment and observed date/time;
- issue type and likely impact;
- reproducible steps using non-sensitive test data;
- relevant request/correlation/event/release identifiers;
- sanitized screenshots or logs;
- whether data access, money movement, rights, entitlement, provider mutation, or service disruption occurred;
- safe contact information for follow-up.

## Severity classes

- **C0 — existential:** loss of institutional control, source/rights destruction, systemic compromise, or unrecoverable evidence loss.
- **C1 — critical:** unauthorized privileged access, material data exposure, payment/entitlement integrity failure, destructive automation, or broad production compromise.
- **C2 — material:** scoped platform/role/data/availability/privacy/supply-chain weakness with meaningful impact.
- **C3 — localized:** low-impact defect, hardening opportunity, or issue contained by effective controls.

CrownThrive may reclassify a report as evidence develops.

## Continuous security governance

Security is evaluated continuously through OS-governed workflows, specialist/agent controls, repository validation, provider-managed security evidence where applicable, dependency/supply-chain checks, runtime observations, and recovery controls.

A security workflow that runs is not automatically equivalent to an effective provider ruleset, production authorization, or protected deployment. Repository enforcement, runtime certification, provider state, and institutional authority remain separate dimensions.

Provider-managed scanners and security products are evidence and defense-in-depth. They do not replace CrownThrive OS governance or manufacture permission to merge/deploy a consequential change.

## Agent and factory security gate

For eligible automated/reversible work, the applicable CrownThrive control must establish sufficient evidence, authority, specialist review, rollback, and separation of duties before execution/promotion.

Agents and factories may observe, prepare, test, quarantine, retry bounded reversible operations, generate candidates, and execute within separately granted authority. They may not:

- manufacture D3/sovereign authority;
- self-approve consequential actions where separation of duties is required;
- convert `HOLD` to `PASS` without required evidence;
- infer provider-wide authority from one certified operation;
- weaken or remove a failing security check merely to clear CI;
- conceal evidence, incidents, or uncertainty;
- silently expand permissions or action scope.

D3 security decisions and equivalent reserved actions remain human-controlled unless the governing constitution is separately changed.

## Self-healing security controls

Self-healing means correcting the cause and proving the control afterward—not suppressing the finding.

Permitted patterns can include deterministic low-risk repair, known-good configuration restoration, bounded idempotent retry, quarantine, reversible rollback, regeneration from trusted schemas, degradation to read-only/fail-closed, rerunning original controls, and independent post-repair verification.

Self-healing must not reconstruct or publish restricted material, erase incident history, silently broaden privileges, auto-waive a required approval, or mark a failure resolved without evidence.

## Provider-write and deployment security

Phase 3 uses operation-level/provider-specific certification. A provider being connected or technically capable does not mean CrownThrive has authorized all mutations.

Where a write path requires certification, current evidence must support the exact operation and applicable controls such as bounded scope, appropriate authorization, readback, idempotency/duplicate control, rollback or compensation, audit evidence, and fail-closed behavior.

A component or provider lane that lacks its required evidence remains candidate/blocked/HOLD rather than being promoted for convenience.

## Payment and economic surfaces

A public payment link may be intentionally public. Private account/security information and non-public customer, settlement, dispute, payout, banking, tax, or operational records remain outside public Git and documentation.

Provider evidence such as checkout success, webhook delivery, transaction/balance events, or API responses does **not** independently establish CrownThrive license rights, ownership, entitlement, settlement, revenue-recognition truth, charitable/tax status, or institutional approval. Those states require the applicable OS, CHLOM, ThriveEvergreen, and financial/evidence reconciliation.

Suspected payment-route tampering or economic-integrity issues should be treated as HOLD until reconciled.

## Response process

```text
receive/detect privately
→ preserve evidence
→ classify severity and affected scope
→ contain / reduce authority / HOLD where necessary
→ identify affected identities, data, money, rights and dependencies
→ apply required specialist/governance gate
→ correct or mitigate within authority
→ rerun the original failed control
→ run broader regression/security validation
→ independent verification where required
→ restore only with evidence
→ record incident/correction in the OS
→ update tests, standards, runbooks and archive lineage
```

Closure requires verified behavior and affected-state reconciliation, not merely a proposed code change.

## AI/agent security

AI/ML/LLM and agent workflows are privileged software operators when they can read protected state or invoke tools. Security review considers untrusted-input/prompt injection, least privilege, protected-data exposure, provider/model/version changes, authorization separate from model confidence, independent verification, DAIL/audit evidence, rollback/fail-closed controls, dependency posture, and evaluation drift.

A model's confidence, generated output, or agent consensus does not create legal, rights, economic, provider-write, or D3 authority.

## Advanced cryptographic/decentralized concepts

CHLOM cryptographic, blockchain, poly-chain, token, bridge, validator, or decentralized-settlement concepts remain governed by their actual active state. Historical or target architecture is not production truth. Any production activation requires the applicable security, rights/legal, recovery, custody, privacy, economic, and jurisdiction-specific review.

## Research boundaries

Do not exceed authorized access or retain unnecessary data. Do not perform destructive testing, denial-of-service, social engineering, physical intrusion, extortion, credential stuffing, unauthorized payment/entitlement tests, or public disclosure that creates unnecessary risk.

No bug bounty or compensation is promised unless a separate authorized written program/agreement applies.

## Supported source

Security fixes target the current accepted OS/component branch or an explicitly supported release. Historical, research, draft, archived, and superseded material may remain visible for lineage and does not necessarily represent a supported runtime.

## Public repository boundary

This repository must not contain restricted CrownThrive records, private contracts/privileged communications, raw private customer/personnel/financial/identity/health/journal records, restricted rights evidence, unreleased protected masters, or private trade-secret implementation details.

Suspected accidental exposure remains an incident even after deletion because Git history, caches, forks, indexes, logs, or mirrors may retain copies.

## Contact

**CrownThrive, LLC**  
**contact@crownthrive.com**

Security policy changes are governed by CrownThrive OS. Downstream documentation/web projections inherit this state; they do not define it.
