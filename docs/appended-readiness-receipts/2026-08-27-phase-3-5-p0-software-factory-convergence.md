# Phase 3.5 P0 Software-Factory Convergence Receipt

- Program: CrownThrive OS Phase 3.5 institutional convergence
- Baseline source head: `fdb6bfd243a16e34dc7956ce770c9fcaef7f7bd5`
- Scope: PentaPR/PentaTagger controlled deferral and Governance Observability provider-read degradation
- Authority: no CHLOM, D3, merge, release, payment, or money authority is created by this receipt
- Production classification: production active; convergence holds remain

## Defects closed by this change

1. The PentaPR lifecycle previously invoked a repository-wide PentaTagger verification with `--max-items 500` under a governed 180-request ceiling. A live run processed 36 pull requests, consumed 184 provider calls, correctly emitted `DEFERRED`, and then converted exit code 75 into a hard workflow failure.
2. Governance Observability raised an unhandled HTTP 403 when GitHub Actions enrichment was forbidden, preventing the telemetry plane from reporting that provider evidence was degraded.
3. Open PR #634 contained the intended 24-entity cap but also changed PentaHeal's `--gate-report` input to the not-yet-created PentaHeal output. That regression is not adopted.

## Implemented controls

- PentaTagger repository sweeps are bounded to 24 entities and 180 provider calls in the PentaPR lifecycle.
- Exit code 75 is accepted only when the generated receipt explicitly declares `DEFERRED`.
- A deferred terminal preflight blocks PentaMerge/PentaCloser while allowing the technical workflow to complete with explicit evidence.
- PentaGate remains the sole input to PentaHeal; the gate-report path is protected by contract tests.
- GitHub Actions 403/404 enrichment failures fall back to trusted `workflow_run` payload identity.
- Restricted provider reads generate `HOLD_EVIDENCE` and never manufacture governance PASS, CHLOM authority, or D3 authority.
- Governance Observability writes `github-observability.json` and `pr-governance-state.json` receipts and projects the receipt into the workflow summary.
- Contract tests cover the 403 fallback, bounded sweep, exit-75 semantics, terminal-authority block, and PentaHeal gate-report invariant.

## Exit evidence required before merge

- Governance Observability Contract passes on the exact PR head.
- Static and Python syntax checks pass.
- No workflow parser failure is present.
- PentaGate/PentaHeal remain fail-closed.
- No independent D3 or release authority is asserted.

## Post-merge verification

Run the PentaPR lifecycle against the current repository backlog and verify one of these governed outcomes:

- `PASS` within the request ceiling; or
- `DEFERRED` with an explicit receipt and no hard workflow failure.

Then trigger Governance Observability on a PR head and verify that an Actions-read restriction produces a successful technical run carrying `HOLD_EVIDENCE`, `DEGRADED_PROVIDER_ENRICHMENT`, exact head identity from the trusted event, and `authority_created: NONE`.
