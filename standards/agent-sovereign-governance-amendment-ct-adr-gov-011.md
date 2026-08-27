# Governance Standard Amendment — CT-ADR-GOV-011

**Effective:** 2026-08-19  
**Applies to:** `ct.standard.docs-autonomy.v1`, repository automation, agent relay, CI/security evidence and current Phase 3 execution. Historical origin: Phase 2.99-to-3 transition.

This amendment preserves CrownThrive's agent-sovereign authority model while restoring GitHub `main` protection as a required technical enforcement perimeter. GitHub remains infrastructure and evidence, not CrownThrive's sovereign authority.

## Current governance tiers

CrownThrive distinguishes five related states:

1. **policy detection** — a validator or security scanner detects a violation;
2. **provider enforcement** — GitHub or another provider technically prevents an invalid transition;
3. **agent-sovereign enforcement** — CrownThrive's registered agents refuse promotion unless coded institutional policy passes;
4. **reserved human authority** — D3 actions require an authorized human/professional even when agent quorum passes;
5. **post-promotion revalidation** — canonical state is independently rechecked for drift, bypass or regression.

For `crownthrive1/CrownThrive-OS`, state 3 remains the sovereign decision authority. State 2 is now a **required defense-in-depth merge perimeter** for canonical `main`, not the authority root. State 5 remains required.

## Automatic merge contract

An automatic D0–D2-eligible merge requires:

- current-state/collision reconciliation;
- documentation validation;
- security validation and applicable provider scan evidence;
- the always-run `CrownThrive governed merge gate` status passing;
- no secret/restricted-data exposure;
- risk score at least `85/100`;
- required specialist endorsements;
- `4/5` affirmative votes (`75%`, rounded up);
- independent Agent D approval;
- no deny/block vote;
- rollback/recovery;
- documentation impact;
- downstream PENTA Phase 4 — Verify and Phase 5 — Preserve reconciliation.

D3 is never auto-authorized by quorum.

## Required GitHub merge perimeter

The canonical `main` branch must be configured so routine publication cannot bypass the institutional controls. The target provider enforcement is:

- pull request required before merge;
- required status context `CrownThrive governed merge gate`;
- required branch to be current with `main` before merge;
- force pushes blocked;
- branch deletion blocked;
- routine administrative bypass disabled;
- bypass permitted only through an explicitly authorized D3 break-glass action with evidence and post-event revalidation.

Documentation Governance and Security Governance must emit on every pull request so they can remain inspectable independent evidence and do not become permanently pending because of path-filter skips.

The stable governed merge gate itself also emits on every pull request and re-runs the deterministic institutional, security, runtime, repository, dependency and conflict controls. Provider-managed CodeQL findings remain independent provider evidence and must never be fabricated by a local compatibility job.

## Security self-healing

Security self-healing is permitted only when the repaired state passes the original failed control and the full institutional/security suite. An agent may not disable or weaken the governing check, conceal the finding, expose/reconstruct credentials, widen privileges, erase evidence or self-approve the originating material change.

## GitHub role

GitHub remains important for repository history, PR review, CI, CodeQL, dependency review, secret-scanning evidence where available, merge blocking and post-merge validation. Its settings are not CrownThrive's institutional sovereign authority.

**GitHub main protection is a required defense-in-depth merge perimeter, but it is not the authority root.** A provider PASS cannot substitute for CT-ADR-GOV-011 quorum, specialist, risk, rollback, documentation, downstream or D3 authority requirements.

Where GitHub already operates a provider-managed security capability such as CodeQL default setup, CrownThrive consumes that provider evidence rather than introducing a conflicting duplicate advanced configuration solely to make a local workflow appear more complete.

## Roadmap rule

Phase 3 — Execute is current. This amendment does not blanket-certify any subsystem: repository enforcement, provider behavior, CI evidence and post-promotion readback remain independently gated. The current GitHub ruleset perimeter is behaviorally verified at the repository level; exact-head CI and any provider-side change still require their own evidence, and D3 remains human-reserved.
