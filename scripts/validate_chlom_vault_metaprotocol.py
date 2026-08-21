#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "developers/manifests/chlom-vault-metaprotocol.v1.json").read_text())
doc = (ROOT / "developers/chlom-vault-metaprotocol-and-custody.mdx").read_text()

assert manifest["contract_id"] == "ct.chlom.vault-metaprotocol.v1"
assert manifest["chlom_expansion"] == "Compliance Hybrid Licensing and Ownership Model"
assert manifest["dail_expansion"] == "Decentralized Autonomous Information Ledger"

boundary = manifest["public_private_boundary"]
assert boundary["protected_body_publicly_reachable"] is False
assert boundary["raw_secret_export"] is False
assert "secret_values" in boundary["restricted_fields"]
assert "vault_topology" in boundary["restricted_fields"]
assert "private_identity_mapping" in boundary["restricted_fields"]

alg = manifest["algorithm_registry"]
assert alg["current_algorithm_count"] == 20
assert alg["custody_capsule_required"] is True
assert alg["implementation_bundle_required_before_invocable"] is True
assert alg["disabled_when_handler_unmaterialized"] is True

identity = manifest["hybrid_identity"]
assert identity["public_fingerprint_profile"] == "ct-identity-stable-v1"
assert identity["private_identifier_random"] is True
assert identity["private_identifier_derived_from_public"] is False
assert identity["mapping_immutable"] is True
assert identity["mapping_public"] is False
assert identity["client_private_identifier_return"] is False

cap = manifest["capability_gateway"]
assert cap["raw_secret_operations_supported"] is False
assert cap["mcp_broker_role"] == "authenticated_capability_broker"
assert cap["execution_gateway_role"] == "server_side_protected_execution"
ops = {x["key"]: x for x in cap["operations"]}
assert ops["provider_proxy"]["state"] == "specified_hold"
assert ops["script_execute"]["state"] == "specified_hold"
assert ops["script_execute"]["arbitrary_dynamic_execution"] is False
assert ops["identity_resolve_receipt"]["private_id_return"] is False

archive = manifest["archive"]
assert archive["logical_period"] == "monthly"
assert archive["revision_model"] == "immutable_revisions_within_month"
assert archive["key_in_archive"] is False
assert archive["key_in_public_repo"] is False
assert archive["history_policy"] == "append_or_supersede_never_silent_delete"
snap = archive["current_snapshot"]
assert snap["revision"] == 3
assert snap["algorithm_count"] == 20
assert snap["protected_asset_count"] == 68
assert snap["hybrid_private_identity_mapping_count"] == 1
assert snap["ciphertext_sha256"] == "3034b0904e5ba53f2080dca57c9784bc40b331ac9f16d827df6ab4125548b76e"
assert snap["zip_sha256"] == "deb0d91a259d72776eeecfe82878932374348eeb72a3737a78b5fd3836c9b67a"
assert snap["ciphertext_bytes"] == 17739
assert snap["zip_bytes"] == 18890
assert archive["historical_revisions_preserved"] == [1, 2]

agentic = manifest["agentic_custody"]
assert agentic["external_scheduler_slots_added"] == 0
assert agentic["non_voting"] is True
assert agentic["d2_maximum"] is True
assert agentic["history_preserved"] is True

novel = manifest["novel_asset_foundry"]
assert novel["enabled"] is True
assert novel["auto_publication"] is False
assert novel["auto_commerce_activation"] is False
assert novel["monetization_default"] == "candidate_hold"

gov = manifest["governance"]
assert gov["d0_d1_routine_custody_needs_new_sovereign_vote"] is False
assert gov["d2_independent_verification_policy_applies"] is True
assert gov["d3_human_reserved"] is True
assert gov["history_may_be_silently_deleted"] is False

chain = manifest["blockchain_portability"]
assert chain["current_ledger"] == "DAIL"
assert chain["blockchain_required_for_current_controlled_test"] is False
assert chain["future_anchor_must_not_require_secret_body"] is True

# Public disclosure negative controls. These names/topology strings must not appear in the public doctrine.
for forbidden in (
    "decrypted_secret",
    "SUPABASE_SERVICE_ROLE_KEY",
    "private_subject_id: ctpriv:",
    "BEGIN PRIVATE KEY",
    "CHLOM_FALLBACK_VAULT_PASSWORD",
    "chlom_drive_archive_key_2026_08_v1",
    "chlom_metaprotocol_capability_root_v1",
):
    assert forbidden not in doc, f"protected topology/material leaked in public doc: {forbidden}"

print("CHLOM Vault metaprotocol public invariants: PASS")
