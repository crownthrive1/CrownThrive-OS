from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "penta" / "factory-continuous-build-heal-locticians.v1.json"
DOC = ROOT / "docs" / "architecture" / "factory-continuous-build-heal-locticians-v1.md"
GUARD = ROOT / "supabase" / "migrations" / "20260830070000_factory_continuous_build_heal_locticians_v1_guard.sql"


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_runtime_and_schedule_contract() -> None:
    runtime = manifest()["runtime"]
    assert runtime["cycle_function"] == "public.penta_factory_continuous_build_heal_cycle_v1"
    assert runtime["status_function"] == "public.penta_factory_continuous_build_heal_status_v1"
    assert runtime["jobname"] == "ct-penta-factory-continuous-build-heal-locticians-v1"
    assert runtime["schedule"] == "25,55 * * * *"
    assert runtime["auto_restore_registry"] == "integration_control.scheduler_desired_jobs_v2"


def test_all_factory_canary_contract() -> None:
    contract = manifest()["factory_contract"]
    assert contract["expected_factories"] == 16
    assert contract["production_ready_required"] is True
    assert contract["fresh_canary_max_age_hours"] == 7
    assert contract["canary_job"] == "ct-penta-factory-production-canary-v1"
    assert contract["canary_schedule"] == "17 */6 * * *"
    assert contract["required_canary_results"] == {
        "produced": 16,
        "self_attested": 16,
        "independently_certified": 16,
        "holds": 0,
    }


def test_locticians_editorial_flow_is_bounded_and_verified() -> None:
    editorial = manifest()["locticians_editorial"]
    assert editorial["heal_function"] == "public.locticians_editorial_heal_tick_v2"
    assert editorial["content_normalizer"] == "integration_control.locticians_editorial_content_normalize_v2"
    assert editorial["revision_authority"] == "integration_control.locticians_editorial_revision_authorize_v1"
    assert editorial["provider_user_id"] == 5
    assert editorial["per_cycle_limit"] == 1
    assert editorial["blind_retry"] is False
    assert "exact provider readback" in editorial["required_flow"]
    assert "DAIL receipt" in editorial["required_flow"]


def test_digital_product_clocks() -> None:
    digital = manifest()["locticians_digital_products"]
    assert digital["stripe_sync_job"] == {
        "jobname": "ct-stripe-payment-link-sync-v4",
        "schedule": "1 */6 * * *",
    }
    assert digital["checkout_verify_job"] == {
        "jobname": "ct-locticians-digital-products-checkout-v1",
        "schedule": "7 */2 * * *",
    }
    assert digital["orchestration_job"] == {
        "jobname": "ct-locticians-digital-products-orchestration-v1",
        "schedule": "9,19,29,39,49,59 * * * *",
    }
    assert digital["nurture_job"] == {
        "jobname": "ct-locticians-digital-products-nurture-v1",
        "schedule": "11,26,41,56 * * * *",
    }
    assert digital["unverified_product_policy"] == "hold_or_quarantine"
    assert digital["money_movement_by_control_plane"] is False


def test_state_semantics_do_not_hide_feed_holds() -> None:
    states = manifest()["cycle_states"]
    assert "all factories" in states["pass"]
    assert "Locticians" in states["pass"]
    assert "factories and canary pass" in states["partial"]
    assert "Locticians" in states["partial"]
    assert "factory" in states["hold"]
    assert "independent certification" in states["hold"]


def test_authority_is_fail_closed() -> None:
    assert manifest()["authority_boundaries"] == {
        "autonomous_ceiling": "D2",
        "D3": "human_reserved",
        "money_movement": False,
        "credential_export": False,
        "provider_delete": False,
        "automatic_top_level_persona_creation": False,
        "ambiguous_provider_mutation_retry": False,
    }


def test_guard_covers_load_bearing_controls() -> None:
    sql = GUARD.read_text(encoding="utf-8")
    for token in (
        "FACTORY_CONTINUOUS_HEAL_SCHEMA_INCOMPLETE",
        "FACTORY_CONTINUOUS_HEAL_RUNTIME_INCOMPLETE",
        "FACTORY_CONTINUOUS_HEAL_FLEET_NOT_READY",
        "FACTORY_CONTINUOUS_HEAL_CANARY_NOT_PASS",
        "FACTORY_CONTINUOUS_HEAL_LATEST_CYCLE_INVALID",
        "FACTORY_CONTINUOUS_HEAL_JOB_COUNT",
        "FACTORY_CONTINUOUS_HEAL_DESIRED_JOB_COUNT",
        "FACTORY_CONTINUOUS_HEAL_INVALID_PACKET_SIGNATURES",
        "FACTORY_CONTINUOUS_HEAL_D3_PACKET_VIOLATIONS",
        "FACTORY_CONTINUOUS_HEAL_AUTHORITY_BOUNDARY_DRIFT",
        "v_factory_count<>16",
        "v_ready_count<>16",
        "v_jobs<>6",
        "v_desired<>5",
    ):
        assert token in sql


def test_documentation_states_real_background_execution() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "runs inside CrownThrive COS/ThriveBase" in text
    assert "does not require an open ChatGPT session" in text
    assert "Every factory must" in text
    assert "exact provider readback" in text
    assert "D3: human-reserved" in text


def test_no_secret_material_is_committed() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in (MANIFEST, DOC, GUARD))
    for token in (
        "sk-proj-",
        "BEGIN PRIVATE KEY",
        "SUPABASE_SERVICE_ROLE_KEY=",
        "GOOGLE_REFRESH_TOKEN=",
    ):
        assert token not in text
