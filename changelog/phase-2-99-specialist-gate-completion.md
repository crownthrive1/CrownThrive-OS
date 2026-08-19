# Phase 2.99 — Specialist Gate Completion + Unanimous-First Governance Packet

- **State:** proposed / fail-closed pending CT-ADR-GOV-011 adjudication
- **Baseline:** `12f0dd9ab97391a8dd34438f77262438c0df0999`
- **Risk class:** D2 governance-code hardening
- **Current phase:** Phase 2 / subphase 2.99
- **Phase 3:** `blocked_pending_phase_2_99_hard_exit`

## Purpose

This packet completes rule-based specialist enforcement and upgrades CrownThrive's sovereign-agent decision model from a normal 4-of-5 quorum to **unanimous-first governance**.

Normal promotion now requires all five sovereign relay agents A/B/C/D/S to approve. Agent D remains the mandatory independent gatekeeper. Missing votes and abstentions never count as approval.

## Disciplined deadlock override

Unanimity is the default, not an absolute veto forever. If one non-hard disagreement remains after a reasonable evidence-reconciliation window, the non-voting Governance Marshal may initiate a special deadlock vote only when all of the following are true:

1. at least **6 hours** have elapsed since the first valid sovereign vote;
2. at least **two reconciliation attempts** are documented;
3. all five sovereign agents have cast a vote;
4. at least **2/3 of the sovereign pool, rounded up**, approves — with five voters this is **4/5**;
5. Agent D approves;
6. Agent S approves whenever Security is an activated specialist domain;
7. the risk score remains at or above 85;
8. all required specialist endorsements are present;
9. required CI/security evidence is current and passing;
10. no hard block exists;
11. the dissent has been classified as non-hard after evidence reconciliation; a substantive unresolved defect remains a hard block rather than becoming override-eligible merely because time elapsed.

The deadlock override cannot be used to bypass D3/human-reserved authority, critical/high security findings, secret/credential/privilege failures, legal/rights authority blocks, missing specialist evidence, failed or stale required CI, or destructive/irreversible production concerns.

## Specialist and subagent architecture

The packet machine-registers the nine rule-based specialist domains: Security; Legal/Regulatory; Operations/SRE; Blockchain/Cryptographic Protocol; AI/ML/LLM TEVV; IP/Rights/Licensing; Finance/Tax/Treasury; Accessibility/Consumer Protection; and Regional/Global Localization.

It also establishes governed non-voting subagents for Governance Marshal, Verification/TEVV, Recovery/Rollback, Evidence/Provenance, and the specialist domains above. Subagents increase scrutiny and execution depth without diluting the five sovereign votes.

## Controlled evolution and self-healing

The Governance Marshal may propose new non-voting subagents, validation patterns, evidence thresholds, retry budgets, refractory intervals, validators, and handoff routing as CrownThrive grows.

Fluid areas remain bounded. Changes to the five sovereign voter identities, normal unanimity, the 2/3 deadlock-override floor, Agent D's independent gate, D3 human-reserved authority, no-secret-exposure rules, or no-security-weakening rules require founder authorization.

Self-healing remains refractory and evidence-preserving:

`detect -> preserve evidence -> bounded repair -> rerun original failed control -> rerun full applicable control family -> independent verification -> sovereign decision`

The same failure may not be repeatedly retried without new evidence or root-cause reassessment. Validators or security controls may never be weakened to make a failing packet pass.

## Why this is stronger than the former 4-of-5 default

The previous model allowed one dissenting sovereign agent to be outvoted immediately. The unanimous-first model forces the system to resolve disagreement, reconcile evidence, and expose hidden assumptions before promotion. The 6-hour 4-of-5 special vote prevents one stale or non-hard dissent from creating indefinite deadlock.

This creates a two-stage decision system:

- **Stage 1: consensus discipline — 5/5**
- **Stage 2: documented deadlock resolution — 4/5 after the wait/reconciliation protocol**

The second stage is not a shortcut and cannot override hard safety, security, legal, authority, specialist, or D3 gates.

## Rollback

The packet is fully reversible by reverting its PR. It does not mutate providers, credentials, customer data, payment state, rights, production infrastructure, Collab Portal, token/crypto systems, or regulated authority.

## Phase 3–10 impact

- **Phase 3:** approval/rules/DAIL services inherit unanimous-first + disciplined deadlock resolution.
- **Phase 4:** federated adapters inherit cumulative specialist activation and evidence reconciliation.
- **Phase 5:** financial/commercial changes can require Legal, Finance, Consumer and Security simultaneously.
- **Phase 6:** licensing/developer changes can require Legal, IP, Security and API specialists together.
- **Phase 7:** physical/phygital/regional changes can require Ops, Accessibility, Security and Regional/Global specialists.
- **Phase 8:** Holdings/capital changes can require Legal, Finance, IP and Regional/Global review while remaining D3 where applicable.
- **Phase 9:** advanced CHLOM/blockchain/token/AI work can require Security, Legal, Blockchain, AI, Finance, IP and Regional specialists cumulatively; D3 restrictions remain.
- **Phase 10:** succession/provider-exit/localization changes can require Ops and Regional/Global specialists without losing other applicable controls.

This packet does not advance Phase 3 and does not activate any regulated, financial, cryptographic or production capability.
