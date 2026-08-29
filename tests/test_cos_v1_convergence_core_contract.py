from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "penta" / "cos-v1-convergence-core.v1.json"
ARCHITECTURE = ROOT / "docs" / "COS_V1_CONVERGENCE_ARCHITECTURE.md"
GUARD = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260829070000_cos_v1_convergence_guard.sql"
)


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_release_identity_and_typed_truth() -> None:
    data = manifest()
    assert data["contract_id"] == "ct.cos.release.1.0.0"
    assert data["semantic_version"] == "1.0.0"
    assert data["release_name"] == "CrownThrive COS V1.0.0"
    authorities = data["source_of_truth"]["authorities"]
    assert len(authorities) == 7
    by_type = {item["truth_type"]: item for item in authorities}
    assert by_type["institutional_history"] == {
        "truth_type": "institutional_history",
        "authority": "DAIL",
        "conflict_rule": "history_is_immutable",
    }
    assert by_type["rights_authority_identity"]["authority"] == "CHLOM"
    assert by_type["provider_current_state"]["authority"] == "Direct provider readback"
    assert by_type["provider_current_state"]["conflict_rule"] == "provider_wins_current_state"
    assert by_type["reconciled_current_state"]["authority"] == "PentaSELF + PentaCensus"
    assert by_type["operational_capability"]["authority"] == "PentaWire + PentaCertify"


def test_cos_kernel_preserves_protocol_roles() -> None:
    kernel = manifest()["kernel"]
    assert kernel["pentas"] == "motion"
    assert kernel["dail"] == "immutable institutional history"
    assert kernel["penta_cookies"] == "local live state and capability descriptors"
    assert kernel["penta_census"] == "reconciled institutional state"
    assert "decentralized trust" in kernel["chlom"]
    assert kernel["penta_self"] == "autonomous resilience and monotonic repair"
    assert "continuous" in kernel["penta_planner"]
    assert "independent" in kernel["penta_certify"]
    assert "verified outcome" in kernel["penta_closer"]


def test_pentas_cos_epoch_is_signed_and_node_bound() -> None:
    routing = manifest()["routing_model"]
    assert routing["network_epoch"] == "cos-v1"
    assert routing["protocol_id"] == "ct.pentas.packet.v2"
    assert routing["protocol_version"] == "2.0.0"
    assert routing["signed_packets_required"] is True
    assert routing["origin_node_required"] is True
    assert routing["content_addressed"] is True
    assert routing["immutable_receipts_required"] is True
    assert set(routing["routing_modes"]) == {
        "system",
        "capability",
        "factory",
        "persona",
        "role",
        "topic",
        "quorum",
        "broadcast",
    }
    assert routing["legacy_signed_epoch"] == "pentas-v2-hybrid"
    assert routing["legacy_signed_epoch_state"] == "accepted_legacy"


def test_dail_trust_is_checkpointed_without_false_chain_claim() -> None:
    trust = manifest()["dail_trust"]
    assert trust["contract"] == "ct.dail.trust-checkpoint.v2"
    assert trust["hash_algorithm"] == "SHA-256"
    assert trust["signature_algorithm"] == "HMAC-SHA256"
    assert trust["checkpoint_signature_required"] is True
    assert trust["historical_events_rewritten"] is False
    assert trust["external_chain_anchor_state"] == "production_gated"
    assert trust["external_chain_transaction_claimed"] is False
    assert len(trust["production_chain_anchor_requires"]) == 4


def test_census_has_all_required_entity_kinds() -> None:
    census = manifest()["cos_census"]
    kinds = census["entity_kinds"]
    assert census["entity_kind_count"] == 34
    assert census["all_entity_kinds_populated"] is True
    assert census["unknown_lifecycle_entities_allowed"] is False
    assert len(kinds) == 34
    assert len(set(kinds)) == 34
    for required in (
        "system",
        "penta",
        "provider",
        "adapter",
        "credential_binding",
        "factory",
        "persona",
        "agent",
        "scheduler",
        "workflow",
        "repository",
        "branch",
        "release",
        "deployment",
        "website_surface",
        "domain",
        "database",
        "schema",
        "dataset",
        "drive_artifact",
        "form",
        "product",
        "price",
        "entitlement",
        "campaign",
        "media_asset",
        "chlom_asset",
        "wallet",
        "protocol",
        "policy",
        "evidence_artifact",
        "incident",
        "hold",
        "commercial_opportunity",
    ):
        assert required in kinds


