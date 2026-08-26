# Penta Transport & Capability Primitives Family

**Family ID:** `transport-primitives`  
**Portal:** `/io/pentas/families/transport-primitives`

## Story

Higher-level CrownThrive systems should not repeatedly reinvent low-level request, mutation, parsing, queueing, event or delivery behavior. The primitive family provides a governed vocabulary of reusable capabilities beneath PentaRoute.

The current technical census includes request primitives such as PentaFetch/PentaGet/PentaHead/PentaOptions, mutation primitives such as PentaPost/PentaPut/PentaPatch/PentaDelete, discovery/read primitives such as PentaQuery/PentaSearch/PentaRead/PentaList, transform/validation primitives, cache/sync/ingest/import/export, queue/retry/dispatch/schedule, event/stream/hook, and build/deploy/release-related capability primitives.

## Primary members

The exact primary-member list is runtime-discovered from the PentaRoute primitive census after stronger explicit family assignments are applied. Typical members include PentaTun, PentaFetch, PentaGet, PentaHead, PentaOptions, PentaPost, PentaPut, PentaPatch, PentaDelete, PentaQuery, PentaSearch, PentaRead, PentaList, PentaParse, PentaResolve, PentaTransform, PentaValidate, PentaCache, PentaSync and PentaIngest.

Cross-cutting primitives such as PentaAuth, PentaVault, PentaSign, PentaSnapshot, PentaRollback, PentaCertify, PentaAudit, PentaRelease and PentaBind may belong primarily to another family while remaining registered route primitives.

## Responsibilities

- stable primitive identity;
- typed inputs/outputs and side effects;
- transport/mutation semantics;
- idempotency/retry expectations;
- readback requirements;
- error and evidence contracts;
- reusable composition beneath higher systems.

## Operating flow

```text
higher-level child system
→ PentaRoute
→ exact primitive contract
→ exact provider/runtime binding
→ bounded effect
→ readback/evidence
→ higher-level result
```

## Authority boundary

A primitive is a verb, not a permission. PentaDelete cannot delete merely because it exists. PentaPost cannot create an object without exact provider and institutional authority. PentaDeploy cannot deploy an uncertified artifact. Higher-level child contracts supply the business/rights/security/economic authorization.

## Status and evidence

Primitive registration proves institutional identity. Independently executable primitives must also satisfy the universal Penta portal, status, audit and release standards. Technical registry presence does not automatically make a primitive machine-production eligible.

## Incidents and recovery

Primitive incidents preserve request identity, target, idempotency, retry count, previous/new state and compensation/rollback references. Retry must never upgrade a HOLD or bypass a failed authority gate.

## Releases and roadmap

The primitive census may grow as common reusable capabilities emerge. New primitive names must be added to a canonical source and will automatically fail the family verifier until classified.
