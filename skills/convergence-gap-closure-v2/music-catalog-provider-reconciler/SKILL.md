# Music Catalog Provider Reconciler

## Identity

- Skill: `ct.skill.convergence.music-catalog-provider-reconciler.v1`
- Suite: `ct.skill-suite.convergence-gap-closure.v2`
- Version: `1.0.0`
- Family / framework: Virality Music / PentaMedia
- Institutional generation: Phase 3 — Execute
- Lifecycle: `CANDIDATE`
- Default execution: D0/D1
- Authority ceiling: D2 only under a separately adopted operation contract
- Live side effects: disabled by this skill package
- Provider effect claims: require exact readback
- Owner: CrownThrive, LLC

## Purpose

Reconcile Virality Music works, masters, albums, playlists, editions, ISRC/UPC/PRO metadata, rights states, SoundCloud and distributor observations, and public Atlas routes without collapsing provider snapshots into canonical truth.

## Strategic lanes

- Virality Music
- SoundCloud
- DistroKid/distributors
- Backroad FM
- Melanated TV
- CrownThrive Studios

## Deterministic sequence

1. Resolve exact work/master/edition identity, title/artist aliases, source master, duration, release, identifiers, artwork, contributors, AI provenance, and rights state.
2. Collect current provider observations and distinguish public profile counts, track records, releases, and distributor evidence.
3. Match records deterministically using stable IDs first and normalized metadata/fingerprints second.
4. Classify matched, duplicate, provider_only, canon_only, metadata_conflict, rights_hold, distribution_candidate, distributed, or licensing_candidate.
5. Generate catalog and public-route deltas without publishing or distributing.
6. Bind provider readback and work-level exceptions to the canonical music ledger.

## Required inputs

- exact canonical subject and stable ID;
- exact source/version/effective-state references;
- directive or task identity;
- requested authority and environment;
- evidence/custody references already authorized for the skill;
- desired outputs and destination surfaces.

## Hard boundaries

- No upload, distribution, takedown, release, royalty claim, or license grant.
- No fabricated plays, likes, releases, identifiers, or rights.
- No replacement of accepted masters.
- No use of aggregate provider counts as work-level proof.
- No plaintext credentials, private keys, tokens, or secret values.
- No self-certification or self-approval.
- No `PASS`, `ACTIVE`, `WRITE_VERIFIED`, or `PRODUCTION` claim without the evidence required for that exact state.
- No silent deletion, historical rewrite, or unrelated ledger mutation.

## Output contract

Return:

- catalog reconciliation;
- provider match map;
- metadata conflict register;
- rights/distribution status candidates;
- ledger deltas;
- exact source and subject identity;
- authority used and side-effect flag;
- evidence references and unresolved gates;
- rollback, correction, or next-state handoff where applicable.

## Failure behavior

Fail closed with a typed reason code when identity, source, authority, rights, privacy, security, economic basis, provider capability, readback, custody, or required evidence is missing. A hold is a routed condition for repair; it is not permission to weaken the gate.
