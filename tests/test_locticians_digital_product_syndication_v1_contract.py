from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "penta" / "locticians-digital-product-syndication.v1.json"
GUARD = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260829070000_locticians_digital_product_syndication_v1_guard.sql"
)
SYNC = ROOT / "supabase" / "functions" / "stripe-payment-link-sync-v4" / "index.ts"


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_brilliant_directories_digital_product_binding() -> None:
    provider = manifest()["provider"]
    assert provider["publisher_user_id"] == 5
    assert provider["data_id"] == 73
    assert provider["data_type"] == 4
    assert provider["surface_key"] == "digital_products"
    assert provider["public_path"] == "/digital-products"
    assert provider["required_provider_fields"] == ["post_url", "post_promo"]
    assert provider["exact_read_after_write_required"] is True
    assert provider["delete_authority"] == "D3_HUMAN_RESERVED"


def test_payment_authority_is_single_and_read_only() -> None:
    payment = manifest()["payment"]
    assert payment["active_authority"] == "verified external Stripe Payment Links"
    assert payment["stripe_account_id"] == "acct_1MENDxCJFUeGxc8S"
    assert payment["payment_link_inventory_records"] == 32
    assert payment["active_payment_links"] == 28
    assert payment["provider_sync_mode"] == "read_only"
    assert payment["payment_link_mutation"] is False
    assert payment["product_mutation"] is False
    assert payment["price_mutation"] is False
    assert payment["money_movement"] is False
    assert payment["raw_secret_export"] is False
    assert payment["bd_native_payment_state"] == "documented_ui_only_api_unverified"
    assert payment["parallel_payment_authority"] is False


def test_daily_schedule_and_release_policy() -> None:
    policy = manifest()["listing_policy"]
    assert policy["daily_listing_limit"] == 10
    assert policy["timezone"] == "America/New_York"
    assert policy["publication_start_hour"] == 8
    assert policy["publication_end_hour"] == 17
    assert policy["homepage_features_per_day"] == 2
    assert policy["checkout_reverify_hours"] == 6
    assert policy["listing_refresh_days"] == 30
    assert policy["nurture_after_hours"] == [24, 168, 336, 720]
    assert policy["unverified_products"] == "hold"
    assert policy["provider_mismatch"] == "quarantine and unpublished containment"
    assert policy["automatic_blind_retry"] is False


def test_initial_batch_is_ten_exact_provider_records() -> None:
    batch = manifest()["initial_batch"]
    listings = batch["listings"]
    assert batch["source_count"] == 10
    assert batch["provider_bound"] == 10
    assert batch["independent_audit_approved"] == 10
    assert batch["release_contract_passed"] == 10
    assert batch["exact_content_hash_matches"] == 10
    assert batch["exact_required_field_readbacks"] == 10
    assert batch["held"] == 0
    assert batch["quarantined"] == 0
    assert len(listings) == 10
    assert [item["provider_post_id"] for item in listings] == list(range(4202, 4212))
    assert [item["sequence"] for item in listings] == list(range(1, 11))
    assert [item["publish_at_et"][-8:] for item in listings] == [
        "08:00:00",
        "09:00:00",
        "10:00:00",
        "11:00:00",
        "12:00:00",
        "13:00:00",
        "14:00:00",
        "15:00:00",
        "16:00:00",
        "17:00:00",
    ]
    assert sum(bool(item["homepage_feature"]) for item in listings) == 2
    assert all(item["stripe_payment_link_id"].startswith("plink_") for item in listings)
    assert all(item["stripe_product_id"].startswith("prod_") for item in listings)
    assert all(item["stripe_price_id"].startswith("price_") for item in listings)


def test_nurture_is_six_actions_per_listing_and_opt_in_safe() -> None:
    nurture = manifest()["nurture"]
    assert nurture["actions"] == 60
    assert nurture["actions_per_listing"] == 6
    assert nurture["price_and_availability"] == "every six hours"
    assert nurture["newsletter_syndication"].startswith("24 hours")
    assert nurture["social_distribution"].startswith("seven days")
    assert nurture["conversion_refresh"].startswith("fourteen days")
    assert nurture["seo_refresh"].startswith("thirty days")
    assert nurture["direct_buyer_contact_without_opt_in"] is False


def test_mesh_inventory_fails_closed() -> None:
    mesh = manifest()["inventory_mesh"]
    assert mesh["catalog_candidates_evaluated"] == 1042
    assert mesh["new_eligible_candidates"] == 0
    assert mesh["blocked_candidates"] == 1042
    assert "quality" in mesh["blocking_policy"]
    assert mesh["automatic_source_certification_work"] is True


def test_runtime_and_clocks_are_explicit() -> None:
    runtime = manifest()["runtime"]
    assert runtime["stripe_payment_link_sync"] == "stripe-payment-link-sync-v4"
    assert runtime["checkout_verify"] == "public.locticians_digital_product_checkout_verify_tick_v1"
    assert runtime["daily_schedule"] == "public.locticians_digital_product_schedule_batch_v1"
    assert runtime["orchestrator"] == "public.locticians_digital_product_orchestration_tick_v1"
    assert runtime["audit"] == "public.locticians_digital_product_audit_tick_v1"
    assert runtime["publish"] == "public.locticians_digital_product_publish_tick_v1"
    assert runtime["nurture"] == "public.locticians_digital_product_nurture_tick_v1"
    assert runtime["status"] == "public.locticians_digital_product_status_v1"
    assert runtime["provider_create_or_reconcile"] == (
        "integration_control.locticians_universal_provider_create_or_reconcile_v4"
    )

    clocks = {item["job"]: item["schedule"] for item in manifest()["canonical_clocks"]}
    assert clocks == {
        "ct-stripe-payment-link-sync-v4": "1 */6 * * *",
        "ct-locticians-digital-products-checkout-v1": "7 */6 * * *",
        "ct-locticians-digital-products-orchestration-v1": "9,19,29,39,49,59 * * * *",
        "ct-locticians-digital-products-nurture-v1": "11,26,41,56 * * * *",
    }


