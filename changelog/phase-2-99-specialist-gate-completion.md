# Phase 2.99 — Rule-based specialist gate completion

- **State:** reconciled proposal / fail-closed pending fresh exact-head governance
- **Canonical reconciliation baseline:** `ee6175f627b228a13056620c0686f5e248374a57`
- **Risk class:** D2 governance-code hardening
- **Current phase:** Phase 2 / 2.99
- **Phase 3:** `blocked_pending_phase_2_99_hard_exit`

## Purpose

This packet closes the post-bootstrap mismatch between CrownThrive's specialist-governance doctrine and the executable merge-decision engine. The prior engine machine-required only Security and Legal/Regulatory endorsements. The reconciled engine derives specialist requirements from the governed registry and supports all nine rule-based specialist domains cumulatively.

## Canonical authority preserved

This reconciliation explicitly removes the branch's superseded unanimous-first / timed deadlock-override experiment. CT-ADR-GOV-011 remains:

- five sovereign voters: A/B/C/D/S;
- automatic D0-D2 promotion requires at least 4/5 approvals;
- Agent D must approve;
- any deny/block prevents automatic promotion;
- risk score must remain at or above 85;
- every applicable specialist endorsement is required;
- institutional, security, Node-24/runtime and governed-main-perimeter controls remain required;
- D3 remains authorized-human / qualified-professional authority and cannot be created by agent quorum.

The non-voting subagent registry adds scrutiny and execution depth but no sovereign vote or bypass authority. Core voter/quorum/D3/security invariants remain founder-reserved against self-amendment.

## Nine machine-enforced specialist domains

1. Security & Privacy — `security`
2. Legal / Regulatory — `legal_regulatory`
3. Operations / SRE — `operations_sre`
4. Blockchain / Cryptographic Protocol — `blockchain_protocol`
5. AI / ML / LLM TEVV — `ai_ml_llm_tevv`
6. IP / Rights / Licensing — `ip_rights_licensing`
7. Finance / Tax / Treasury — `finance_tax_treasury`
8. Accessibility / Consumer Protection — `accessibility_consumer_protection`
9. Regional / Global Localization — `regional_global_localization`

The decision engine normalizes changed-domain labels, reads patterns and endorsement IDs from `agent-sovereign-governance.v1.json`, and accumulates every matching specialist instead of maintaining a separate hard-coded lookup table.

Examples now covered by executable self-tests:

- `rights` => Legal + IP/Rights;
- `blockchain` => Security + Blockchain Protocol;
- `privacy` => Security + Legal;
- `royalty` => Legal + Finance;
- `cross-border` => Legal + Regional/Global;
- `settlement` => Blockchain Protocol + Finance.

The self-test also proves all nine stable endorsement IDs are registered, all nine can activate, missing cumulative endorsements fail closed, 4/5 remains the quorum, and D3 still cannot auto-merge.

## Self-healing and controlled evolution

The non-voting Governance Marshal may propose new non-voting subagents, validation patterns, evidence thresholds and refractory controls. It does not vote and cannot create merge authority. D0/D1 non-authority refinements remain validation/audit bounded. D2 governance changes require the existing CT-ADR-GOV-011 process and applicable specialists. Changes to the sovereign voter pool, 4/5 + Agent-D quorum, D3 boundary or security non-weakening invariants require explicit founder authorization.

Self-healing remains evidence preserving:

`detect -> preserve evidence -> bounded repair -> rerun original failed control -> rerun full applicable controls -> independent verification -> sovereign decision`

Validators, findings, evidence or privilege may never be weakened to force a pass.

## Reconciliation lineage

The pre-reconciliation branch was based on pre-PR-64 main and contained noncanonical unanimous-first/deadlock semantics. After PR #64 and PR #95 became canonical and issue #83 closed, the branch was merged forward onto `ee6175f...` without force-pushing or erasing historical lineage. The current proposal starts from the post-Node24/post-provider-perimeter tree and reapplies only the bounded specialist/subagent hardening compatible with canonical authority.

## Rollback / impact

Rollback is a normal revert of this packet. No provider, credential, customer, payment, binding rights, production infrastructure, Collab, token/crypto or restricted-evidence mutation is introduced.

Documentation impact: `docs_updated` through this public-safe changelog and the machine governance manifest. Phase 3-10 inherit cumulative specialist activation after canonical promotion, but this packet does not itself advance any phase or activate regulated/financial/cryptographic capability.
