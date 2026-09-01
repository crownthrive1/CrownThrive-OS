# PENTA_SURVIVAL_CONTRACT v1

**Contract ID:** `ct.penta.survival-policy.v1`
**Effective date:** 2026-08-31
**Owner:** CrownThrive LLC
**Scope:** every registered CrownThrive Penta; verified proof is mandatory for `certified` and `production` maturity
**Failure disposition:** `HOLD_FAIL_CLOSED`

## Decision

Every Penta must declare how its institutional identity, durable state, deterministic behavior, work ownership, recovery, evidence, authority and health survive interruption.

A Penta is not production-safe merely because a model can recreate a plausible response after restart. Production survival means the system can re-establish the **same identity, same authoritative state, same deterministic rules, same queue and lease ownership semantics, same authority boundaries, and the same evidence lineage** without depending on chat memory or model memory.

The machine-readable contract is:

- declaration schema: `schemas/penta/penta-survival-contract-v1.schema.json`;
- executed-proof schema: `schemas/penta/penta-survival-proof-v1.schema.json`;
- policy: `data/penta/survival-policy.v1.json`;
- declaration registry: `data/penta/survival-contracts.registry.json`;
- executed-proof directory: `penta/survival/evidence/`;
- validator and gate: `runtime/penta_survival.py`;
- repository command: `scripts/validate_penta_survival.py`;
- model-off proof plan: `tests/survival/model-off-survival-test-plan.v1.json`.

## Applicability and maturity rule

All registered Pentas enter the protocol.

| Penta maturity | Required survival state |
| --- | --- |
| `specified` | Contract declaration exists; known gaps remain explicit. |
| `implemented` | Contract declaration exists and implementation references are concrete. |
| `hold` | Contract declaration or preserved hold/retirement evidence identifies the unresolved survival boundary. |
| `certified` | Independently verified, unexpired contract bound to the exact release subject. |
| `production` | Independently verified, unexpired contract bound to the exact source, artifact, doctrine and compiled behavior. |
| `retired` | Last effective contract and retirement/recovery disposition remain preserved. |

A current production label does not manufacture survival proof. A production Penta lacking verified survival evidence enters `SURVIVAL_HOLD` for **new promotion, changed production scope and release eligibility**. This policy does not silently kill an already running bounded service, rewrite historical production evidence or claim that an untested shutdown is safer. It prevents the gap from creating new authority and ratchets the system toward zero survival debt.

## Exact release subject

A verified contract is not generic. It binds to:

```text
penta_id
+ exact source ref
+ source commit SHA
+ artifact SHA-256
+ runtime version
+ doctrine version
+ compiled behavior hash
+ deterministic function-set hash
+ evidence bundle SHA-256
+ independent verifier
+ evidence expiration
```

The release invariant is:

```text
candidate SHA = certified SHA = production SHA
```

A certificate for one commit, artifact, doctrine or compiled behavior cannot be reused for another. Any mismatch or expiration returns `HOLD_FAIL_CLOSED`.

### Immutable candidate / proof-metadata split

The runtime candidate and the proof metadata are intentionally different Git subjects:

1. candidate commit **A** is fixed and the deployable artifact is built from A;
2. the restart, model-off, recovery, queue, lease, authority and negative tests execute against A;
3. an independent verifier emits a content-addressed proof bundle that binds A and the artifact digest;
4. the declaration, proof bundle and registry digest may be committed in control-plane metadata commit **B**, or stored in another governed evidence store;
5. the release gate runs from B, verifies that A still exists, and releases only the artifact built from A.

`A` remains the candidate, certified and production source SHA. `B` is control-plane evidence metadata, not a rebuilt candidate. Requiring the declaration to contain the SHA of the same commit that contains the declaration would create an impossible self-referential hash and is therefore forbidden. The binding mode is `external_exact_subject_proof`.

## Required footprint

### `persistent_identity`

Declares the stable `penta.*` machine identity and its canonical registry source. It must survive process restart and node replacement and remain independent from host, provider, process and model identity.

Required proof demonstrates that a model/provider swap or process restart does not create a new Penta or lose the old one.

### `persistent_state`

Declares the authoritative external state store, state schema, checkpoint strategy, backup, restore test, RPO and RTO.

Non-negotiable rules:

- authoritative state is externalized;
- process memory is never the sole authoritative store;
- recovery does not reconstruct institutional truth from model inference;
- restored state is versioned and digest-comparable.

### `deterministic_functions`

Lists the functions whose inputs, outputs and decisions must replay deterministically. Each function declares:

- function name and semantic version;
- implementation SHA-256;
- input and output schemas;
- replay vectors and their SHA-256;
- isolated side-effect mode;
- proof that stored inputs replay to the same output.

