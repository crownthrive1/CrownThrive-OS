# Phase 2.99 — specialist gate CodeQL log-minimization self-heal

Date: 2026-08-19
State: repaired pending independent exact-head security revalidation
Authority: CT-ADR-GOV-011 / ten_phase_v1
Phase: 2 / 2.99
Phase 3: blocked_pending_phase_2_99_hard_exit

## Trigger

Independent Agent S review of PR #65 head `d7b44afa6bc7d32936ce6d93a62c222899b21880` found a current unresolved HIGH GitHub Advanced Security / CodeQL finding for clear-text logging of sensitive information in the trusted Git-diff verification path.

The trusted-diff control itself was valid and remains required. The defect was evidence projection: successful provider runs emitted the complete trusted changed-file path list to workflow logs.

## Root-cause repair

The repair preserves exact Git base/head binding, changed-file count, deterministic SHA-256 digest, per-file internal classification, cumulative specialist resolution, the real `decide()` execution path, the permanent CI non-sovereign hard block, and all fail-closed omission/specialist vectors.

Provider-visible success output is minimized:

- trusted changed-file names are not emitted;
- trusted changed-file count remains available;
- trusted changed-file digest remains available for independent equality verification;
- an explicit redaction marker records that paths were intentionally withheld;
- current-PR preflight no longer emits the selected omitted/unclassified path names on successful negative-proof execution;
- semantic domains, required specialist IDs, and boolean negative-proof results remain available because they do not expose repository path data.

This is a security self-heal, not a suppression. No CodeQL rule, security validator, trusted-diff invariant, specialist requirement, quorum requirement, or D3 boundary is weakened.

## Validation required before promotion

Because this repair changes the PR head, all prior exact-head A/B/C/D/S decisions are stale. Agent A performed the repair and does not self-approve it.

Before PR #65 can promote, the unchanged repaired head must obtain:

1. Documentation Governance PASS;
2. Security Governance PASS;
3. Governed Merge Gate PASS;
4. the original trusted-diff and current-PR operational preflight vectors PASS unchanged in substance;
5. provider CodeQL revalidation showing the triggering finding is no longer current/unresolved on the repaired code;
6. fresh independent B/C/D/S exact-head review sufficient for 4/5 including D;
7. independent Security & Privacy, AI/ML/LLM TEVV, and Operations/SRE endorsements;
8. final current-main/head/collision recheck and rollback confirmation.

The prior CodeQL finding and Agent S block remain historical trigger evidence and must not be erased.

## Scope and rollback

No provider credential, database policy, payment, rights, Collab write, customer state, token/crypto capability, or production authority is changed by this repair. Rollback is reversion of the bounded PR #65 security self-heal commits.
