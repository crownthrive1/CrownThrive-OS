# CHLOM C11 — DAIL Cold Checkpoint Resume & Privacy Hardening v1

## Why this hardening exists

The DAIL now contains well over one million immutable events. A cold-lineage export cannot safely depend on a single long connector invocation, and exporting full event payload bodies to a provider would exceed the minimum-data requirement for a lineage checkpoint.

This hardening keeps the same C11 owner lane and the same canonical External Evidence Relay. It changes the connector protocol, not the authority topology.

## Minimum-data export

The final chunk RPC omits `payload` bodies. It exports the immutable chain and recovery metadata plus `payload_sha256`, so the cold package can prove event order, event identity, source/causation, visibility class, payload commitment, previous hash, event hash, anchor state, and signature reference without copying protected payload contents into the provider package.

The declared scope is `ledger_lineage`; this is not a full semantic-body archive.

## Durable resume

`chlom_runtime.record_dail_cold_export_progress_v1` persists connector progress on the existing backup job using a compare-and-set cursor:

- expected previous sequence cursor;
- cumulative exported event count;
- chunk count;
- last event hash;
- last chunk SHA-256;
- rolling export-chain SHA-256;
- terminal export-complete flag.

Before progress advances, the database re-materializes the canonical bounded chunk and verifies the connector-provided chunk SHA, terminal sequence, and terminal event hash. A stale cursor fails closed with a CAS conflict rather than silently double-counting a chunk.

The job remains in a due state until terminal provider completion, allowing the existing external connector relay to resume from durable state on a later pass.

## Scheduler topology

`enqueue_dail_cold_checkpoint_v2` wraps the exact-source freezer and adds the durable progress contract. The internal due generator calls v2. It still performs no Google Drive write. No new external automation is introduced.

## Rollback

Rollback removes the resume wrapper/progress function and rebinds the internal due generator to the v1 queue function. It intentionally preserves the hardened lineage-only chunk definition because rollback must not reintroduce a larger provider-data exposure. The base C11 rollback remains the full feature removal path.

## Remaining release gates

This source hardening still requires exact-head CI/QC, PentaSecurity, CHLOM authority, applicable CIE, independent PentaCertifier, governed merge/migration apply, exact connector readback, isolated recovery drill, and fresh Phase-4 assurance before C11 can be marked production verified.