The function set has a canonical digest. The contract also binds the compiled behavior hash to the exact release.

A Penta with no applicable deterministic function must explicitly declare `not_applicable` and explain why. Omission is not an acceptable declaration.

### `queues`

Declares every durable work queue and proves stable job IDs, idempotency, retry policy, dead-letter handling, delivery semantics and ordering.

A redelivered job may create another attempt. It may not create a duplicate authoritative effect, entitlement, payment, provider write, receipt or audit outcome.

A Penta that does not use queues must explicitly declare that fact and the reason.

### `leases`

Declares every time-bounded ownership lease, TTL, renewal interval, clock source, fencing token and stale-owner rejection proof.

A replacement owner must receive a new fencing token. The prior owner must be unable to produce a valid effect after expiration or takeover.

A Penta that does not use leases must explicitly declare that fact and the reason.

### `recovery`

Declares the recovery strategy, RPO, RTO, backup/restore test, isolated recovery test and dependency rebuild path.

Recovery must work without a model. A model may help explain recovery evidence after the fact; it cannot be the recovery mechanism or authority source.

### `evidence`

Declares an immutable, content-addressed evidence bundle tied to the exact release subject. Required evidence includes:

- execution and receipt lineage;
- negative tests;
- stress tests;
- restart/fault-injection tests;
- the model-off survival test;
- evidence timestamp and expiration;
- evidence-manifest SHA-256.

A test plan, workflow definition, documentation page or generated claim is not proof that the runtime passed. Evidence must record the exact executed subject and observed result.

### Executed survival proof bundle

A `verified` attestation is never accepted by itself. Certified and production contracts must point to an immutable JSON proof bundle under `penta/survival/evidence/` whose canonical SHA-256 equals both `evidence.manifest_sha256` and `attestation.evidence_bundle_sha256`.

The bundle must:

- bind the exact candidate source, artifact, runtime, build, doctrine, compiled behavior and deterministic function-set digests;
- bind the canonical model-off test-plan digest;
- cover every plan case with `pass` or an independently justified `not_applicable` disposition;
- force the unconditional identity, state, DAIL, CHLOM, exact-subject certification, model-off, crash-boundary and isolated restore cases to pass;
- require queue, lease, deterministic replay and model-replacement cases when those capabilities apply;
- identify an independent verifier, verification method, run reference and receipt chain;
- remain unexpired and report zero failed applicable cases;
- state that the proof run did not manufacture authority or promote production.

The validator recomputes the proof-bundle digest and test-plan digest. A prose claim, arbitrary URI, workflow definition or `attestation.status=verified` field cannot produce `VERIFIED`.

### `authority_enforcement`

Declares the deterministic mutation boundary, CHLOM authority reference, DAIL evidence reference, exact-candidate rule, provider binding/readback rule and append-only audit/receipt requirements.

The model boundary is absolute:

```text
model may propose
model may not authorize
model may not mutate authoritative state
model may not directly write providers
model may not replace CHLOM, DAIL, receipts, queues, leases or exact-release evidence
```

Missing, mismatched or expired authority fails closed.

### `health_check`

Separates three questions:

1. **Liveness:** is the process responsive?
2. **Readiness:** are durable dependencies and authority boundaries ready for dispatch?
3. **Survival:** can identity, state, queues, leases, evidence and deterministic behavior reconcile after disruption?

Health must expose dependency, authority, queue, lease, model and degraded states separately. A responsive process is not necessarily ready. An unavailable model is not necessarily a failed deterministic core. A healthy model is not proof of a healthy Penta.

### `model_dependency`

Declares one of:

- `none` — the runtime does not require a model;
- `optional` — the model improves or proposes work but the deterministic core remains operable;
- `proposal_required` — new cognition/proposals stop without the model, while deterministic authority and continuity remain intact.

Every mode must preserve durable state, queue/lease safety and authority independently from the model. Model output remains an untrusted proposal until validated.

### `degraded_without_model`

Declares the exact model-off mode, permitted operations, forbidden operations and health state.

Permitted behavior can include recovery, deterministic replay, health emission, evidence verification, work reconciliation and processing already-authorized deterministic jobs. The contract must not falsely claim full capability when the Penta depends on model-generated proposals.

The following remain forbidden in every degraded mode:

- model authorization;
- model direct mutation;
- model direct provider write.

### `replaceable_model`

When a model is used, it must sit behind an adapter contract and compatibility tests. Replacing the model or provider must preserve:

- Penta identity;
- durable state;
- authority outcomes;
- deterministic replay results.

The provider/model identifier never becomes the Penta identity.

### `restart_behavior`

Declares and proves behavior across at least:

