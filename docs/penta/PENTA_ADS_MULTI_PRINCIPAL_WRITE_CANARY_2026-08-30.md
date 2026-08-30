# PentaAds Multi-Principal Write Canary — 2026-08-30

Status: **PASS**

This receipt supplements `PENTA_ADS_ADLUXE_MULTI_PRINCIPAL_V2.md`.

## Canary target

- Provider: AdLuxe Network
- Existing zone: `165354`
- Site: PentaAds (`49942`)
- Format: Banner
- Size: 468x60 Full Banner
- Operation: semantic no-op `PUT`; existing name, active state, approval state, size, revenue model, 70% publisher revenue rate, and floors preserved

## Authority chain

1. Write executed through `estate_control` using the existing full-scope PentaAds estate credential.
2. Provider returned HTTP 200.
3. Estate Control read-after-write returned HTTP 200 and matching production state.
4. Independent least-privilege Publisher readback used `/publish/zone/165354` and returned HTTP 200.
5. No raw credential was returned, logged, or copied into this artifact.

## Result

- Zone remains Approved.
- Zone remains active.
- Revenue rate remains 70%.
- Estate Control response/readback SHA-256: `d8b1a5f247aab1fdaf33856f9f2f9cc4d14cb6f05fa2349aba96dcb13e69afdf`
- Publisher independent readback SHA-256: `f57ca45c9d59e24301e3cda49f7edd94a519b33397a9026990aef5d5f9be972c`
- `secret_exported = false`

## Certification meaning

This canary proves the v2 production path for current-estate zone configuration:

`bounded D2 mutation -> Estate Control provider write -> Estate Control readback -> independent Publisher readback -> evidence`

The Manager principal was not used because provider evidence currently classifies it as `AUTHENTICATED_ISOLATED` with zero assigned current-estate objects. No silent credential escalation is permitted.
