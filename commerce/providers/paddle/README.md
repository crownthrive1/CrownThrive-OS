# Paddle catalog adapter

This directory contains additive, versioned Paddle catalog waves derived from governed CrownThrive commercial contracts.

## Wave 001 — production verified

`go-flipbooks.wave-001.v1.json` maps the PentaGreen `ct.pentagreen.go-flipbooks-standard-pro.v1` contract to two live Paddle catalog products and six live prices:

- Go Flipbooks Standard: Launch ($29 one-time), Studio ($99 one-time), Commerce ($249 one-time), Managed Standard ($49/month).
- Go Flipbooks PRO: PRO Setup ($297 one-time), PRO Monthly ($29/month).

Production apply created 2 products and 6 prices with 0 holds. Independent catalog readback returned the same 2 active products and 6 active prices. Immediate replay created 0 new objects and resolved all 8 provider objects as existing.

Go Flipbooks Managed Services ($100/$200/$300/$500 custom scopes) is deliberately deferred to Wave 002 until the Paddle account's appropriate service tax category is verified/enabled. This prevents misclassifying professional/implementation services as SaaS.

## Canonical production execution

The governed production path is the ThriveBase function:

```sql
select integration_control.paddle_go_flipbooks_wave001_v1(false); -- dry-run
select integration_control.paddle_go_flipbooks_wave001_v1(true);  -- idempotent apply
```

That function resolves the selected Paddle credential through PentaWire/Vault, routes provider calls through the CHLOM DAIL HTTP wrapper, persists a non-secret receipt, rejects duplicate/drifted provider objects, performs exact provider readback, and is executable by `service_role` only. `anon` and ordinary `authenticated` users have no execute permission and cannot read the receipt table.

## Portable adapter

`tools/paddle/sync-catalog.mjs` is retained for controlled development/portability and dry-run validation. It is **not** a second credential authority. If used in apply mode, `PADDLE_API_KEY` must be injected transiently by an approved server credential runtime and must never be committed, logged, or returned.

```bash
node tools/paddle/sync-catalog.mjs --manifest commerce/providers/paddle/go-flipbooks.wave-001.v1.json
```

The adapter pins `Paddle-Version: 1`, creates products before prices, uses CrownThrive stable IDs in Paddle `custom_data`, refuses destructive changes, fails closed on duplicate/conflicting provider objects, and reads every created or reused provider entity back before returning `PASS`.

Production provider IDs and receipt IDs are recorded in `docs/evidence/paddle-go-flipbooks-wave-001-20260904.json`; credential material is not.
