# CHLOM Living Docs → dS-CaaS Runtime Contract

CrownThrive's living documentation governs approved meaning. The executable CHLOM runtime consumes validated, versioned machine contracts referenced by that documentation; it does **not** execute free-form prose.

The intended control path is:

`source/evidence → governed article/standard → versioned machine policy/contract → deterministic validation → reference/provider policy engine → decision → DAIL event → docs-impact reconciliation`.

This separation is important. Human-readable documents explain authority, scope, effective periods, rights and remedies. Machine bundles carry exact rule IDs, conditions and outputs. A policy engine such as OPA or Cedar may execute a compiled representation, but CrownThrive retains policy identity, precedence, approval, effective-period, evidence and correction authority. OpenFGA may answer relationship questions, but CrownThrive retains actor/organization/delegation semantics. Temporal may schedule workflows, but CrownThrive retains approval, hold, remedy and DAIL meaning.

Every executable policy bundle must have a stable ID/version, source and authority references, effective window, test fixtures, default-deny behavior, unknown-condition fail-closed behavior, required approvals, data classification, documentation-impact references, rollback/supersession reference and DAIL event mapping.

The Phase 2.99 reference runtime proves four foundational behaviors now: authenticated/organization boundary checks, deterministic fail-closed policy evaluation, D3/approval holds and append-only hash-chained DAIL events. It performs no provider mutation, payment, rights grant, credential rotation or production deployment.
