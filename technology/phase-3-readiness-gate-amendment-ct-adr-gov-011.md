# Phase 3 Readiness Gate Amendment — CT-ADR-GOV-011

**Effective:** 2026-08-18  
**Current state:** `blocked_pending_phase_2_99_hard_exit`

This amendment changes one repository-governance dependency in the Phase 3 Readiness Gate while preserving every other hard gate.

## Superseded repository-provider dependency

Earlier S106-era gate language treated effective GitHub `main` branch/ruleset required-check enforcement and a provider-level blocked-failing-check test as a Phase 2.99 hard-exit and Phase 3-entry requirement.

Under `CT-ADR-GOV-011`, that provider-specific requirement is superseded. GitHub branch protection/rulesets are optional defense-in-depth, not CrownThrive's sovereign authority.

## Replacement hard repository-governance requirement

Before Phase 3 entry, CrownThrive's provider-independent repository governance must prove:

- registered five-agent voter identities;
- deterministic 75% quorum = four of five affirmative votes;
- mandatory independent Agent D gatekeeper approval;
- minimum `85/100` automatic-merge risk score;
- successful institutional documentation validation;
- successful Security Governance validation;
- applicable CodeQL/dependency/secret-scanning evidence or explicit governed `not_applicable` state;
- rule-based specialist endorsement for changed domains;
- no unresolved critical/high security finding;
- no secret/restricted-data exposure;
- D0–D3 authority enforcement with D3 human/reserved;
- rollback/recovery evidence;
- documentation impact and downstream Phase 3–10 propagation;
- post-merge `main` revalidation retained as defense-in-depth.

GitHub's actual branch-protection state must still be recorded accurately. The absence of GitHub protection alone does not fail this gate; a violation of the CrownThrive agent policy does.

## Remaining Phase 2.99 state

This amendment does not mark Phase 2.99 complete and does not satisfy Phase 3 entry by itself. Articleization/recovery, canonical identity and relationship work, provider/account/version/deployment/API/export verification, registrar/DNS/TLS/runtime verification, private-core/secrets architecture, Collab Portal certification, security/evaluation evidence and all other unresolved hard-exit requirements remain binding.

## Acceptance evidence

The repository-governance portion of Phase 3 readiness can pass only when the machine manifests, validators, security workflow, relay configuration, quorum/risk decision engine and independent validation all agree. A prose declaration alone is insufficient.
