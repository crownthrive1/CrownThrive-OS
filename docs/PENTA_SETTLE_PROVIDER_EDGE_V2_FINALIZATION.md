# PentaSettle Provider Edge v2 — Production Finalization

## Development linkage

Refs #98.

## Production convergence

This receipt closes the repository-state gap for the already deployed and certified `ct.penta.settle.provider-edge.v2` runtime.

- Pull request: #619
- Provider edge: `penta-settle-provider-edge`
- Production Supabase function ID: `affebe57-dcae-4e4e-aa1b-8bfda994be2c`
- Certified bundle SHA-256: `e833c9c5d4eb31ed7b785d4e10e69090d8c6a11c008bdeeb7126efb6d26b5ed0`
- Runtime posture: production-live, exact-authority-only
- Enabled live adapters: Stripe Connect transfer, PayPal Penta payouts, PayPal Ambassador payouts
- Unattended monetary authority: zero
- Exact ECAC: required
- Independent approval: required
- Provider readback: required
- Certification canaries: zero-value and no provider write

Final merge must synthesize and validate this branch against the then-current `main`; no stale base SHA is treated as release authority. Provider writes remain bounded by single-use exact settlement authority rather than any global enable flag.
