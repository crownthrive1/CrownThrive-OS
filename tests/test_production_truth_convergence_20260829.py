from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"


def read(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def test_penta_protocol_replay_window_is_paired_and_restored() -> None:
    pre = read("20260829032450_penta_protocol_registry_replay_preflight_v3.sql")
    post = read("20260829032550_penta_protocol_registry_replay_restore_v3.sql")
    assert "last_verified_at drop not null" in pre.lower()
    assert "last_verified_at set not null" in post.lower()
    assert "where last_verified_at is null" in post.lower()
    assert "raise exception 'penta_system_registry_last_verified_at_restore_failed'" in post.lower()


def test_runtime_truth_sweep_is_fail_closed_and_monotonic() -> None:
    sql = read("20260829043200_penta_runtime_truth_and_crawler_echo_guard_v2.sql")
    lowered = sql.lower()
    assert "penta_registry_runtime_reference_sweep_v1" in lowered
    assert "penta_runtime_reference_check_v1" in lowered
    assert "aggregate_fail_closed_projection_not_root_incident" in lowered
    assert "root_failures_remain_independently_owned" in lowered
    assert "ct-penta-runtime-reference-sweep-v1" in lowered
    assert "ct-penta-crawler-roam-v3" in lowered
    assert "ct-pentas-mesh-router-v3" in lowered
    assert "scheduler_desired_job_upsert_v2" in lowered
    assert "'rollback_policy','monotonic'" in lowered
    assert "'provider_write',false" in lowered
    assert "'d3_execution',false" in lowered
    assert "'authority_created',false" in lowered
    assert "revoke all on function public.penta_registry_runtime_reference_sweep_v1" in lowered


def test_stripe_crosswalk_uses_one_canonical_platform_alias() -> None:
    sql = read("20260829043000_stripe_catalog_crosswalk_canonical_credential_v3.sql")
    lowered = sql.lower()
    assert "name=''stripe_server_api_key''" in lowered
    assert "ct-stripe-catalog-crosswalk-refresh-v3" in lowered
    assert "'money_movement',false" in lowered
    assert "'checkout_activation',false" in lowered
    assert "'provider_write','read_only_catalog'" in lowered
    assert "stripe_catalog_crosswalk_refresh_v2" in lowered


def test_pentamarketer_projection_is_event_ledger_authoritative() -> None:
    sql = read("20260829043100_pentamarketer_event_derived_projection_v2.sql")
    lowered = sql.lower()
    assert "penta_marketer_campaign_projection_v2" in lowered
    assert "append_only_event_ledger" in lowered
    assert "event_ledger_authoritative" in lowered
    assert "mutable_summary_authority" in lowered
    assert "ct-pentamarketer-event-projection-v2" in lowered
    assert "penta marketer" not in ""  # keep test file deterministic and import-only


def test_no_secret_values_are_committed_by_truth_convergence() -> None:
    names = [
        "20260829043000_stripe_catalog_crosswalk_canonical_credential_v3.sql",
        "20260829043100_pentamarketer_event_derived_projection_v2.sql",
        "20260829043200_penta_runtime_truth_and_crawler_echo_guard_v2.sql",
    ]
    content = "\n".join(read(name) for name in names)
    assert "sk_live_" not in content
    assert "rk_live_" not in content
    assert "api_token" not in content
    assert "decrypted_secret as" not in content.lower()
