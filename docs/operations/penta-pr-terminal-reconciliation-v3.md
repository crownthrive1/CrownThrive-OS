# PentaPR Terminal Reconciliation v3

Contract: `ct.penta-pr-terminal-reconciliation.v3`

## Permanent invariants

1. Provider-current GitHub head SHA is the mutation fence.
2. Historical Vergence rows remain evidence but are non-authoritative when their SHA differs from the provider-current head.
3. `VERIFIED_ZERO_DELTA` closes without merge.
4. A verified zero-delta SHA may extend to a provider-current descendant only when the entire compare delta is the finding's generated `penta/remediations/<finding>.execution.json` file.
5. `SUPERSEDED` closes without branch deletion; history remains preserved.
6. `MERGE_READY` requires explicit `exact_head_certified=true` and GitHub still enforces repository merge protection.
7. Draft, repair-required, certification-required and D3 work remain open.
8. Every terminal write is followed by provider readback and written to the canonical PR truth ledger.
9. PentaCrons/PentaTime owns the recurring terminal sweep; PentaSELF restores it if missing or inactive.
10. No force merge, force push, secret export, D3 authority manufacture, or destructive branch cleanup is introduced by this contract.
11. Retroactive reconciliation is closure-only: historical/current provider truth is backfilled, but historical merges are never manufactured.
12. Historical PRs missing from `penta_pr.lifecycle` are reconstructed by provider-truth upsert rather than silently omitted.
13. Retroactive traversal is resumable and lease-fenced per active CrownThrive repository through `penta_pr.retroactive_backfill_v3`.

## Runtime route

`PentaPR -> PentaPM -> PentaCloser/PentaMerge -> GitHub -> provider readback -> github_pr_truth_receipts_v2 -> PentaPR events -> DAIL`

## Retroactive route

`active repository census -> leased historical page -> GitHub provider truth -> lifecycle/truth upsert -> exact-head zero-delta evaluation -> safe close only -> provider readback -> cursor advance`

The retroactive lane scans `state=all` and therefore reconstructs open, closed, and merged provider truth. It never reopens a terminal PR. An open historical PR is mutated only when the existing governed zero-delta evidence remains valid for its provider-current head under the exact-head/evidence-only-descendant rules. Retroactive merge is explicitly disabled.

## Production cadence

`penta-pr-terminal-reconcile-v3` executes every two minutes through `pentatime.execute_guarded_v3('penta_pr_terminal_reconcile')`.

Each scheduled pass protects current open PRs first, then consumes one leased historical backfill page. This keeps normal terminal reconciliation responsive while making historical convergence monotonic and resumable.
