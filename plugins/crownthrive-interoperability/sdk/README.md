# CrownThrive Interoperability Adapter SDK Scaffold

**State:** controlled test / public-safe scaffold  
**Execution authority:** none  
**Provider writes:** disabled by default  
**D3 automation:** prohibited

This scaffold standardizes how CrownThrive adapter and route packages are proposed before any provider operation is activated.

## Files

- `adapter-package.template.json` — package identity, focused capabilities, exact contract bindings, canaries, provider limits, testing, and governance.
- `route.template.json` — source/destination bindings, exact contract, minimization, idempotency, retry, rollback/readback, observability, and activation gates.

## Required build sequence

1. Assign stable adapter, plugin, capability, binding, route, transformation, and contract IDs.
2. Resolve the exact provider/service identity and current documentation.
3. Bind credentials only through Vault or provider-managed authorization; never put raw credentials in package files.
4. Select exact canonical contract versions.
5. Define focused read capabilities before writes.
6. Run a least-data read canary.
7. Add exact-operation write canaries only where necessary.
8. Require rollback and read-after-write for every mutation.
9. Run schema, compatibility, negative, security, privacy, and idempotency tests.
10. Bind a different independent verifier.
11. Record immutable package and public-contract digests.
12. Keep public submission, commerce, licensing, and production activation separately gated.

## Request-budget semantics

- `-1` — no CrownThrive local monthly ceiling;
- `0` — disabled;
- positive integer — CrownThrive local monthly ceiling;
- `NULL` — unresolved/fail closed.

Provider throttles, included capacity, billing, quotas, abuse controls, and terms remain authoritative. A local `-1` never means that a provider is free, unmetered, or unable to throttle.

## Public/private boundary

Public-safe adapter materials may expose stable IDs, versions, purposes, schemas, invariants, lifecycle states, reason classes, and digests.

Restricted materials include credentials, private keys, private identity mappings, exact private field maps, protected transformations, proprietary scoring weights, account topology, private evidence bodies, and protected implementation.

## Validation

The repository validator must reject:

- owner/verifier equality;
- D3-capable adapter packages;
- active provider writes without exact write/rollback/readback canaries;
- missing required test classes;
- missing exact-version contract bindings;
- inconsistent request-budget semantics;
- secret-shaped package content;
- destructive or open-ended root operations;
- live commerce or public submission claims without evidence.

The scaffold does not install or execute an adapter. It produces a governed candidate for the Adapter Foundry and Compatibility Verifier.