- graceful restart;
- crash before commit;
- crash after commit but before receipt;
- queue redelivery;
- lease owner loss;
- model unavailable;
- model replaced.

The restart matrix must prove identity preservation, state rehydration, in-flight reconciliation, stable job IDs, duplicate-effect prevention, stale-lease fencing and authority re-evaluation.

## Model-off survival acceptance suite

The canonical model-off plan explicitly tests:

- PentaDND leases, TTLs and conflict precedence;
- PentaQueue work and state persistence;
- PentaPM assignment and accountable ownership;
- DAIL append-only history;
- CHLOM authority continuity;
- PentaCertifier exact-subject certificates;
- PentaSELF case identity and replay;
- COS phase cursor and completed dependency persistence;
- crash windows across database, outbox, execution, receipt and audit boundaries;
- model unavailable and model replacement behavior;
- isolated backup/restore.

The plan is a requirement, not evidence. Each Penta must attach exact-subject receipts for every applicable case.

## Enforcement

### Full census audit

```bash
python3 scripts/validate_penta_survival.py --root . audit \
  --output artifacts/penta-survival-audit.json
```

The audit always exposes all family coverage gaps. Audit mode does not convert a gap to PASS; it exits zero so the migration census can be generated even while debt exists.

### Full production check

```bash
python3 scripts/validate_penta_survival.py --root . check \
  --output artifacts/penta-survival-check.json
```

This command fails when any `certified` or `production` family member lacks an independently verified, unexpired contract.

### Pull-request ratchet

```bash
python3 scripts/validate_penta_survival.py --root . ratchet \
  --base-ref origin/main \
  --output artifacts/penta-survival-ratchet.json
```

The ratchet blocks:

- a new registered Penta without a declaration;
- any changed registered Penta without a valid declaration;
- a changed `certified` or `production` Penta without independently verified exact-release proof;
- an invalid, missing, mismatched or expired contract;
- a registry hash that does not match the contract.

Existing gaps remain visible debt but cannot be used to create new or broadened authority.

### Exact release gate

```bash
python3 scripts/validate_penta_survival.py --root . release \
  --penta-id penta.example \
  --source-commit <40-hex-sha> \
  --artifact-sha256 <64-hex-sha256> \
  --doctrine-version <version> \
  --compiled-behavior-hash <64-hex-sha256>
```

The release gate checks out the control-plane declaration/proof commit, confirms the immutable candidate commit exists and is an ancestor without checking it out as metadata, validates the content-addressed proof, and emits a deterministic PASS/HOLD receipt. It performs no deployment and no provider write.

The governed merge gate consumes the survival audit, deterministic tests and change ratchet immediately. The reusable exact-release workflow is the mandatory pre-mutation interface for PentaRelease, PentaCertifier and provider deployment callers once they supply `penta_id`, candidate SHA and artifact digest. A legacy release workflow that does not yet carry those exact-subject inputs is not represented as survival-certified; its caller plumbing remains explicit migration debt rather than a manufactured PASS.

## Census and portal projection

PentaCensus and each Penta portal should project, but not redefine, these fields:

- `survival_contract_ref`;
- `survival_contract_sha256`;
- `survival_status`;
- `survival_validation_receipt_sha256`;
- `evidence_as_of`;
- `evidence_expires_at`;
- `model_dependency_mode`;
- `degraded_without_model_mode`;
- `last_restart_test_at`;
- `last_model_off_test_at`;
- `production_release_eligible`.

PentaDocs, dashboards and portals are projections. The canonical contract and exact evidence remain the authority source.

## Migration sequence

1. PentaCensus enumerates all registered identities and maturity states.
2. Each Penta creates a stable declaration from `data/penta/survival-contract.template.v1.json`.
3. The deployable candidate source commit and artifact are fixed; they are not changed by later proof metadata.
4. Model-off, restart, redelivery, fencing, recovery, authority-negative and exact-release tests run against that immutable candidate.
5. PentaAssure/PentaCertifier emits an independent proof bundle conforming to `schemas/penta/penta-survival-proof-v1.schema.json`.
6. The declaration binds the exact candidate and proof-bundle digest, then is registered with its own canonical digest in a later control-plane metadata commit.
7. Full `check` reaches zero production blockers.
8. PentaRelease and production dispatch call the exact release gate from the control-plane metadata commit before provider mutation.

No waiver or prose assertion substitutes for missing proof. The safe state is visible `HOLD_FAIL_CLOSED`, followed by repair, retest and re-verification.

Retirement does not erase survival lineage. A retired Penta retains its last valid declaration and recovery/evidence references so identity, historical state and restart behavior remain reconstructable without treating the member as execution-eligible.
