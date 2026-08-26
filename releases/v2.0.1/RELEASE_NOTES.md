# CrownThrive OS V2.0.1 — Founder Visibility & Autonomous Briefing

Release date: 2026-08-25 / 2026-08-26 UTC

## Release summary

CrownThrive OS V2.0.1 extends the autonomous ThriveBase runtime with founder-facing visibility that does not require the founder or ChatGPT to remain present. The execution plane remains fail-closed and continues to preserve CHLOM governance boundaries.

## Added in V2.0.1

- Immediate exception email for material runtime failures, critical scheduler faults, exhausted retries, security/governance exceptions, and genuine D3/founder decisions.
- Daily Operations Brief generated at approximately 08:05 America/New_York.
- Weekly Founder Executive Brief generated Mondays at approximately 10:05 America/New_York.
- Routine successful background jobs remain in ThriveBase/DAIL receipts instead of producing notification noise.
- Material production, commerce, release, revenue, risk, infrastructure, and ecosystem changes may be surfaced even when no founder action is required.
- Founder subject semantics preserve the distinction between STATUS/WATCH and ACTION NEEDED.
- Email content excludes raw credentials and secrets.
- Brief generation is idempotent so the same reporting period is not intentionally mailed twice.

## Runtime architecture

ThriveBase pg_cron → OS V2 dispatcher → governed task queue → Edge runtime → provider adapters → persistent receipts → CHLOM DAIL → Mailgun founder communications.

Critical boundaries remain unchanged: D3/new-authority work is human-reserved; self-approval is disabled; uncontrolled recursive spawning is disabled; HOLD is never silently converted to PASS.

## Proven production evidence

- OS V2 minute dispatcher independently executes from ThriveBase.
- Mailgun path has returned provider HTTP 200 and persisted provider receipts.
- Founder expectations email was accepted by Mailgun at 2026-08-26 00:41:37 UTC.
- V2.0.1 runtime state is `hot` / `released` in ThriveBase.

## Operator expectation

The founder should not have to inspect database jobs to know what matters. Immediate critical exceptions are pushed, a concise daily brief reports operating state, and a weekly brief provides executive-level movement. Full machine evidence remains auditable in ThriveBase, CHLOM DAIL, GitHub, and provider receipts.
