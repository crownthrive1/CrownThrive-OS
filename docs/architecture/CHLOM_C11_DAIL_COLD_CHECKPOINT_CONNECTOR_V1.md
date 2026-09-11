# CHLOM C11 — DAIL Cold Checkpoint Connector Protocol v1

## Purpose

This work closes the executable gap between a healthy HOT DAIL chain and a stale COLD checkpoint without creating a second external connector clock. The canonical CrownThrive External Evidence Relay remains the Google Drive connector failure domain. CHLOM owns source-prefix integrity, export protocol, checkpoint semantics, and recovery evidence.

## Current defect addressed

The institutional midnight backup is healthy and byte/readback/restore verified, but it is an institutional-state snapshot rather than a full DAIL ledger-lineage checkpoint. Consequently `read_dail_phase4_assurance_status_v2` can correctly report `HOLD_STALE_CHECKPOINT` even while the generic midnight backup is current.

The DAIL estate is too large for a one-shot RPC export. The connector protocol therefore uses an immutable exact source prefix plus bounded chunks.

## Runtime contract

1. `chlom_runtime.enqueue_dail_cold_checkpoint_v1(false)` reads current Phase-4 assurance and the bounded checkpoint+tail verifier. When COLD is stale and no unresolved DAIL cold job exists, it freezes an exact DAIL source prefix and queues one connector job in the existing backup continuity queue.
2. `public.dail_cold_checkpoint_export_chunk_v1(job_id, after_sequence_id, limit)` exports only the frozen prefix, with a maximum 5,000 events per call. Every chunk carries first/last sequence, first previous hash, last event hash, canonical chunk SHA-256, source head, and the next cursor.
3. The External Evidence Relay composes the restricted package in Google Drive, verifies every chunk hash and cross-chunk chain, reads the exact bytes back, and performs an isolated restore drill.
4. `chlom_runtime.complete_dail_cold_checkpoint_v1(...)` fails closed unless the export count/head, chunk chain, component hashes, package/manifest hashes, structured parse, custody, provider readback, and complete isolated recovery evidence all agree with the frozen source prefix.
5. Completion records a v2 cold checkpoint and existing CHLOM recovery-drill receipt. It does not activate Phase 4 by assertion; the canonical assurance reader decides from current evidence.

## DAIL concurrency repair

The existing v1 checkpoint recorder performs exhaustive chain verification while holding the global DAIL append advisory lock. At current ledger scale that is an unnecessary long critical section. `record_dail_cold_checkpoint_v2` performs the checkpoint+tail verification and source-prefix checks before acquiring a separate short cold-receipt-chain lock. It never takes `chlom_runtime.dail.global.v1` and never performs the legacy full-chain scan.

The DAIL event chain remains immutable. The cold checkpoint receipt chain is independently serialized and append-only.

## Security boundaries

- Export and completion are `service_role`/trusted-database only.
- Public, `anon`, and `authenticated` execution is revoked.
- Database code queues work and exports source bytes only. It does not write Google Drive.
- The existing external relay is reused; no second external scheduler is introduced.
- Export source is frozen to an exact event count, max sequence, and head hash.
- The export RPC cannot read beyond that frozen head and is bounded to 5,000 events per request.
- A provider upload is not a checkpoint. A checkpoint is not recovery assurance. Both exact readback and the complete isolated recovery drill are required.
- No raw credential, private-key, rights, money, vote/quorum, D3, or authority-expansion capability is added.

## Internal due generation

`ct-dail-cold-checkpoint-due-v1` is an internal pg_cron due generator. It may queue a job only when the canonical cold-assurance state is not PASS and there is no unresolved DAIL cold connector job. It creates no provider-write authority.

## Rollback

The rollback unschedules only the new internal due generator and removes only the four introduced functions. Historical DAIL events, cold checkpoint receipts, recovery-drill receipts, generic backup jobs, manifests, and external-relay topology are preserved.

## Release gate

Source readiness is not production readiness. Required release path remains:

`build -> tests/QC -> PentaSecurity -> CHLOM authority -> applicable CIE -> independent PentaCertifier -> governed merge/apply -> connector export/readback -> isolated recovery drill -> exact Phase-4 assurance readback`
