# Penta Identity, Label & Family Fabric v1

This source-controlled projection matches the live ThriveBase identity/family reconciliation fabric introduced on 2026-08-30.

## Purpose

Every admitted Penta and Penta Family must be known to the operating system as a canonical identity with preserved aliases, system-native labels, role/job, family/state, activation state, runtime state, maturity, and evidence lineage. Documentation presence alone does not create execution authority.

## Historical invariant

Identity history is append-only and SHA-256 bound. Canonical records are never destructively deleted. Renames, aliases, retired families, previous family assignments, and supersessions remain evidence. Retire or supersede; do not erase.

## Runtime surfaces

- `integration_control.penta_identity_registry_v1`
- `integration_control.penta_identity_aliases_v1`
- `integration_control.penta_identity_labels_v1`
- `integration_control.penta_identity_history_v1`
- `integration_control.penta_family_runtime_v1`
- `integration_control.penta_identity_projection_receipts_v1`
- `integration_control.penta_identity_refresh_v1(text)`
- `integration_control.penta_identity_lookup_v1(text)`
- `integration_control.penta_family_status_v1(text)`
- `integration_control.penta_family_route_v1(text,text)`

The family router is coordination software only. It never inherits a member's credential, provider, financial, D3, deployment, certification, or dispatch authority.

## Verified first reconciliation

Run `cad6019e-ada1-4a5c-8cbe-2d24b45f60eb` processed all 437 active citizens, activated 15 Family runtime identities, assigned jobs to all 437 citizens, and emitted 3,996 active system labels. It produced 449 canonical fabric identities because PentaMail, PentaHeartbeat, and PentaOD each had two historical citizen/source representations that correctly resolve to one canonical identity with preserved aliases.

Runtime evidence at the first post-reconciliation readback:

- 83 `ACTIVE`
- 305 `ACTIVE_FAIL_CLOSED`
- 46 `HOLD_FAMILY`
- 140 `RUNTIME_PRESENT`
- 39 `IMPLEMENTED_SOURCE`
- 255 `INSTITUTIONAL_ONLY`

The 46 `HOLD_FAMILY` identities remain citizens with jobs and system awareness, but PentaDocs still reports their canonical family as pending; no family assignment is fabricated.

## Source authority

The reconciliation consumes an exact snapshot of `data/penta/os-v1.registry.json` from main SHA `845deac432b3210e73f61dffde8e335a84d24837`, registry version 1.5.0. The fetched file SHA-256 is `052a9bdcdd31e6f10f2c95ea56d4486366b6b125a9c0122036061c3ede10227b`; the registry-declared SHA-256 is `bafdea05053e7c4e85a4c8a6af16df5177cfa73c00c3a7fd2e2b090e2619eed1`.

Provider migration source custody is preserved using the provider-issued migration versions and exact provider SQL bodies. Production history was not rewritten and replay was not attempted.
