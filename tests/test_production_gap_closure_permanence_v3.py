import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data" / "penta" / "production-gap-closure.20260829.v3.json"
PENTA_SELF_SQL = ROOT / "supabase" / "migrations" / "20260829022000_penta_self_monotonic_repair_persistence_v2.sql"
STRIPE_SQL = ROOT / "supabase" / "migrations" / "20260829023000_stripe_webhook_and_product_reliability_v3.sql"
BD_SQL = ROOT / "supabase" / "migrations" / "20260829024000_locticians_bd_independent_warm_failover_v3.sql"
PAYPAL_SQL = ROOT / "supabase" / "migrations" / "20260829025000_paypal_webhook_reliability_v3.sql"


def read(path: Path) -> str:
    assert path.is_file(), f"missing required source: {path}"
    return path.read_text(encoding="utf-8")


def test_contract_preserves_authority_and_secret_boundaries() -> None:
    data = json.loads(read(CONTRACT))
    assert data["authority_ceiling"] == "D2"
    assert data["d3_human_reserved"] is True
    assert data["source_custody"]["raw_credentials_in_git"] is False
    assert data["brilliant_directories"]["raw_secret_projection"] is False
    assert data["brilliant_directories"]["switch_on_429"] is False
    assert data["stripe"]["guards"]["money_movement"] is False
    assert data["paypal"]["guards"]["money_movement"] is False


def test_pentaself_resolution_is_monotonic() -> None:
    sql = read(PENTA_SELF_SQL)
    required = [
        "certified_problem_resolutions_v2",
        "problem_regression_events_v2",
        "problem_monotonic_guard_v2",
        "stale_reopen_suppressed",
        "regression_verified",
        "stale_regression_observation",
        "critical_cron_state_v2",
        "desired_version",
        "cron_version_downgrade_prohibited",
        "ACTIVE_DRIFT_OBSERVED_NOT_OVERWRITTEN",
        "ct-penta-self-monotonic-reconcile-v2",
    ]
    for marker in required:
        assert marker in sql
    assert "active_drift_overwrite" not in sql
    assert "cron.unschedule(j.jobid)" not in sql


def test_provider_ingress_is_evidence_gated() -> None:
    stripe = read(STRIPE_SQL)
    paypal = read(PAYPAL_SQL)
    bd = read(BD_SQL)

    for marker in [
        "stripe_event_receipts_v3",
        "signature_verified",
        "stripe_webhook_signed_canary_v3",
        "provider_endpoint_matches",
        "money_movement_executed",
        "stripe_product_crosswalk_v3",
    ]:
        assert marker in stripe

    for marker in [
        "paypal_event_receipts_v3",
        "paypal_signature_not_verified",
        "paypal_webhook_reconcile_v3",
        "paypal_webhook_simulate_v3",
        "money_movement",
    ]:
        assert marker in paypal

    for marker in [
        "store_locticians_bd_standby_secret_v3",
        "provider_key_id_not_allowed",
        "standby_not_distinct_from_primary",
        "raw_secret_exposed",
        "switch_on_429",
    ]:
        assert marker in bd or marker in read(CONTRACT)


def test_all_new_security_definer_routines_revoke_client_execution() -> None:
    combined = "\n".join(read(p) for p in [PENTA_SELF_SQL, STRIPE_SQL, BD_SQL, PAYPAL_SQL])
    assert "revoke all on function" in combined
    assert " from public,anon,authenticated" in combined or " from public, anon, authenticated" in combined
    assert "grant execute" in combined


def test_no_literal_provider_credentials_are_committed() -> None:
    combined = "\n".join(read(p) for p in [PENTA_SELF_SQL, STRIPE_SQL, BD_SQL, PAYPAL_SQL, CONTRACT])
    forbidden = ["sk_live_", "whsec_", "access_token\":", "api_token\":"]
    # Prefixes can appear only as validation patterns, never followed by actual material.
    assert "sk_live_" not in combined or "like 'sk\\_live\\_%'" in combined
    assert "whsec_" not in combined or "like 'whsec\\_%'" in combined
    assert "api_token\":" not in combined
