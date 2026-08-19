# CT-ADR-GOV-011 — Agent-Sovereign Governance, Quorum, Security and CHLOM Automation

- **Status:** accepted for implementation within Phase 2.99
- **Decision date:** 2026-08-18
- **Roadmap namespace:** `institutional_build_phase / ten_phase_v1`
- **Current phase:** Phase 2 / subphase 2.99
- **Phase 3 state:** blocked pending all remaining Phase 2.99 hard-exit requirements
- **Supersedes:** only the policy conclusion in S106-era records that GitHub branch/ruleset fail-closed merge enforcement is itself a Phase 2.99 hard-exit / Phase 3-entry requirement
- **Preserves:** the factual S106 observation that GitHub `main` was unprotected and required-status-check enforcement was off

## Decision

CrownThrive's own coded, registered and independently validating agents are the sovereign fail-closed automation authority for repository promotion. GitHub remains the repository transport, audit history, CI runner, security-analysis provider and post-merge defense-in-depth layer. GitHub branch protection/rulesets may be enabled later as an additional control, but they are not CrownThrive's trust anchor and are not independently required for Phase 3 entry.

This decision does **not** loosen the Phase 2.99 hard exit. It replaces one repository-provider-specific gate with a stronger provider-independent institutional gate: coded validation, security evidence, rule-based specialist activation, risk rating, quorum, independent gatekeeper approval, D0–D3 authority, rollback and documentation/downstream reconciliation.

## Five-agent sovereign voter pool

The institutional relay contains five vote-eligible roles:

1. `ct.relay.agent-a` — Orchestrator & Integrator
2. `ct.relay.agent-b` — Evidence & Reconciliation Auditor
3. `ct.relay.agent-c` — Build & Documentation Executor
4. `ct.relay.agent-d` — Independent Gatekeeper & Handoff Steward
5. `ct.relay.agent-s` — Security & Resilience Sentinel

Automatic D0–D2-eligible promotion requires `ceil(5 × 0.75) = 4` affirmative votes. Missing votes and abstentions are not approvals. Any `deny` or `block` prevents automatic merge. Agent D must independently approve.

One agent equals one vote. Confidence, model size, role prestige or provider identity does not create weighted voting.

## Risk and evidence gate

A packet must score at least `85/100` for automatic merge using the current dimensions:

- evidence quality — 30%;
- validation strength — 25%;
- security posture — 25%;
- reversibility — 10%;
- authority fit — 10%.

Hard blocks override the score. The score cannot convert a D3 action into an agent-authorized action.

## D3 remains human/reserved

No 4-of-5 or 5-of-5 agent vote can substitute for required human/reserved authority for consequential actions such as binding legal terms, rights or ownership changes, securities/token issuance/public sale, IP transfer, production credential rotation, privileged access change, destructive or irreversible production mutation, material money movement, privacy/security exceptions or other actions classified D3.

Agents may prepare, test, recommend, block and produce evidence for D3. Execution requires the applicable authorized human/professional decision.

## Security Governance and self-healing

Security is now a standing relay role and CI domain. Applicable changes consume:

- deterministic CrownThrive security-policy validation;
- CodeQL evidence;
- dependency-review evidence;
- provider secret-scanning/push-protection evidence when enabled/available;
- independent Agent S review;
- post-repair rerun of the original failed control;
- full institutional revalidation;
- independent gatekeeper verification.

Critical/high findings block automatic promotion until repaired/revalidated or escalated. Self-healing may fix deterministic D0/D1 defects automatically. D2 requires independent verification, applicable specialist endorsement, quorum and rollback. D3 remediation remains reserved.

A system may never “heal” by disabling or weakening the failing check, suppressing the finding, exposing/reconstructing a secret, broadening privileges, deleting evidence, fabricating state or self-approving its own material change.

## Rule-based specialist activation

The policy activates domain specialists when relevant:

- legal/regulatory;
- security/privacy;
- operations/SRE;
- blockchain/cryptographic protocol;
- AI/ML/LLM TEVV;
- IP/rights/licensing;
- finance/tax/treasury;
- accessibility/consumer protection;
- regional/global localization and succession.

Specialist agents support evidence, deterministic review and recommendations. They do not impersonate or replace qualified counsel, regulators, auditors or other licensed professionals when those roles are required.

## CHLOM / dS-CaaS architecture effect

CHLOM remains the governed rights/rules/roles/revenue/records/remedies spine and may evolve into a CrownThrive-owned institutional metaprotocol. dS-CaaS is the runtime compliance/governance enforcement profile consuming those records.

The target architecture may become context-aware, adaptive, self-checking and boundedly self-healing across AI/ML/LLM agents, conventional cloud services and later decentralized/cryptographic adapters. It is not sentient, self-authorizing or exempt from law/human authority.

