# Phase 2.99 — CHLOM Builder Cells and Reference Kernel

Baseline: `12f0dd9ab97391a8dd34438f77262438c0df0999`.

This packet begins executable CHLOM construction without advancing Phase 3. It creates ten bounded, non-voting build cells, an open-source intake registry, a provider-independent Python reference kernel, deterministic policy evaluation, approval/D3 holds, DAIL hash chaining, documentation-impact normalization, unit tests and a living-status generator.

The packet intentionally avoids the active PR #64/#65 ownership surfaces. It does not modify their agent-governance manifest/validator or governance workflows. It should remain draft while the current security/RLS gate is unresolved and must be reconciled with the Node-24/runtime and specialist-gate packets before any later CI wiring or production activation.

Community candidates are recorded only after direct GitHub LICENSE verification: Open Policy Agent (Apache-2.0), OpenFGA (Apache-2.0), Cedar (Apache-2.0) and Temporal (MIT). No source is copied from those repositories in this tranche; no upstream project becomes CrownThrive policy, rights or institutional authority.

Definition of done for this tranche: reference unit tests pass; DAIL chain verifies; default deny and restricted-publication deny pass; D3 and missing-rights-approval requests hold; living status renders from manifests; no secret/restricted body appears; production activation remains false; Phase 3 remains blocked_pending_phase_2_99_hard_exit.
