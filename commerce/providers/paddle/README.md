# Paddle catalog adapter

This directory contains additive, versioned Paddle catalog waves derived from governed CrownThrive commercial contracts.

## Wave 001

`go-flipbooks.wave-001.v1.json` maps the PentaGreen `ct.pentagreen.go-flipbooks-standard-pro.v1` contract to two Paddle catalog products and six prices:

- Go Flipbooks Standard: Launch ($29 one-time), Studio ($99 one-time), Commerce ($249 one-time), Managed Standard ($49/month).
- Go Flipbooks PRO: PRO Setup ($297 one-time), PRO Monthly ($29/month).

Go Flipbooks Managed Services ($100/$200/$300/$500 custom scopes) is deliberately deferred to Wave 002 until the Paddle account's appropriate service tax category is verified/enabled. This prevents misclassifying professional/implementation services as SaaS.

## Execution

Dry-run (no credential):

```bash
node tools/paddle/sync-catalog.mjs --manifest commerce/providers/paddle/go-flipbooks.wave-001.v1.json
```

Provider apply (server runtime only):

```bash
PADDLE_API_KEY='(injected by the credential runtime)' \
node tools/paddle/sync-catalog.mjs \
  --manifest commerce/providers/paddle/go-flipbooks.wave-001.v1.json \
  --apply \
  --receipt paddle-wave-001-receipt.json
```

The API key must be injected at runtime from approved credential custody. Never commit it. The adapter pins `Paddle-Version: 1`, creates products before prices, uses CrownThrive stable IDs in Paddle `custom_data`, refuses destructive changes, fails closed on duplicate/conflicting provider objects, and reads every created or reused provider entity back before returning `PASS`.
