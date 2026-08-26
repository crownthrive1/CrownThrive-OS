# CHLOM Mesh Control Plane — Production Receipt v1

**Control plane:** `ct.control.chlom-mesh.v1`  
**Contract:** `ct.contract.chlom-mcp-operating.v1` v1.0.0  
**Date:** 2026-08-26 UTC  
**Phase namespace:** `phase-2-to-3-bounded-substrate`  
**State:** `production_hot`  

## Deployed runtime

- Supabase/ThriveBase project: `tzajnzshmtzjenqulehq`
- Public read-only status Edge Function: `chlom-mesh-status` v2
- Authenticated governed request Edge Function: `chlom-mesh-control` v1
- Heartbeat scheduler: pg_cron job `153`, `*/5 * * * *`
- Control-plane bindings: 8 bound / 0 hold / 0 degraded at certification readback
- DAIL verification: PASS, 2,063 events checked, zero current failures, one documented legacy correction preserved

## Bound control objects

1. CHLOM MCP Operating Contract
2. DAIL audit chain
3. runtime-variable registry
4. CrownThrive Sites Mesh
5. ThriveEvergreen autonomous publisher v2
6. ThriveEvergreen production storefront
7. vaulted capability registry
8. CHLOM Mesh authenticated control endpoint

## Public verification

`https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/chlom-mesh-status`

The public surface exposes sanitized status only. It does not expose secret values, raw database access, administrative credentials, or mutation capability.

## Mutation boundary

`chlom-mesh-control` is JWT-protected and request-only. It records governed action requests with idempotency and a DAIL event. It does not directly execute delete operations, money movement, secret export, or D3 human-reserved decisions.

Supported request classes are bounded to: `inspect`, `reconcile`, `bind`, `repair`, `heartbeat`, and `publication_request`.

D3 requests are recorded as `HOLD`; the endpoint does not manufacture authority.

## Self-test evidence

- Idempotency key: `ct-test-20260826-001`
- Request ID: `34fb7f69-22d9-4289-86b4-41af1b94a81d`
- Decision: `ALLOW`
- Execution effect: `REQUEST_ONLY`
- DAIL event ID: `dd280fe1-0885-43c1-83b9-1cfacfc726a0`
- DAIL event hash: `81a1e1998ce0589baa87943867abe5cffa53a065347e84a543fb0c8687cf200b`

## Source authority

Implementation was derived from the uploaded CHLOM MCP Operating Contract v1.0, Phase 2.7 institutional exhaustiveness requirements, and the CrownThrive Holdings shared-operating-spine architecture. Source presence does not itself advance the five-phase institutional program; this deployment is a bounded executable substrate and preserves fail-closed Phase 2/3 gates.

## Non-regression controls

- fail closed: true
- D3 human reserved: true
- no secret exposure: true
- no delete default: true
- no money movement default: true
- DAIL required on governed mutation requests: true
- independent verifier required for protected runtime bindings: true
