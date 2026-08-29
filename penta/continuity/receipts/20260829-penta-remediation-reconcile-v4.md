# Penta remediation reconciliation v4

Production migration `penta_remediation_reconcile_post_surgery_success_v4` is active.

- Canonical contract: `ct.penta.pm.assignment-execution.v4`
- Post-surgery success may be evidenced by `latest_started_at` or `last_success_at`.
- A real recurrence surgery is preserved as `no_code_delta=false`.
- PentaCertify remains the terminal reconciliation authority.
- D3 authority is unchanged.
- Production execution-ledger readback after reconciliation: 52 verified, 0 queued, 0 verification, 0 held, 0 failed.