def test_agent_mesh_is_bounded_to_d2() -> None:
    mesh = manifest()["agent_mesh"]
    assert mesh["specialized_agents"] == 4
    assert mesh["capabilities"] == 9
    assert mesh["playbooks"] == 7
    assert set(mesh["agents"]) == {
        "ct.pentamarketer.agent.product-syndicator-v1",
        "ct.pentamarketer.agent.checkout-monitor-v1",
        "ct.pentamarketer.agent.digital-product-nurture-v1",
        "ct.pentamarketer.agent.digital-product-certifier-v1",
    }
    assert mesh["maximum_autonomous_authority"] == "D2"
    assert mesh["d3_remains_fail_closed"] is True


def test_native_bd_payment_is_not_falsely_activated() -> None:
    research = manifest()["provider_research"]
    assert research["native_digital_products_documented"] is True
    assert research["documented_payment_types"] == [
        "free",
        "one_time",
        "recurring",
        "custom_donation",
    ]
    assert research["protected_thank_you_delivery_documented"] is True
    assert research["form_manager_documented"] is True
    assert research["checkout_form_fields_gateway_specific"] is True
    assert research["default_checkout_fields_must_be_preserved"] is True
    assert research["arbitrary_form_iframe_or_script_injection"] is False
    assert research["native_payment_api_fields_verified"] is False


def test_payment_link_sync_has_no_write_or_secret_export_path() -> None:
    source = SYNC.read_text(encoding="utf-8")
    assert 'vault("stripe_connect_live_secret_key_v1")' in source
    assert 'vault("stripe_production_control_gateway_secret_v1")' in source
    assert "GET_required" not in source
    assert "/v1/payment_links?" in source
    assert "/line_items?" in source
    assert 'payment_link_mutation: false' in source
    assert 'product_mutation: false' in source
    assert 'price_mutation: false' in source
    assert 'money_movement: false' in source
    assert 'raw_secret_export: false' in source
    assert "sk_live_" in source
    assert "sk_live_51" not in source
    assert "plink_1U9J" not in source
    assert "buy.stripe.com" not in source
    assert "POST_required" in source


def test_convergence_guard_covers_load_bearing_controls() -> None:
    sql = GUARD.read_text(encoding="utf-8")
    tokens = (
        "LOCTICIANS_DIGITAL_PRODUCT_POLICY_DRIFT",
        "LOCTICIANS_DIGITAL_PRODUCT_PROVIDER_CONTRACT_DRIFT",
        "LOCTICIANS_DIGITAL_PRODUCT_VERIFIED_SOURCE_COUNT",
        "LOCTICIANS_DIGITAL_PRODUCT_DAILY_SCHEDULE_DRIFT",
        "LOCTICIANS_DIGITAL_PRODUCT_EXACT_READBACK_COUNT",
        "LOCTICIANS_DIGITAL_PRODUCT_REQUIRED_FIELD_READBACK_COUNT",
        "LOCTICIANS_DIGITAL_PRODUCT_PROVIDER_POST_ID_DRIFT",
        "LOCTICIANS_DIGITAL_PRODUCT_NURTURE_ACTION_COUNT",
        "STRIPE_PAYMENT_LINK_COMPLETE_SYNC_MISSING",
        "STRIPE_PAYMENT_LINK_SNAPSHOT_COUNTS",
        "LOCTICIANS_DIGITAL_PRODUCT_MESH_CANDIDATE_COUNTS",
        "LOCTICIANS_DIGITAL_PRODUCT_CANONICAL_JOB_COUNT",
        "LOCTICIANS_DIGITAL_PRODUCT_AGENT_COUNT",
        "LOCTICIANS_DIGITAL_PRODUCT_CAPABILITY_COUNT",
        "LOCTICIANS_DIGITAL_PRODUCT_PLAYBOOK_COUNT",
        "BD_NATIVE_PAYMENT_ACTIVATED_WITHOUT_CERTIFICATION",
        "array[4202,4203,4204,4205,4206,4207,4208,4209,4210,4211]",
        "v_nurture<>60",
        "v_snapshot_records<>32",
        "v_snapshot_active<>28",
        "v_candidates<>1042",
        "v_blocked<>1042",
    )
    for token in tokens:
        assert token in sql


def test_certification_summary_is_consistent() -> None:
    certification = manifest()["certification"]
    assert certification == {
        "status_function": "public.locticians_digital_product_status_v1",
        "status": "production_active",
        "sources": 10,
        "listings": 10,
        "provider_bound": 10,
        "scheduled_or_live_verified": 10,
        "held_or_quarantined": 0,
        "nurture_actions": 60,
        "stripe_sync_records": 32,
        "stripe_sync_active_records": 28,
        "stripe_sync_payload_sha256": "e0025953cc78db5bd64bfc01ce4f0b6f970db1a76526de9cacf8d4a5f0214518",
    }


def test_no_runtime_credentials_are_committed() -> None:
    contents = "\n".join(
        path.read_text(encoding="utf-8") for path in (MANIFEST, GUARD, SYNC)
    )
    forbidden = (
        "ctvisual_20260829",
        "ctseed_20260829",
        "cteditorial_20260829",
        "readback_7b8e",
        "compact_43d",
        "sk-proj-",
        "whsec_",
        "rk_live_",
    )
    for token in forbidden:
        assert token not in contents
