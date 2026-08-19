# Phase 2.99 — Specialist Gate Completion Packet

- **State:** proposed / fail-closed pending CT-ADR-GOV-011 quorum
- **Baseline:** `12f0dd9ab97391a8dd34438f77262438c0df0999`
- **Risk class:** D2 governance-code hardening
- **Current phase:** Phase 2 / subphase 2.99
- **Phase 3:** `blocked_pending_phase_2_99_hard_exit`

## Finding

The post-merge self-audit of CT-ADR-GOV-011 found a machine-enforcement gap. The documentation and relay prompts named nine rule-based specialist cells, but the first `governed_merge_decision.py` implementation only required machine endorsements for Security and Legal/Regulatory domain patterns.

That mismatch could allow a future D2 packet involving Operations/SRE, Blockchain/Cryptographic Protocol, AI/ML/LLM TEVV, IP/Rights/Licensing, Finance/Tax/Treasury, Accessibility/Consumer Protection, or Regional/Global Localization to satisfy quorum without the specialist endorsement promised by the institutional policy.

## Correction

This packet does not weaken or bypass the new controls. It:

- registers all nine specialist cells with stable `endorsement_id` values and rule-based activation patterns;
- derives required specialists dynamically from the manifest rather than duplicating a second hard-coded map in the decision engine;
- makes overlapping domains cumulative—for example `rights` requires both Legal/Regulatory and IP/Rights/Licensing, `blockchain` requires Security and Blockchain/Cryptographic Protocol, and `cross-border` requires Legal/Regulatory and Regional/Global Localization;
- validates that exactly nine specialist cells remain registered;
- self-tests every specialist cell plus cross-domain overlaps;
- preserves the 4-of-5 quorum, mandatory Agent D gate, `>=85` risk threshold, D3 human-reserved boundary, GitHub non-sovereign role and all existing security/Collab controls.

## Why this packet is not auto-merged by its author

CT-ADR-GOV-011 is already canonical on `main`. This correction changes governance code and is therefore treated as D2. It must pass the newly activated prospective process rather than relying on the bootstrap exception used for PR #63.

Before merge, the packet requires:

1. institutional and Security Governance CI green;
2. risk score at or above 85;
3. applicable specialist review, including Security because governance code/security policy execution is affected;
4. four of five affirmative A/B/C/D/S votes;
5. affirmative Agent D gatekeeper vote;
6. no deny/block vote;
7. rollback/recovery confirmed;
8. documentation impact and Phase 3–10 consequences reviewed.

## Rollback

The packet is fully reversible by reverting its PR. It does not mutate providers, credentials, customer data, payment state, rights, production infrastructure, Collab Portal or token/crypto systems.

## Phase 3–10 impact

- **Phase 3:** Approval/rules/DAIL services must preserve cumulative rule-based specialist activation rather than a single-specialist shortcut.
- **Phase 4:** Federated adapters inherit the applicable specialist set by changed domain.
- **Phase 5:** Financial/commercial changes can require Legal, Finance, Consumer and Security simultaneously.
- **Phase 6:** Licensing/developer changes can require Legal, IP, Security and API specialists together.
- **Phase 7:** Physical/phygital/regional changes can require Ops, Accessibility, Security and Regional/Global specialists.
- **Phase 8:** Holdings/capital changes can require Legal, Finance, IP and Regional/Global review while remaining D3 where applicable.
- **Phase 9:** Advanced CHLOM/blockchain/token/AI changes can require Security, Legal, Blockchain, AI, Finance, IP and Regional specialists cumulatively; D3 restrictions remain.
- **Phase 10:** Succession/provider-exit/localization changes can require Ops and Regional/Global specialists without losing other applicable controls.

This packet does not advance Phase 3 and does not activate any regulated, financial, cryptographic or production capability.
