# Phase 3 Readiness Gate Amendment — CT-ADR-GOV-011

**Effective:** 2026-08-19  
**Current state:** `blocked_pending_phase_2_99_hard_exit`

This amendment preserves CrownThrive's agent-sovereign authority model, keeps GitHub subordinate to institutional authority, and makes the GitHub `main` merge perimeter a required Phase 2.99 hard-exit / Phase 3 hard-entry control.

## GitHub authority boundary

GitHub branch protection and rulesets are not CrownThrive's sovereign authority. CT-ADR-GOV-011 remains the authority root: 4-of-5 A/B/C/D/S quorum for eligible D0–D2 promotion, mandatory Agent D approval, risk score at least 85, applicable specialist endorsements, validation/security evidence, rollback/recovery, documentation/downstream reconciliation, and reserved human/qualified-professional authority for D3.

GitHub nevertheless must technically enforce the minimum canonical-branch perimeter so a failed or skipped repository control cannot be routinely merged into `main` and published through Mintlify.

## GitHub main merge perimeter is a Phase 3 hard-entry dependency

Before Phase 3 entry, provider evidence must show that canonical `main` requires:

- pull requests before merge;
- the stable required status context `CrownThrive governed merge gate`;
- strict/current-with-`main` status-check enforcement;
- force pushes blocked;
- branch deletion blocked;
- routine admin bypass disabled;
- bypass limited to explicit D3 break-glass authority with evidence and post-event revalidation.

The target machine source is `developers/manifests/github-main-enforcement-target.v1.json`.

The `Documentation Governance`, `Security Governance`, and `Governed Merge Gate` workflows must emit on every pull request. This prevents a required check from remaining permanently pending because a path filter skipped the workflow.

The current provider observation remains `branch_protected=false` / required checks off. Therefore this gate is **not yet satisfied**. PR #64 is the bootstrap packet that installs the always-run merge-gate substrate. Provider configuration must be enabled after that bootstrap is merged, then independently re-read from GitHub and recorded as provider evidence.

## Remaining repository-governance requirements

Before Phase 3 entry, CrownThrive must also prove:

- registered five-agent voter identities;
- deterministic 75% quorum = four of five affirmative votes;
- mandatory independent Agent D gatekeeper approval;
- minimum `85/100` automatic-merge risk score;
- successful institutional documentation validation;
- successful Security Governance validation;
- successful **GitHub Actions runtime gate** across every governed workflow;
- Node 24 as the current action runtime floor, with Node 20 prohibited;
- immutable full-length commit-SHA references for every remote workflow action;
- no runtime-warning suppression or insecure Node escape hatch used as a substitute for an action upgrade;
- no unverified self-hosted Actions runner;
- governed dependency update/self-healing through pull-request reconciliation rather than direct-to-`main` mutation;
- applicable CodeQL/dependency/secret-scanning evidence or explicit governed `not_applicable` state;
- rule-based specialist endorsement for changed domains;
- no unresolved critical/high security finding;
- no secret/restricted-data exposure;
- D0–D3 authority enforcement with D3 human/reserved;
- rollback/recovery evidence;
- documentation impact and downstream Phase 3–10 propagation;
- post-merge `main` revalidation retained as defense-in-depth.

## GitHub Actions runtime gate

The governing machine source is `developers/manifests/github-actions-runtime-policy.v1.json` and its deterministic validator is `scripts/validate_github_actions_runtime_policy.py`.

A Phase 3 entry decision fails if any governed workflow contains an unapproved or mutable remote action reference, a Node-20 action line, an unverified self-hosted runner, a prohibited runtime escape hatch, a duplicate advanced CodeQL configuration conflicting with provider-managed default setup, or an unreconciled action update.

Dependabot may propose GitHub Actions updates, but the proposal has no merge authority. Upstream runtime/security compatibility must be verified, the pinned workflow SHA and machine policy must be reconciled together, and the ordinary agent/security/quorum controls must pass.

## Remaining Phase 2.99 state

This amendment does not mark Phase 2.99 complete and does not satisfy Phase 3 entry by itself. Articleization/recovery, canonical identity and relationship work, provider/account/version/deployment/API/export verification, registrar/DNS/TLS/runtime verification, private-core/secrets architecture, Collab Portal certification, security/evaluation evidence and all other unresolved hard-exit requirements remain binding.

## Acceptance evidence

The repository-governance portion of Phase 3 readiness passes only when:

1. the machine manifests and validators agree;
2. the always-run workflows pass on representative PRs;
3. GitHub provider state independently confirms the target `main` ruleset/protection;
4. a failing required-check condition is demonstrably blocked from merge, or equivalent provider evidence proves the same enforcement;
5. the result is independently verified by the sovereign relay.

A prose declaration or successful CI run alone is insufficient.
