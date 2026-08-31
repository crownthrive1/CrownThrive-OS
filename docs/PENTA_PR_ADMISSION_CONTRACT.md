# Penta PR Admission Contract v1

Canonical contract: `ct.penta.pr-admission.v1`.

A Penta MUST NOT create a pull request merely because work exists or because observed behavior looks anomalous. A pull request is admitted only when a bounded merge candidate exists, current production/topology truth has been reconciled, current ownership and founder intent have been checked, and the deterministic admission controller returns `CREATE` or an explicit collision-safe `SUPERSEDE`.

## Invariants

1. **One subject -> one owner lane -> one open PR.** New work for an owned subject updates/restacks the existing branch.
2. **HOLD never creates a replacement PR.** A held candidate remains attached to its canonical owner and dependency graph until material state changes.
3. **Release generation is idempotent.** `release_candidate_key = repo + version + canonical base generation`. A matching open owner returns `REUSE/NOOP`, never another release PR.
4. **PASS is evidence-bound.** PR prose, labels, automation, and release metadata may not claim PASS unless exact-head provider evidence/receipt supports that claim. CI absence, `action_required`, skipped jobs, neutral, cancelled, stale-head success, originator readiness, and repository `SELF_CERTIFIED` artifacts are not PASS.
5. **Current truth precedes candidate creation.** Before a new PR can be admitted, the caller must read current `main`, current open PR ownership, active Penta/work ownership, affected production runtime/provider truth, current changes already deployed or staged, and the current topology snapshot.
6. **Founder intent is not inferred away.** Unusual or noisy production behavior is not automatically a defect. The caller must explicitly review founder/current-authority intent before proposing a behavior change.
7. **Behavior changes are enumerated.** Every observed-state -> desired-state change must be listed. If the desired state differs from the observed state, an explicit authority reference is required. Missing authority returns `HOLD`, not a repair PR.
8. **Current-main or explicit stack only.** A normal candidate must be based on the reconciled current-main SHA. A stacked candidate must name the open owner PR and bind its exact head; stale or floating bases are held.
9. **Pre-open completeness.** Candidate must bind exact base/head, bounded changed files, authority class, tests/readiness, rollback, evidence claims, current reconciliation, and post-open obligations.
10. **Post-open obligations are explicit.** Requirements that cannot exist before a PR number/head exists (for example exact-PR independent certification) are recorded as obligations and may block merge, but do not justify duplicate PR creation.
11. **No authority manufacture.** Admission creates no D3, provider-write, credential, money, rights, certification, vote/quorum, deployment, or release authority.
12. **Terminalization is deterministic.** MERGE only on exact-head terminal evidence; CLOSE only when merged, explicitly superseded with unique work preserved, or abandoned by authorized disposition. Never leave superseded generator PRs open indefinitely.

## Required reconciliation payload

Every candidate must include `reconciliation` with:

- `current_main_sha` and reconciliation timestamp;
- a current topology/census snapshot reference;
- proof that current changes, open PRs, active owners, production truth, and founder intent were checked;
- affected surfaces;
- current-change and production-truth references;
- active-owner references;
- a completed behavior-change review.

The behavior review may legitimately be empty when the candidate preserves current behavior. It must not omit a behavior simply because the caller assumes it is accidental. Intentional tracking, evidence mirroring, routing, CC/BCC behavior, support projection, notification fan-out, scheduler ownership, and similar topology are preserved unless current authority explicitly changes them.

### Example safety rule

If production currently routes a communication to a tracking surface and a candidate proposes removing that route, the candidate must record the observed state, desired state, and the current authority directing that change. Without that authority, admission returns `HOLD_BEHAVIOR_CHANGE_WITHOUT_AUTHORITY`/`behavior_change_without_authority`; the system must not open a PR based on inference.

## Required integration points

Every PR-capable Penta/factory must call `scripts/penta_pr_admission.py` immediately before provider PR creation, including PentaRelease, PentaPR, PentaSELF remediation, PentaDocs automation, PentaPM-generated source lanes, and any future PR writer.

Provider adapters must supply the current open-PR ownership index. They must obey `REUSE` by updating the existing canonical branch/PR rather than opening a new PR.

PentaRelease additionally MUST use `release_candidate_key` and must converge release manifest, release intelligence, PentaDocs/readback, CIE/economic surfaces, and release metadata into one canonical release transaction unless an explicitly different subject has a justified independent lifecycle.

## Gate admission vs gate execution

GitHub Actions admission is distinct from validator execution. A workflow run with `action_required` and zero jobs is an upstream provider admission HOLD. It must not be rewritten as a validator failure or PASS. Repair the provider admission policy, then execute the exact-head gate and bind its immutable receipt.

## Operational correction doctrine

When later current truth or founder intent proves an earlier interpretation wrong, the newest authoritative interpretation must supersede the earlier finding before any further PR generation. Existing valid work is preserved; only the incorrect proposed behavior change is abandoned. Do not delete history and do not let stale comments, stale evidence, or a prior assistant interpretation outrank current topology or explicit founder intent.
