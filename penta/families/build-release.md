# Penta Build, Certification & Release Family

**Family ID:** `build-release`  
**Portal:** `/io/pentas/families/build-release`

## Story

This family is CrownThrive's governed software delivery and source-convergence production line. It turns requirements into candidates, artifacts, test evidence, certification decisions, pull requests, merges and releases while keeping builder, verifier and terminal authorities separated.

## Primary members

PentaFactory · PentaBuild · PentaCertify · PentaAssure · PentaQuality · PentaPR · PentaMerge · PentaCloser · PentaRelease · PentaRunners · PentaPunters · PentaActions · PentaResults

## Responsibilities

- candidate/software generation;
- build/package/version evidence;
- exact adapter/capability certification;
- independent assurance and quality contracts;
- PR lifecycle, stacking and collision handling;
- governed merge/closure;
- release packaging, publication and readback;
- execution runners, dispatch and result receipts.

## Operating flow

```text
gap/specification
→ PentaRFA/PentaFactory
→ PentaBuild
→ tests + negative/stress cases
→ PentaCertify + PentaAssure/PentaQuality
→ PentaPR
→ PentaMerge/PentaCloser
→ PentaRelease
→ provider/readback evidence
→ PentaResults + preservation
```

## Cross-family handoffs

Security/Trust supplies credential/security/compliance gates. Resilience/Continuity supplies snapshots, rollback, version and readiness controls. Knowledge/Data preserves source truth. Routing/Interoperability handles provider and repository transport.

## Authority boundary

Build success is not certification. Certification does not create business/legal/economic authority. Merge is not deployment. Release is not payment, entitlement, rights clearance or provider-wide write permission. Originators do not self-certify where independence is required.

## Status, incidents and recovery

PentaStatus reports queue, build, certification and release state. PentaCloser handles stale/terminal work. Failed releases preserve exact head/artifact hashes, failure evidence and rollback target.

## Releases and roadmap

This family is intentionally composable. New build/release machinery must preserve exact-head evidence, PentaSerialized continuity, Node/supply-chain rules, rollback, provider readback and the stable required governance contexts.
