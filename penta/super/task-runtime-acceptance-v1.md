# Task Runtime Penta Family — Production Acceptance v1

This is the acceptance contract for PentaDND, PentaSnapshot, PentaTranslate, PentaLease and PentaCollision. No component may be represented as production-ready until its exact implementation passes every applicable gate and independent readback.

## Required test matrix

### PentaDND
- Acquire an exact-resource lease while unrelated resources remain runnable.
- Reject conflicting equal/lower-priority mutation claims according to policy.
- Permit higher-priority emergency/safety route where policy requires.
- Expire abandoned lease at TTL without manual cleanup.
- Renew only with valid owner/heartbeat and bounded maximum TTL policy.
- Release on success, rollback, HOLD handoff and timeout.
- Prove paused routes resume after release.
- Prove DND cannot become global maintenance/shutdown by wildcard accident.

### PentaSnapshot
- Capture exact pre-state fingerprints before mutation.
- Detect state drift between snapshot and mutation attempt.
- Restore a bounded canary to the captured state.
- Preserve append-only DAIL/history through rollback.
- Reject incomplete/unreadable snapshot as mutation authority.

### PentaLease / PentaCollision
- Two workers race for the same scope: exactly one mutation owner.
- Duplicate dispatch with same idempotency key causes no duplicate side effect.
- Stale owner recovery occurs only after lease/TTL rules permit it.
- Rogue/unleased writer produces incident/HOLD, not a competing counter-write.
- Exact-head/CAS drift aborts mutation.
- Independent verifier work cannot be suppressed by originator lease.

### PentaTranslate family
- Immutable source evidence remains byte-identical.
- Machine projection has stable identity/digest and provenance.
- English projection round-trips through the governed representation without semantic identity loss for the certified corpus.
- Additional human-language projections preserve source linkage and confidence.
- No protected mapping, key material, cipher rule, private vocabulary implementation or private identity mapping leaks to public GitHub, public Drive views, logs or DAIL.
- Translation verification is performed by a non-originating verifier.

## Institutional gates

Every material test/mutation must bind DAIL-EVIDENCE -> DAIL-DECISION -> DAIL-EXECUTION as applicable, with stable causation and supersession. PentaCensus must read back the canonical identity/family/runtime/maturity state. Drive receives governed human/hybrid evidence; protected implementation remains in restricted custody. PentaContext receives sanitized state->decision->outcome continuity evidence only.

## Production definition

`PRODUCTION_READY` requires exact implementation + passing runtime tests + rollback/restore + security + collision/concurrency + three-DAIL chain/readback + PentaCensus registration/readback + independent PentaCertifier disposition + actual production runtime readback. Documentation, a PR, CI alone, preview deployment, provider acceptance, or founder intent alone are not sufficient.