def test_repository_federation_is_exact() -> None:
    repos = manifest()["repository_convergence"]
    assert repos["provider_observed_repositories"] == 14
    assert repos["federation_accounted"] == 14
    assert repos["runtime_accounted"] == 14
    assert repos["provider_is_current_state_authority"] is True
    assert repos["historical_aliases_preserved"] is True
    assert repos["unresolved_identity_is_not_invented"] is True
    assert len(repos["repositories"]) == 14
    assert len(set(repos["repositories"])) == 14
    assert "crownthrive1/CrownThrive-OS" in repos["repositories"]
    assert "crownthrive1/CrownThrive-CIE-OS" in repos["repositories"]
    assert "crownthrive1/chlom-protocol" in repos["repositories"]
    assert "crownthrive1/brilliant-directories-mcp" in repos["repositories"]


def test_factory_registry_contains_all_eleven_factories() -> None:
    convergence = manifest()["factory_convergence"]
    factories = convergence["factories"]
    assert convergence["factory_count"] == 11
    assert convergence["production_enabled_count"] == 11
    assert convergence["offline_count"] == 0
    assert convergence["repair_route_required"] is True
    assert convergence["weekend_default"] == "plan_and_prepare"
    assert len(factories) == 11
    assert len({item["factory_key"] for item in factories}) == 11
    assert all(item["production_enabled"] for item in factories)
    assert all(item["repair_route"] for item in factories)
    by_key = {item["factory_key"]: item for item in factories}
    assert by_key["penta.persona-factory"]["name"] == "PentaPersonaFactory"
    assert by_key["penta.planner-factory"]["candidate_only"] is True
    assert by_key["penta.proprietary-asset-factory"]["candidate_only"] is True
    assert by_key["penta.software-factory"]["candidate_only"] is False


def test_planner_and_persona_factory_are_continuous_but_bounded() -> None:
    planner = manifest()["planner"]
    assert planner["state"] == "production_active"
    assert planner["weekend_mode"] == "plan_and_prepare"
    assert planner["overnight_mode"] == "plan_and_prepare"
    assert planner["maximum_candidates_per_cycle"] == 25
    assert planner["maximum_factory_submissions_per_cycle"] == 5
    assert planner["maximum_persona_submissions_per_cycle"] == 5
    assert planner["maximum_active_factory_wip"] == 12
    assert planner["dedupe_required"] is True
    assert planner["d3_auto_execution"] is False
    assert "Every non-current" in planner["idle_hold_policy"]

    persona = manifest()["persona_factory"]
    assert persona["state"] == "production_active"
    assert persona["reuse_existing_first"] is True
    assert persona["new_persona_last_resort"] is True
    assert persona["independent_certification_required"] is True
    assert persona["controlled_test_required"] is True
    assert persona["maximum_new_persona_candidates_per_day"] == 3
    assert persona["authority_ceiling"] == "D2"


def test_wire_openai_and_site_truth_are_not_overclaimed() -> None:
    adapters = manifest()["adapter_and_provider_convergence"]
    assert adapters["penta_wire_state"] == "pass"
    assert adapters["provider_contract_holds"] == 0
    assert adapters["tool_contract_drift_services"] == 0
    assert adapters["unresolved_tools"] == 0
    assert adapters["openai_factory_generator"]["capability"] == "capability://code-generation"
    assert adapters["openai_factory_generator"]["production_capable"] is True
    assert adapters["openai_factory_generator"]["raw_secret_exposure"] is False

    sites = manifest()["site_truth"]
    assert sites["surface_count"] == 22
    assert sites["availability_separate_from_truth"] is True
    assert sites["unknown_truth_state_allowed"] is False
    assert sites["noncurrent_surfaces_must_be_repair_routed"] is True
    snapshot = sites["current_snapshot"]
    assert sum(snapshot.values()) == 22
    assert snapshot["unknown"] == 0
    assert snapshot["stale"] == 11
    assert snapshot["intentionally_gated"] == 11
    assert "does not mean current" in sites["interpretation"].lower()


def test_only_two_cos_orchestration_clocks_are_created() -> None:
    runtime = manifest()["canonical_cos_runtime"]
    assert runtime["status"] == "public.cos_v1_status_v2"
    assert runtime["convergence"] == "public.cos_v1_convergence_cycle_v2"
    assert runtime["certification"] == "public.cos_v1_certify_v1"
    clocks = {item["jobname"]: item["schedule"] for item in runtime["clocks"]}
    assert clocks == {
        "ct-dail-trust-checkpoint-v2": "7,22,37,52 * * * *",
        "ct-cos-v1-convergence-v2": "9,19,29,39,49,59 * * * *",
    }
    assert runtime["specialist_clocks_reused"] is True
    assert runtime["duplicate_specialist_execution_created"] is False


