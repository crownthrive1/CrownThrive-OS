# Phase 2.99 — Founder Strategy & Audit capability reconciliation

**Date:** 2026-08-20  
**Phase:** 2 / 2.99  
**State:** prepared, stacked capability; not activated or sovereign  
**Risk:** D2 governance/agent-control proposal; D3 remains human-reserved

## Identity decision

The earlier candidate identity `ct.agent.founder-strategy-orchestrator` is preserved as predecessor history and is **not** promoted as a second master orchestrator.

The single canonical master candidate is:

`ct.agent.founder-orchestrator`

The former strategy candidate's useful scope continues as:

`ct.capability.founder-strategy-audit`

under the canonical master.

Queue, collision and convergence coordination remains the sibling capability family owned by PR #158. Strategy/audit remains the capability packet owned by PR #159.

Nothing is silently deleted or overwritten. The former agent ID, its original candidate packet, rationale, children and prior validation remain queryable as lineage.

## Capability children preserved

The Strategy & Audit capability retains:

- `ct.subagent.founder-evidence-provenance`
- `ct.subagent.founder-architecture-impact`
- `ct.subagent.founder-drift-sprawl`
- `ct.subagent.founder-security-permissions`
- `ct.subagent.founder-vote-clerk`
- `ct.subagent.founder-report-compiler`
- `ct.subagent.founder-verification-evals`

All remain non-voting.

## Authority boundary

The canonical master and both capability families remain subordinate to A/B/C/D/S governance. They do not add a vote, impersonate the founder, create signature authority, merge, write directly to `main`, move money, grant rights, broaden privileged access, convert UNKNOWN to PASS, or execute D3.

First activation still requires exact-head governance, four of five A/B/C/D/S approvals with Agent D mandatory, no deny/block, applicable specialists, founder ratification, verified live vote receipts, supervised dry runs and rollback evidence.

## Packet relationship

- PR #158 — canonical master identity plus Queue/Collision/Convergence capability family.
- PR #159 — Strategy & Audit capability family and report schema.
- PR #159 must be stacked on the exact accepted/current head of PR #158 rather than compete as a parallel master packet.

## Phase effect

None. Phase 3 remains blocked. This reconciliation removes an agent-identity collision; it does not close a Phase 2.99 hard gate by itself.
