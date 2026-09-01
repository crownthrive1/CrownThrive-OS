# OPERATIONClean Audio Protection

Status: **ACTIVE BOUNDED RUNBOOK**  
Version: **1.0.0**  
Stable skill ID: `ct.skill.operation-clean.audio-protection.v1`  
Execution authority: **D1 bounded reversible protection operations only**

## Purpose

Protect founder-deposited Virality Music / Backroad FM phone-drop audio before downstream normalization, Radio.co readiness, publishing, licensing, deletion, or other irreversible disposition.

This skill is an asset-protection and custody workflow. It does not manufacture music ownership, rights clearance, licensing authority, provider upload authority, or purge authority.

## Required invariants

1. Discover and resolve the actual active source folder/object set before processing. A same-named empty or stale folder MUST NOT be treated as proof that the source population is empty.
2. Preserve the original object and original provider/Drive identity until the protection predicate has passed and read back.
3. Reuse existing immutable asset identity where already bound. Never reprocess an object already represented by the canonical protection ledger or an exact fingerprint unless reconciliation explicitly requires it.
4. Compute a binary SHA-256 for the deposited file. When deterministic audio decoding is available, also compute a normalized decoded-audio SHA-256.
5. Duplicate classification is HASH-FIRST:
   - identical binary hash = exact copy;
   - different binary hash + identical decoded-audio hash = alternate encode of the same decoded audio;
   - different decoded-audio hash = distinct audio/alternate take until stronger evidence proves otherwise.
6. Filename, title similarity, size, apparent take numbering, or model judgment alone never authorizes deletion or deduplication.
7. Capture safe technical metadata such as source filename, size, duration, codec/container and normalization result.
8. Bind CHLOM/DID identity only through the current governed CHLOM path.
9. Create/read back the protected Vault manifest and PentaVault binding while raw audio remains in private custody.
10. Append/read back DAIL protection and custody evidence. Evidence is append/supersede; never silently overwrite history.
11. Move an original into the canonical fingerprinted/protected stage only after its protection predicate passes.
12. Rights remain `UNKNOWN` / `NOT CLAIMED` unless independently supported. Deposit, Drive custody, DID, hash, fingerprint, Vault binding or DAIL do not themselves prove copyright ownership or distribution rights.
13. Deletion authority is `NONE` during protection. Purge eligibility is a later governed state requiring duplicate resolution, canonical protected custody, identity/fingerprint/Vault/DAIL readback, metadata reconciliation, restore proof and applicable retention/certification gates.

## Canonical state machine

`SOURCE_DISCOVERED -> HASHED -> IDENTITY_BOUND -> VAULT_BOUND -> DAIL_RECORDED -> PROTECTED_READBACK -> FINGERPRINTED_DID`

Downstream states such as metadata-tagged, provider-ready, uploaded, review hold or purge-eligible are separate state dimensions and MUST NOT be inferred merely because protection passed.

## Radio/provider boundary

Protection is upstream of Radio.co or any replacement distribution provider. For founder catalog ingestion, do not impose customer-submission upsell economics. For external/customer submissions, verify the applicable entitlement/payment before paid fulfillment.

Before any provider upload:

- resolve existing provider identity/uploads;
- enforce idempotency;
- perform exact provider readback;
- preserve provider evidence separately from rights evidence.

## Cursor and cohort discipline

Operate in bounded cohorts. At closeout, update/read back the canonical ledger with:

- batch/cohort ID;
- protected count;
- exact/alternate-encode/distinct duplicate classifications;
- holds;
- immutable IDs and fingerprints;
- custody/Vault/DAIL references;
- source/current location identity;
- next safe cursor;
- visible remaining population with an explicit completeness qualifier when connector listing is capped.

## Failure behavior

A transport, fingerprint, identity, Vault, DAIL, readback, provider or rights failure creates `HOLD` for the affected asset; it does not justify deleting, skipping evidence, weakening the predicate, or promoting the asset to protected/uploaded.

## Survival footprint

The deterministic footprint must survive model loss: source/object identity, canonical ledger state, hashes/fingerprints, Vault manifests, DAIL receipts, state transitions and recovery evidence. Model assistance is replaceable and must not be the sole custodian of protection state.

## Evidence boundary

Public OS source carries this safe operating contract. Raw masters, private Drive identities where restricted, credentials, unpublished rights evidence and protected Vault material remain in their governed private custody systems.
