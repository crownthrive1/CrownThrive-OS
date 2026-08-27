#!/usr/bin/env python3
"""Validate the DAIL v2 evidence-spine and factory-continuation contracts."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "developers/contracts/dail-evidence-spine.contract.v2.json"
MANIFEST = ROOT / "developers/manifests/dail-evidence-spine.v2.json"
CONTINUATION = ROOT / "developers/manifests/dail-factory-continuation.v2.json"
DOC = ROOT / "developers/dail-evidence-spine-v2.mdx"

EXPECTED_LAYERS = {
    "ct.pentafabric.identity-imprint",
    "ct.pentafabric.rights-conditions",
    "ct.pentafabric.ledger-assurance",
    "ct.pentafabric.execution-interoperability",
    "ct.pentafabric.economy-distribution",
}
EXPECTED_PALLETS = {f"P-{index:02d}" for index in range(1, 13)}
EXPECTED_OS_SURFACES = {
    "ct.os.canon-source",
    "ct.os.identity-authority",
    "ct.os.rights-licensing",
    "ct.os.thrivebase-domain-state",
    "ct.os.factory-build",
    "ct.os.release-distribution",
    "ct.os.provider-adapters",
    "ct.os.commerce-economics",
    "ct.os.agents-schedulers",
    "ct.os.mesh-continuity",
    "ct.os.backup-preservation",
    "ct.os.docs-public-projections",
    "ct.os.observability-telemetry",
}
REQUIRED_CHECKPOINT_FIELDS = {
    "canonicalization_version",
    "run_id",
    "lane",
    "attempt",
    "state",
    "claim_id",
    "fencing_token",
    "lease_until",
    "idempotency_key",
    "input_digest",
    "output_digest",
    "artifact_digest",
    "authority_ref",
    "correlation_id",
    "causation_id",
    "previous_event_hash",
    "event_hash",
    "provider_idempotency_key",
    "readback_digest",
    "rollback_digest",
}
REQUIRED_V2_HASH_FIELDS = {
    "canonicalization_version",
    "chain_id",
    "sequence_id",
    "source_system",
    "source_event_id",
    "trust_domain",
    "evidence_class",
    "idempotency_key",
    "authority_basis",
    "visibility_class",
    "payload_sha256",
    "verification_receipt_id",
    "previous_event_hash",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate() -> None:
    contract = load(CONTRACT)
    manifest = load(MANIFEST)
    continuation = load(CONTINUATION)

    require(contract["schema_version"] == "2.0.0", "contract schema drift")
    require(manifest["schema_version"] == "2.0.0", "manifest schema drift")
    require(continuation["schema_version"] == "2.0.0", "continuation schema drift")
    require(contract["framework_count_delta"] == 0, "DAIL must not create a ninth framework")
    require(contract["vote_effect"] is False, "DAIL capability pack must not vote")
    require(contract["quorum_effect"] is False, "DAIL capability pack must not affect quorum")
    require(
        contract["native_substrate_state"] == "DEFERRED_TARGET_ARCHITECTURE",
        "native Substrate must remain deferred",
    )
    require(
        contract["truth_boundary"]["hmac_verification_is_not_public_nonrepudiation"] is True,
        "HMAC truth boundary is required",
    )
    require(
        contract["truth_boundary"]["external_anchor_is_not_claimed_until_independent_readback"] is True,
        "anchor readback truth boundary is required",
    )
    require(
        REQUIRED_V2_HASH_FIELDS
        <= set(contract["canonical_chain"]["v2_hash_preimage_required_fields"]),
        "v2 hash preimage omits required provenance or authority fields",
    )
    require(
        set(contract["evidence_classes"])
        == {
            "E0_INTERNAL_ASSERTION",
            "E1_INTERNAL_HASHED",
            "E2_SEPARATE_WORKLOAD_VERIFIED",
            "E3_EXTERNAL_UNVERIFIED",
            "E4_EXTERNAL_SYMMETRIC_VERIFIED",
            "E5_EXTERNAL_ASYMMETRIC_ATTESTED",
            "E6_INDEPENDENTLY_ANCHORED",
        },
        "evidence-class ladder drift",
    )

    layers = {entry["layer_id"] for entry in manifest["pentafabric_layer_bindings"]}
    require(layers == EXPECTED_LAYERS, "all five Pentafabric layers must bind to DAIL")
    pallets = {entry["pallet_id"] for entry in manifest["capability_pallet_bindings"]}
    require(pallets == EXPECTED_PALLETS, "all twelve capability pallets must bind to DAIL")
    require(
        all(entry["dail_receipt_required"] for entry in manifest["capability_pallet_bindings"]),
        "every capability pallet must require DAIL receipts for material events",
    )
    surfaces = {entry["surface_id"] for entry in manifest["os_surface_bindings"]}
    require(surfaces == EXPECTED_OS_SURFACES, "OS material-flow surface binding census drift")
    require(
        all(entry["material_transitions"] for entry in manifest["os_surface_bindings"]),
        "every OS surface must declare its material transitions",
    )
    require(
        manifest["coverage_controls"]["exactly_one_canonical_receipt_per_material_transition"]
        is True,
        "exactly-one material transition coverage is required",
    )
    require(manifest["coverage_controls"]["raw_payload_in_dail"] is False, "raw bodies must stay out")
    require(manifest["coverage_controls"]["secret_in_dail"] is False, "secrets must stay out")

    binding_states = {
        entry["binding_id"]: entry["state"] for entry in manifest["runtime_bindings"]
    }
    require(
        binding_states["ct.dail.independent-anchor.v1"]
        == "SCHEMA_IMPLEMENTED_ADAPTER_NOT_BUILT_NO_PRODUCTION_CLAIM",
        "external anchor cannot be promoted without write/readback evidence",
    )
    require(
        binding_states["ct.dail.external-evidence-relay.v1"]
        == "EXISTING_CLOCK_ADAPTER_PENDING",
        "the existing relay must be reused instead of adding a clock",
    )

    checkpoint_fields = set(continuation["checkpoint_required_fields"])
    require(
        REQUIRED_CHECKPOINT_FIELDS <= checkpoint_fields,
        "factory continuation omits required crash-safe checkpoint fields",
    )
    require(
        continuation["maintenance_reconciliation"]["effective_policy"]
        == "MOST_RESTRICTIVE_GATE_WINS",
        "maintenance conflict must resolve fail closed",
    )
    require(
        continuation["maintenance_reconciliation"]["runtime_apply_allowed_by_this_manifest"]
        is False,
        "a source manifest cannot authorize runtime apply",
    )
    require(
        continuation["continuation_controls"]["stale_worker_completion"] == "REJECT",
        "stale workers must be fenced",
    )
    require(
        continuation["continuation_controls"]["claim_algorithm_source_state"]
        == "SPECIFIED_RUNTIME_PENDING",
        "claim/reclaim cannot be represented as implemented before its worker RPC exists",
    )
    require(
        continuation["continuation_controls"]["missing_readback_or_rollback_may_be_implemented"]
        is False,
        "implementation cannot be inferred without readback and rollback",
    )
    require(
        continuation["receipt_surfaces"]["cross_shape_substitution_allowed"] is False,
        "operational, portable and reference factory receipts are distinct contracts",
    )
    require(
        continuation["production_state"] == "NOT_PROMOTED",
        "source implementation must not self-promote",
    )
    require(DOC.exists(), "DAIL v2 operating documentation is required")


if __name__ == "__main__":
    validate()
    print("DAIL evidence spine v2 validation: PASS")
