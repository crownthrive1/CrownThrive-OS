# Phase 2.99 — CHLOM Cell 04 Evidence/DAIL contract v1

This bounded prototype packet advances issue #71 under parent build lane #67 without changing provider, credential, database, payment, rights-grant or production state.

Machine authority in this packet is carried by the versioned JSON contracts/manifest and executable reference tests. This prose is explanatory only.

## Added

- `ct.contract.chlom.dail-event.v1` / `1.0.0` for stable event identity, sequence, correlation, causation, classification, source/evidence references, correction/supersession, hash-chain metadata and documentation impact.
- `ct.contract.chlom.evidence-reference.v1` / `1.0.0` for content-free source/proof pointers with SHA-256 digest, classification, retention and public-projection controls.
- `ct.fixture.chlom.dail-evidence-contract.v1` with a four-event source → decision → conflict/hold → correction lineage and restricted-evidence reference fixtures.
- Standard-library-only executable reference checks for hash-chain integrity, tamper detection, prior-event causation, correction history preservation, restricted-reference safety, decision-lineage reconstruction and portable export/backup bundles.
- A dedicated Node-24-pinned GitHub Actions workflow for Cell 04 acceptance evidence.

## Fail-closed boundaries

- Raw restricted/SEALED evidence bodies are not permitted in the public fixture or machine reference objects.
- A stale/conflicting source opens `hold` and `docs_delta_opened`; it never becomes permission by absence of evidence.
- Correction/supersession preserves the earlier event in the chain rather than overwriting history.
- Causation and supersession may reference only prior events in the verified chain.
- Export is refused when chain verification fails.
- Free-form documentation does not execute policy or create authority.

## Governance

Risk class: D2 semantic evidence/attestation contract.

Required independent specialist gates: Security & Privacy and IP/Rights/Licensing.

Originating Agent B does not self-approve this material packet. Parent #67 remains promotion-held behind the active #64 → provider-main-perimeter verification → #65 governance sequence. Phase 2 / 2.99 remains current under CT-ADR-ROADMAP-010 / `ten_phase_v1`; Phase 3 remains `blocked_pending_phase_2_99_hard_exit`.

Documentation impact: `docs_updated`.

Rollback is a revert of this bounded child packet; no external state exists to unwind.
