# Governance Standard Amendment — CT-ADR-GOV-011

**Effective:** 2026-08-18  
**Applies to:** `ct.standard.docs-autonomy.v1`, repository automation, agent relay, CI/security evidence and Phase 2.99-to-3 transition.

This amendment is current policy and has precedence over earlier S106-era sentences that defined GitHub branch/ruleset required-check enforcement as CrownThrive's own sovereign fail-closed merge requirement.

## Current governance tiers

CrownThrive now distinguishes five related states:

1. **policy detection** — a validator or security scanner detects a violation;
2. **provider enforcement** — GitHub or another provider may technically block an action;
3. **agent-sovereign enforcement** — CrownThrive's registered agents refuse promotion unless the coded institutional policy passes;
4. **reserved human authority** — D3 actions require an authorized human/professional even when agent quorum passes;
5. **post-promotion revalidation** — canonical state is independently rechecked for drift/bypass/regression.

For `crownthrive1/CrownThrive-Support`, state 3 is the sovereign control. GitHub state 2 is optional defense-in-depth and is currently not established on `main`; state 5 remains required.

## Automatic merge contract

An automatic D0–D2-eligible merge requires:

- current-state/collision reconciliation;
- documentation validation;
- security validation and applicable provider scan evidence;
- no secret/restricted-data exposure;
- risk score at least `85/100`;
- required specialist endorsements;
- `4/5` affirmative votes (`75%`, rounded up);
- independent Agent D approval;
- no deny/block vote;
- rollback/recovery;
- documentation impact;
- downstream Phase 3–10 reconciliation.

D3 is never auto-authorized by quorum.

## Security self-healing

Security self-healing is permitted only when the repaired state passes the original failed control and the full institutional/security suite. An agent may not disable or weaken the governing check, conceal the finding, expose/reconstruct credentials, widen privileges, erase evidence or self-approve the originating material change.

## GitHub role

GitHub remains important for repository history, PR review, CI, CodeQL, dependency review, secret-scanning evidence where available and post-merge validation. Its settings are not CrownThrive's institutional sovereign authority.

**GitHub branch protection may supplement the model but is not the authority root.**

Where GitHub already operates a provider-managed security capability such as CodeQL default setup, CrownThrive should consume that provider evidence rather than introducing a conflicting duplicate advanced configuration solely to make its own workflow appear more complete.

## Roadmap rule

This amendment does not open Phase 3. It removes only GitHub branch protection as an independent hard dependency. Every other Phase 2.99 hard-exit and Phase 3 hard-entry requirement remains binding.
