# Penta PR Admission Contract v1

Canonical contract: `ct.penta.pr-admission.v1`.

A Penta MUST NOT create a pull request merely because work exists. A pull request is admitted only when a bounded merge candidate exists and the deterministic admission controller returns `CREATE` or an explicit collision-safe `SUPERSEDE`.

## Invariants

1. **One subject -> one owner lane -> one open PR.** New work for an owned subject updates/restacks the existing branch.
2. **HOLD never creates a replacement PR.** A held candidate remains attached to its canonical owner and dependency graph until material state changes.
3. **Release generation is idempotent.** `release_candidate_key = repo + version + canonical base generation`. A matching open owner returns `REUSE/NOOP`, never another release PR.
4. **PASS is evidence-bound.** PR prose, labels, automation, and release metadata may not claim PASS unless exact-head provider evidence/receipt supports that claim. CI absence, `action_required`, skipped jobs, neutral, cancelled, stale-head success, originator readiness, and repository `SELF_CERTIFIED` artifacts are not PASS.
5. **Pre-open completeness.** Candidate must bind exact base/head, bounded changed files, authority class, tests/readiness, rollback, evidence claims, and post-open obligations.
6. **Post-open obligations are explicit.** Requirements that cannot exist before a PR number/head exists (for example exact-PR independent certification) are recorded as obligations and may block merge, but do not justify duplicate PR creation.
7. **No authority manufacture.** Admission creates no D3, provider-write, credential, money, rights, certification, vote/quorum, deployment, or release authority.
8. **Terminalization is deterministic.** MERGE only on exact-head terminal evidence; CLOSE only when merged, explicitly superseded with unique work preserved, or abandoned by authorized disposition. Never leave superseded generator PRs open indefinitely.

## Required integration points

Every PR-capable Penta/factory must call `scripts/penta_pr_admission.py` immediately before provider PR creation, including PentaRelease, PentaPR, PentaSELF remediation, PentaDocs automation, PentaPM-generated source lanes, and any future PR writer.

Provider adapters must supply the current open-PR ownership index. They must obey `REUSE` by updating the existing canonical branch/PR rather than opening a new PR.

PentaRelease additionally MUST use `release_candidate_key` and must converge release manifest, release intelligence, PentaDocs/readback, CIE/economic surfaces, and release metadata into one canonical release transaction unless an explicitly different subject has a justified independent lifecycle.

## Gate admission vs gate execution

GitHub Actions admission is distinct from validator execution. A workflow run with `action_required` and zero jobs is an upstream provider admission HOLD. It must not be rewritten as a validator failure or PASS. Repair the provider admission policy, then execute the exact-head gate and bind its immutable receipt.