def test_certification_invariants_are_explicit() -> None:
    invariants = manifest()["certification_invariants"]
    assert invariants["typed_truth_authorities"] == 7
    assert invariants["entity_kinds_registered"] == 34
    assert invariants["entity_kinds_populated"] == 34
    assert invariants["repositories_provider_observed"] == 14
    assert invariants["repositories_federation_accounted"] == 14
    assert invariants["repositories_runtime_accounted"] == 14
    assert invariants["scheduler_unknown"] == 0
    assert invariants["site_truth_unknown"] == 0
    assert invariants["repair_routing_gaps"] == 0
    assert invariants["pentas_cos_v1_canary_required"] is True
    assert invariants["dail_merkle_proof_required"] is True
    assert invariants["penta_wire_pass_required"] is True
    assert invariants["pentamail_serialized_epoch_required"] is True


def test_security_boundaries_are_fail_closed() -> None:
    boundaries = manifest()["boundaries"]
    assert boundaries["one_hundred_percent_convergence_is_not_one_hundred_percent_enabled"] is True
    assert boundaries["every_observed_entity_must_be_identified_classified_governed_evidence_addressable_and_repair_routable"] is True
    assert boundaries["d3_human_reserved"] is True
    assert boundaries["money_movement_created"] is False
    assert boundaries["provider_authority_created"] is False
    assert boundaries["raw_secret_material_committed"] is False
    assert boundaries["external_chain_anchor_complete"] is False
    assert boundaries["external_chain_anchor_state"] == "production_gated"


def test_architecture_preserves_source_terminology_and_boundaries() -> None:
    text = ARCHITECTURE.read_text(encoding="utf-8")
    for phrase in (
        "Pentas is motion",
        "DAIL is history",
        "PentaCookies are local live state",
        "PentaCensus is reconciled institutional state",
        "CHLOM is trust",
        "availability health",
        "truth freshness",
        "One hundred percent convergence",
        "HOT",
        "WARM",
        "COLD",
        "plan_and_prepare",
        "D3",
        "production_gated",
    ):
        assert phrase.lower() in text.lower()
    assert "No external transaction is claimed" in text
    assert "does not claim that all public sites" in text


def test_source_guard_covers_load_bearing_runtime() -> None:
    sql = GUARD.read_text(encoding="utf-8")
    required = (
        "COS_V1_REQUIRED_SCHEMA_INCOMPLETE",
        "COS_V1_REQUIRED_FUNCTION_SET_INCOMPLETE",
        "COS_V1_TYPED_TRUTH_AUTHORITY_COUNT",
        "COS_V1_CENSUS_INCOMPLETE",
        "COS_V1_REPOSITORY_CONVERGENCE_FAILED",
        "COS_V1_CANONICAL_CLOCK_DRIFT",
        "COS_V1_SITE_TRUTH_GAP",
        "COS_V1_FACTORY_CONVERGENCE_FAILED",
        "COS_V1_PENTAS_END_TO_END_CANARY_FAILED",
        "COS_V1_DAIL_TRUST_FAILED",
        "COS_V1_PENTAWIRE_FAILED",
        "COS_V1_OPENAI_PENTA_INFERENCE_NOT_READY",
        "COS_V1_PENTAOFAC_CURRENT_PROVIDER_EVIDENCE_MISSING",
        "COS_V1_PENTAMAIL_RECEIPT_EPOCH_STATE",
        "COS_V1_PENTAPLANNER_NOT_PRODUCTION_ACTIVE",
        "COS_V1_PERSONA_FACTORY_NOT_PRODUCTION_ACTIVE",
        "COS_V1_FACTORY_FLEET_NOT_OPERATIONAL",
        "COS_V1_PENTASELF_NOT_PRODUCTION",
        "COS_V1_DAIL_CHAIN_ANCHOR_D3_BOUNDARY_MISSING",
        "COS_V1_STATUS_NOT_CERTIFIABLE",
        "v_truth<>7",
        "v_kinds<>34",
        "v_repositories<>14",
        "v_factory_count<>11",
        "v_cos_jobs<>2",
        "v_legacy_jobs<>0",
        "v_checkpoint_tail>50000",
        "external_chain_transaction_claimed",
        "D3_FOUNDER_DIRECTIVE",
    )
    for token in required:
        assert token in sql


def test_no_secret_material_is_committed() -> None:
    contents = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (MANIFEST, ARCHITECTURE, GUARD)
    )
    forbidden = (
        "sk-proj-",
        "SUPABASE_SERVICE_ROLE_KEY=",
        "MAILGUN_API_KEY=",
        "PAYPAL_CLIENT_SECRET=",
        "BEGIN PRIVATE KEY",
        "ctvisual_20260829",
        "ctseed_20260829",
        "readback_7b8e",
        "compact_43d",
    )
    for token in forbidden:
        assert token not in contents
