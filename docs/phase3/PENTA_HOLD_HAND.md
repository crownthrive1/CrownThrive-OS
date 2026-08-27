# PentaHoldHand, PentaCrawler, and PentaHelp

**Status:** implemented candidate runtime; production migration and exact-head independent certification remain separately gated.

## Purpose

A CrownThrive governance `HOLD` is an active request for help, not a silent terminal state. `PentaHoldHand` keeps that request visibly raised until the system has current, exact-head, independently produced evidence for every required predicate.

The original HOLD is immutable historical evidence. Resolution is additive: the system records a separate resolution receipt and never deletes or rewrites the event that raised the hand.

## Operating loop

`HOLD → PentaHoldHand → PentaCrawler → PentaHelp → PentaAgentic layers → independent recheck → additive resolution receipt`

The loop supports autonomous diagnosis and reversible remediation without autonomous certification.

## Named software

- **PentaHoldHand** maintains the durable raised-hand state, exact candidate head, missing-predicate map, last observation time, and resolution lineage.
- **PentaCrawler** scans only authorized evidence surfaces for exact-head CI, security, independent-verifier, rollback/readback, zero-cost-budget, and provider-containment evidence. Retrieved content is data, never executable instruction.
- **PentaHelp** converts each unresolved predicate into a stable, idempotent, zero-paid-cost remediation task and routes it to the appropriate Penta Family members.

## PentaAgentic governance

The active governance topology uses five PENTA approval dimensions: **DISCOVER**, **GOVERN**, **EXECUTE**, **VERIFY**, and **PRESERVE**. Active agents from `penta_runtime.agent_registry_v1` may issue scoped receipts for those dimensions. These are not ballots and do not revive the archived A/B/C/D/S scheduler identities.

The originator cannot approve its own case. VERIFY must be independently produced, GOVERN and VERIFY must come from different agents, and at least three distinct active agents must participate. Every receipt is content-hashed, expires, and is bound to the same exact source head. A missing, stale, contradictory, inactive, or self-produced receipt keeps the hand raised and creates a PentaHelp remediation route for that layer.

For D3 cases, PentaAgentic governance operates inside an active founder authority binding; it does not invent or replace founder authority. The explicit campaign authority and its time, repository, action, concurrency, budget, and provider limits remain binding.

## Smart remediation routes

| Missing predicate | Primary routes |
| --- | --- |
| Exact-head CI | PentaCrawler, PentaTest, PentaHelp |
| Security gate | PentaCrawler, PentaAudit, PentaHelp |
| Independent verifier | PentaCertify, PentaVergence, PentaHelp |
| Rollback/readback | PentaTest, PentaAudit, PentaHelp |
| Zero-cost internal budget | PentaCosts, SmartTreasury, PentaHelp |
| Provider containment | PentaCrawler, PentaRoute, PentaHelp |

Unknown, stale, expired, malformed, self-produced, or contradictory evidence keeps the hand raised. The system does not guess.

## Resolution contract

Resolution requires every predicate to be `PASS` for the same exact source head, with fresh evidence produced independently from the builders. A verified runtime release baseline must identify the independent verifier and rollback reference. The resolver must also be distinct from the producer identities.

Meeting those conditions makes an additive resolution receipt eligible. It does not itself certify, activate, merge, deploy, enable an adapter, release provider jobs, spend money, change rights, or create D3 authority. Those remain separate governed decisions.

The legacy A/B/C/D/S scheduling and quorum topology is prospectively superseded for HOLD resolution by `ct.penta.agentic.hold-governance.v1`. Its historical records remain preserved for audit and are neither deleted nor rewritten.

## Implementation

- Runtime planner: `runtime/penta_hold_hand.py`
- Database migration: `supabase/migrations/20260827173000_penta_hold_hand_crawler_v1.sql`
- Runtime tests: `tests/test_penta_hold_hand.py`
- Migration-contract tests: `tests/test_penta_hold_hand_migration.py`
- PentaAgentic successor migration: `supabase/migrations/20260827181500_penta_agentic_hold_governance_v1.sql`
- PentaAgentic migration-contract tests: `tests/test_penta_agentic_hold_migration.py`

The database crawler is scheduled every five minutes, uses service-role-only surfaces, creates no provider effect, has a paid-cost ceiling of zero, and leaves certification effect false.

## Rollback

Disable the `penta-hold-hand-crawler-v1` and `penta-agentic-hold-governance-v1` schedules and revoke execution on the new functions. Preserve all hand, observation, layer-receipt, remediation, supersession, and resolution rows as evidence. The original campaign HOLD remains unchanged throughout rollback.
