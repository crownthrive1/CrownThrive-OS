# Framework production promotion and rollback standard

## Purpose

This standard governs promotion of Framework Factory packages from tested/candidate runtime into bounded production operation. Production is an operational lifecycle state, not a grant of sovereign authority, public activation, commerce, D3, provider-write authority, rights, or money movement.

## Production state

A production Framework Factory package uses the existing registry vocabulary:

- `package_state=maintained`;
- `operationally_enabled=true`;
- an append-only `framework_production_receipts_v1` activation receipt;
- exact source/version/content hashes;
- tested rollback;
- unchanged D0-D2 authority ceiling and non-voting state unless separately governed.

Do not invent a new package-state enum merely to label production.

## Authority

Normal production promotion requires the package's real independent parent certifier, currently Agent D where specified. A Founder Override is an exception path only after all of the following are true:

1. the exact packet technically passes;
2. a real governance deadlock is evidenced;
3. `ct.control.founder-override-ask-first-deadlock.v1` produces `AWAITING_FOUNDER_CONFIRMATION` with `override_executable=false`;
4. the Founder is explicitly asked;
5. the Founder explicitly confirms that exact preflight;
6. an exact Founder Continuity request binds the same subject/version/content hash; and
7. the human override verifier returns valid.

Silence is never authority. Surrogate continuity may not production-activate a framework through this exception path.

## Guardian production boundary

Repository Child Guardian production keeps:

- A2/D2 bounded authority;
- no voting/quorum;
- no merge/delete/archive/transfer/visibility authority;
- no child self-activation;
- family titles as presentation only;
- its existing 30-minute runtime;
- current Guardian/family/interoperability canary PASS.

Public activation remains false.

## CIE production boundary

Cultural Imprint Engine production is a governed internal runtime:

- exact current Support↔CIE technical link;
- stable identity `ct.platform.cie` resolved;
- accepted public contract digest parity;
- certification dimensions PASS or explicitly NOT_APPLICABLE to the headless internal runtime;
- repository `linked_governed` after production authority;
- package `maintained` and operational;
- `ct.algorithm.cie.v1` invocation state `production_limited`;
- only `ct.framework-agent.cie` gains bounded algorithm invocation, D2/non-voting;
- protected production canary must PASS without returning the private policy body;
- API/MCP exposure is governed-internal only;
- public activation and commerce remain false.

ThriveEvergreen remains the separate authority for pricing, checkout, Crown Credits/economic activation and entitlement.

## Receipts and rollback

Every activation writes an immutable production receipt and DAIL event. Rollback is authority-reducing: it restores the recorded pre-production state, disables production invocation where applicable, preserves all historical receipts, and never deletes evidence.

Rollback may execute without a fresh escalation because it only removes production authority.

## Security

Production entrypoints are service-only, use fixed search paths, and reject anonymous/authenticated execution. Production receipt tables use forced RLS and are not public Data API surfaces.