Advanced blockchain, poly-chain, smart-contract, token, wallet, oracle, bridge or crypto-economic mechanisms remain Phase 9 research/target architecture until their validated use case, legal/regulatory, securities, money-transmission/BSA-AML, sanctions, tax/accounting, privacy, custody/key-management, smart-contract/bridge-security, consumer-disclosure and recovery gates pass.

No design artifact alone establishes a live CrownThrive cryptocurrency, security, legal tender, registered offering, compliant public sale or production decentralized settlement system.

## CrownThrive IP and licensing effect

Public-safe specifications, schemas, validators and reference implementation code may live in GitHub. Secrets, private evidence, restricted policy internals and protected implementation IP remain in controlled private systems.

Phase 6 may expose CHLOM/dS-CaaS APIs, SDKs, MCP surfaces, policy packs, certified adapters and compliance/governance services under explicit CrownThrive licensing and developer terms. Public visibility does not itself grant commercial, trademark, patent, copyright, trade-secret, redistribution or sublicensing rights.

## Gmail / Collab Portal tracking effect

Material merged passes use Gmail project-manager updates. Until the Collab Portal adapter is fully operationally certified, the runtime recipient set contains three private logical recipients: founder tracking, institutional tracking and the Collab Portal fallback tracking mailbox.

The public repository stores only recipient references. The actual Collab Portal inbound mailbox remains private runtime routing data.

The Collab fallback is disabled only after all seven predicates pass simultaneously:

1. exact credential match;
2. authenticated project metadata;
3. institutional project UID pinned;
4. approved account-specific field mapping;
5. authenticated project read;
6. bounded project write/read-back;
7. webhook sender/delivery integrity.

Any later regression reactivates the fallback. Founder and institutional Gmail tracking remain active.

## Supersession and precedence

Where an earlier S106-era current-policy sentence says any of the following, this ADR supersedes that **policy requirement** as of 2026-08-18:

- GitHub physical non-mergeability is required before CrownThrive can call its own automation fail-closed;
- GitHub branch protection/ruleset enforcement is itself a Phase 2.99 hard-exit requirement;
- GitHub branch protection/ruleset enforcement is itself a Phase 3 entry requirement.

The factual observation that GitHub protection/enforcement was off remains preserved and must not be rewritten as enabled.

## Downstream roadmap propagation

### Phase 3 — Executable Institutional Core

Implement the agent/quorum/risk/specialist/security decision records as executable institutional services. Provider branch protection is optional defense-in-depth; agent policy and all other Phase 2.99 entry requirements remain binding. DAIL must record votes, evidence, risk score, blockers, specialist endorsements, human-reserved approvals and rollback.

### Phase 4 — Federated Ecosystem Activation

Certified platform adapters inherit the same provider-independent authority model. A SaaS vendor, MCP server or repository host cannot silently become CrownThrive authority. Shared adapters preserve platform-specific roles, rights, data ownership and systems of record.

### Phase 5 — Revenue & Market Activation

Price, offer, attribution, consent, payment, fulfillment, entitlement and revenue-state transitions use executable rule gates. Historical economics or provider objects cannot become current commercial authority through agent consensus.

### Phase 6 — Licensing, IP & Developer Economy

External CHLOM/dS-CaaS developer/licensing access requires current IP/rights authority, contract terms, identity/scopes, security certification, API/SDK/MCP versioning, usage evidence and support/remedy controls. Agent quorum cannot issue a binding license absent the required authority.

### Phase 7 — Physical, Phygital & Regional Expansion

Device/location changes inherit safety, privacy, identity, incident, rollback and local-jurisdiction specialist gates. No kiosk/device deployment is authorized solely by a successful software vote.

### Phase 8 — Holdings, Capital & Portfolio Scale

Entity, capital, ownership, IP-custody and securities/investor actions remain D3. Agent automation may reconcile evidence and prepare decisions but cannot form entities, issue securities, transfer IP or move capital by quorum alone.

### Phase 9 — Advanced CHLOM & Interoperable Infrastructure

This becomes the primary activation phase for advanced cryptographic proofs, DID/VC, blockchain/poly-chain adapters, smart-contract settlement, token/crypto research and decentralized governance where conventional infrastructure has a proven limitation. Legal/security/privacy/custody/recovery gates remain mandatory.

### Phase 10 — Generational Continuity, Sovereign Scale & Institutional Permanence

Continuity artifacts must export policy/rule versions, agent registry, quorum formula, specialist activation, risk model, DAIL records, recovery procedures, model/provider inventories, cryptographic/key custody, notification routes and provider-exit procedures so CrownThrive can survive repository, cloud, model, vendor and leadership changes.

## Current hard-gate effect

`CT-ADR-GOV-011` removes only GitHub branch-protection/ruleset enforcement as an independent Phase 2.99/Phase 3 dependency. It does not resolve articleization, source/canonical-identity recovery, provider/account/version/deployment/API/export evidence, domain/DNS/TLS/runtime certification, Collab Portal certification or any other unresolved Phase 2.99 requirement.

Phase 3 therefore remains `blocked_pending_phase_2_99_hard_exit`.
