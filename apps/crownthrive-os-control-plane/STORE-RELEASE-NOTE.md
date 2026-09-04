# CrownThrive OS Marketplace — Production Release Note

Release date: 2026-09-04  
Surface: `/store`  
Catalog: `/store-catalog.v1.json`

## Release scope

This release adds an independent commercial marketplace surface to the existing CrownThrive OS control-plane application. It does not replace the Command Center or change its runtime APIs.

The marketplace publishes:

- 10 Stripe-live digital product offers with exact SKU, price, checkout URL, Go Flipbooks product URL, asset SHA-256, PentaGreen economic ownership, secure-delivery mode, and CHLOM exact-scope labeling.
- Search and category filters for merchandise systems, event-production systems, and rights-administration kits.
- A 12-family CrownThrive OS commercial catalog for MCP, CHLOM, PentaFabric, PentaGreen, Go Flipbooks, PentaAds, ThriveEvergreen, PentaPersonas, PentaCredits, DAIL, reseller operations, and production factories.
- A public-safe developer sandbox for `/api/health`, `/api/mcp`, `/api/chlom`, and `/api/penta`.
- Separate purchaser-use, enterprise/institutional, and reseller/partner licensing pathways.

## Truth boundary

A listed Stripe checkout is represented as active only where current provider readback returned an active Payment Link. Product purchase does not silently grant manufacturing, resale, broadcast, derivative, trademark, AI/model-ingestion, exclusivity, or other rights outside the exact product terms or an executed commercial agreement.

No provider-write, credential, deployment, money-movement, certification, D3, vote, or quorum authority is exposed by the public developer sandbox.
