import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data" / "penta" / "phase35-gap-closure.20260829.v2.json"


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_pentaself_repairs_are_monotonic_without_blind_overwrite() -> None:
    doc = load_contract()
    permanence = doc["verified_repairs"]["pentaself_permanence"]
    assert permanence["state"] == "production"
    assert permanence["successful_repairs_monotonic"] is True
    assert permanence["unknown_newer_change_policy"] == "HOLD_NOT_OVERWRITE"
    assert set(permanence["redundant_guardians"]) == {
        "ct-penta-self-permanence-v2",
        "ct-penta-self-permanence-watch-v2",
    }


def test_payment_evidence_does_not_manufacture_money_authority() -> None:
    doc = load_contract()
    stripe = doc["verified_repairs"]["stripe"]
    paypal = doc["verified_repairs"]["paypal"]
    assert stripe["thrivetickets_webhook"] == "resolved"
    assert stripe["sermon_toolkit_webhook"] == "resolved"
    assert stripe["signed_provider_events_received"] is True
    assert stripe["synthetic_success"] is False
    assert stripe["money_movement"] is False
    assert paypal["provider_event_evidence"] == "verified"
    assert paypal["webhook_signature_claimed"] is False
    assert paypal["synthetic_receipts"] == 0
    assert paypal["money_movement"] is False


def test_pentacensus_is_production_observer_not_execution_authority() -> None:
    census = load_contract()["verified_repairs"]["penta_census"]
    assert census["runtime_maturity"] == "production_observer"
    assert census["execution_eligible"] is False
    assert census["provider_write_authority"] is False
    assert census["d3_auto"] is False
    assert census["money_movement"] is False


def test_bd_failover_is_warm_but_never_rate_limit_key_hops() -> None:
    bd = load_contract()["verified_repairs"]["brilliant_directories"]
    assert bd["primary"] == "WARM_PRIMARY"
    assert bd["independent_provider_keys"] == [13, 14]
    assert bd["independent_vault_aliases_bound"] == 2
    assert bd["independent_standbys_ready"] == 2
    assert bd["sitewide_quota_shared"] is True
    assert bd["switch_on_429"] is False
    assert bd["raw_key_material_in_repository"] is False


def test_only_human_reserved_actions_remain() -> None:
    doc = load_contract()
    actions = {item["key"]: item["authority"] for item in doc["remaining_human_actions"]}
    assert actions == {
        "crownthrive.tech_registrant_email_verification": "D3_HUMAN_RESERVED",
        "radio_co_live_broadcast_credential_rotation": "provider_admin_human_action",
    }
    safety = doc["global_safety"]
    assert safety["d3_bypass"] is False
    assert safety["credential_values_in_repository"] is False
    assert safety["money_movement_enabled"] is False
    assert safety["checkout_activation_enabled"] is False
    assert safety["provider_limit_bypass"] is False
    assert safety["unknown_newer_runtime_overwrite"] is False
    assert safety["historical_evidence_deleted"] is False
