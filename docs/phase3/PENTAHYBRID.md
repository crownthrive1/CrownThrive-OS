# PentaHybrid — Human + AI Integration & Accountability Layer

**Machine key:** `penta.hybrid`

PentaHybrid is the CrownThrive layer that makes autonomous systems and accountable humans operate as one institution without confusing machine capability with human authority.

Its purpose is not to slow automation. Its purpose is to make broad automation safe enough to scale by defining exactly when software may proceed, when a human must review, when explicit approval/quorum is required, how an override is recorded, and when the institution must fail closed.

## Canonical decision states

Every consequential PentaHybrid transaction resolves to one of five states:

1. **machine_allowed** — the action is inside certified bounded authority and may proceed automatically;
2. **human_review_required** — an accountable human must inspect the evidence before the workflow may continue;
3. **human_approval_required** — an explicit approval, quorum, or sign-off is required;
4. **human_override_recorded** — an authorized human changes a machine recommendation and the rationale/evidence is preserved;
5. **hold_fail_closed** — identity, authority, evidence, confidence, separation of duties, conflict, quorum or policy requirements are unresolved.

## What PentaHybrid resolves

A decision package should make the following machine-readable:

```yaml
decision_id: penta.hybrid.<domain>.<id>
workflow_ref: "..."
risk_class: D0 | D1 | D2 | D3
requested_action: "..."
machine_recommendation: "..."
confidence: "..."
evidence_refs: []
required_human_role: "..."
charter_or_authority_ref: "..."
separation_of_duties: "..."
conflict_check: pending | pass | fail
quorum_rule: none | "..."
deadline: "..."
disposition: pending | approved | rejected | modified | recused | hold
override_reason: null
signatures_or_receipts: []
preserve_to:
  - DAIL
  - PentaDocs
```

## Human-gate triggers

PentaHybrid should be invoked whenever an applicable policy requires it, especially for:

- D2/D3 governance actions;
- legal, licensing, exclusivity or material rights changes;
- pricing/economic rules or material payment/settlement changes;
- secrets/security posture or high-impact credential changes;
- privacy-sensitive data use;
- destructive or difficult-to-reverse operations;
- public claims with material reputational/legal consequence;
- canon/cultural decisions reserved to CIE/human stewardship;
- source-history reconstruction or irreversible archive mutation;
- release promotion when the executor cannot independently certify itself;
- unresolved model confidence or contradictory evidence;
- explicit founder/board/council approval requirements.

## Human role resolution

PentaHybrid does not maintain a separate people database. It resolves people and authority through CrownThrive ID, CHLOM role/capability records, PentaAlumni charters where applicable, and PentaGeneration continuity/succession records where applicable.

The system must verify that the person is not merely known, but currently eligible for the exact decision: correct role, active term, adequate risk ceiling, no disqualifying conflict, required separation of duties, and valid quorum context.

## Agent-to-human handoff

A good handoff minimizes cognitive burden without hiding uncertainty. The package should contain:

- what the system wants to do;
- why now;
- exact target and blast radius;
- what authority is claimed and where it comes from;
- what evidence supports the action;
- what remains uncertain;
- reversible/irreversible consequences;
- proposed verification and rollback/compensation;
- machine recommendation and confidence;
- the exact decision requested from the human.

The human should not have to reconstruct the workflow from logs scattered across systems.

## Human-to-agent handoff

When a human approves, rejects, modifies, or overrides, PentaHybrid returns a structured disposition rather than an ambiguous chat/message:

```text
APPROVED_EXACT
APPROVED_WITH_CONDITIONS
REJECTED
MODIFIED_SCOPE
RECUSED
HOLD_MORE_EVIDENCE
EXPIRED_NO_DECISION
```

PentaMation then uses that exact state to resume, modify, or terminate the workflow.

## Independence and separation of duties

For consequential operations, the same autonomous component should not be the sole proposer, executor, verifier and certifier. PentaHybrid works with PentaAssure to enforce independent review or human quorum where CHLOM policy requires it.

Human override is permitted only when the human has authority to override the specific control. An override never deletes the original machine recommendation or evidence.

## PENTA five-stage mapping

- **Discover:** resolve the decision context, evidence, machine confidence, applicable policy, eligible humans, conflicts and prior state.
- **Govern:** determine whether machine execution, review, approval, quorum, recusal, separation of duties or fail-closed hold applies.
- **Execute:** route and record the exact human decision transaction.
- **Verify:** verify identity, role, term, quorum, signature/receipt, conditions and decision integrity.
- **Preserve:** retain the package, recommendation, human disposition, rationale, dissent/override, timestamps and handoff lineage.

## Success criterion

PentaHybrid succeeds when CrownThrive can automate aggressively while always being able to answer: **Which decisions were made by machines, which required a human, who had authority, what evidence they saw, what they decided, whether they overrode the machine, and what happened afterward?**
