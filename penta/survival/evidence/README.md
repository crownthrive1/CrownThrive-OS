# Penta Survival Executed Evidence

This directory stores content-addressed `PENTA_SURVIVAL_PROOF_BUNDLE` records for exact immutable Penta release subjects.

Rules:

- proof files conform to `schemas/penta/penta-survival-proof-v1.schema.json`;
- one proof binds one exact Penta ID, candidate source commit, artifact digest, runtime/build, doctrine, compiled behavior and deterministic function-set digest;
- the proof is generated only after the candidate is fixed; it may live in a later control-plane metadata commit;
- the declaration's `evidence.manifest_sha256` and `attestation.evidence_bundle_sha256` must both equal the canonical SHA-256 of the complete proof JSON;
- every canonical model-off test-plan case appears exactly once as `pass` or independently justified `not_applicable`;
- self-attestation, model output, workflow definitions, placeholders and undocumented omissions are not proof;
- proof generation never changes the candidate, manufactures authority, or promotes production.

The repository starts with no production proof files. Existing production gaps remain visible `SURVIVAL_HOLD` debt until exact tests and independent verification are executed.
