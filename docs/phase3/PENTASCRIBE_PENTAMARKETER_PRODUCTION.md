# PentaScribe + PentaMarketer Production Runtime

Status: Production control plane
Institutional generation: Phase 3

## Operational truth

PentaScribe and PentaMarketer are production-capable as CrownThrive internal control-plane systems. Their production lane executes governed reconciliation, compilation, candidate discovery, campaign validation, queueing, bounded artifact routing, testing, receipts, and evidence preservation.

Production status does **not** mean every downstream provider is write-certified. Provider publication, email delivery, social posting, paid-media spend, commerce mutation, or other consequential external operations remain independently capability-bound and fail closed until the exact adapter, credential, authority reference, and read-after-write verification path are certified.

## PentaScribe production cycle

Each cycle:

1. validates the canonical term/trademark-use registry;
2. reconciles aliases and collision state;
3. scans governed repository surfaces for new `Penta*` terminology and mark-symbol usage;
4. compiles glossary, dictionary, index, FAQ, alias, trademark-use, and reconciliation products;
5. records new discoveries as `candidate_only` without automatic canonical or trademark promotion;
6. emits a SHA-256-bound execution receipt and latest-state pointer.

A cycle with no candidates returns `PASS`. A cycle with unresolved discoveries returns `HOLD_CANDIDATES`; the hold is an institutional review state, not a runtime failure.

## PentaMarketer production cycle

Each cycle:

1. validates campaign structure, PentaScribe terminology, claim rules, CIE imprint, and CHLOM authority reference;
2. compiles the governed campaign manifest;
3. resolves every requested channel to the adapter registry;
4. queues a deterministic campaign item;
5. creates publish-ready artifacts only for adapters in `artifact_only` controlled-test state;
6. fails closed for `hold_unbound` or non-certified provider-write routes;
7. writes per-channel dispositions plus a signed-by-hash execution receipt.

The runtime therefore produces real governed marketing work products while preserving the distinction between prepared content and provider publication.

## Current adapter posture

- `owned_web`: controlled-test, artifact-only, no provider mutation authority.
- `media`: controlled-test, artifact-only, no provider mutation authority.
- `community`: controlled-test, artifact-only, no provider mutation authority.
- `partner`: controlled-test, artifact-only, no provider mutation authority.
- `email`: `hold_unbound` pending exact provider adapter/capability certification.
- `social`: `hold_unbound` pending exact provider adapter/capability certification.
- `paid`: `hold_unbound` pending exact provider adapter, budget/spend authority, and readback certification.

## Production scheduler and evidence

`.github/workflows/penta-scribe-marketer-production.yml` is the first production execution provider. It runs hourly and on relevant `main` updates, executes runtime contract tests, runs a PentaScribe reconciliation cycle, runs a bounded PentaMarketer cycle, and preserves the resulting evidence bundle as a GitHub Actions artifact.

The GitHub Actions lane is execution/evidence infrastructure, not universal authority. CHLOM remains the authority resolver; CIE remains cultural/canon governance; PentaDocs projects current institutional truth; CrownLytics/CrownPulse receive measurement handoffs; PentaMedia/AdLuxe/ThrivePush are downstream distribution surfaces; PentaGreen owns governed economic activation.

## Promotion rule for external adapters

An outbound adapter may move from `hold_unbound` to a mutation-capable state only when all of the following are explicit and independently verifiable:

- exact provider identity and endpoint/tool contract;
- credential/vault binding without secret material in source;
- CHLOM capability and risk class;
- CIE/brand/canon requirements where content is public-facing;
- idempotency/retry/compensation behavior;
- provider-side read-after-write or equivalent receipt verification;
- rollback/remediation path;
- tests/canary evidence;
- audit/evidence retention;
- spend/commerce authority where money or entitlements are involved.

No term, workflow, adapter, or successful CI run manufactures those authorities.
