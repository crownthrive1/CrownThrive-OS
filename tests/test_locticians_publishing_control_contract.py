from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260828232000_pentamarketer_publish_reconcile_candidate_gate_v1.sql"
)
MANIFEST = ROOT / "data" / "penta" / "locticians-publishing-control.v1.json"


def test_publisher_tick_requires_an_eligible_draft() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function crm.penta_marketer_growth_factory_seed_v1()" in sql
    assert "if current_user not in ('postgres','service_role')" in sql
    assert "select count(*)::integer into v_publish_candidates" in sql
    assert "if v_publish_candidates>0 then" in sql
    assert "'eligible_candidate_count',v_publish_candidates" in sql
    assert "'no_eligible_publication_candidate'" in sql
    assert "'provider_write_executed',false" in sql

    gate_position = sql.index("if v_publish_candidates>0 then")
    publisher_position = sql.index("'locticians:publish-reconcile:'||v_ten_min")
    assert gate_position < publisher_position


def test_image_rights_and_authority_boundaries_are_fail_closed() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "d.source_basis->>'image_rights_state'='verified'" in sql
    assert "'image_rights_rule','required_when_image_present'" in sql
    assert "'provider_write_authority','bridge_only'" in sql
    assert "'d3_auto',false" in sql
    assert "delete from" not in sql.lower()


def test_production_receipt_matches_the_certified_provider_binding() -> None:
    receipt = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert receipt["state"] == "production_active_provider_readback_verified"
    assert receipt["provider"]["publisher_principal"] == {
        "user_id": 5,
        "state": "article_canary_verified",
    }
    assert receipt["provider"]["post_type"]["data_id"] == 14
    assert receipt["provider"]["post_type"]["data_type"] == 20
    assert receipt["route"]["route_state"] == "active"
    assert receipt["route"]["auto_publish_if_release_pass"] is True
    assert receipt["route"]["read_after_write_required"] is True
    assert receipt["route"]["rollback_reference_required"] is True
    assert receipt["authority"]["delete_authority"] == "D3_HUMAN_RESERVED"


def test_canary_and_production_publication_evidence_are_distinct() -> None:
    receipt = json.loads(MANIFEST.read_text(encoding="utf-8"))
    canary = receipt["provider_canary"]
    production = receipt["production_publication"]

    assert canary["post_id"] == 4175
    assert canary["post_status"] == 0
    assert canary["visibility"] == "draft_unpublished"
    assert canary["delete_used"] is False

    assert production["post_id"] == 4176
    assert production["post_status"] == 1
    assert production["exact_api_readback_pass"] is True
    assert production["image_present"] is False
    assert production["image_rights_state"] == "not_applicable_image_absent"
    assert production["provider_content_sha256"] == production["source_content_sha256"]


def test_persona_and_factory_certification_are_complete() -> None:
    receipt = json.loads(MANIFEST.read_text(encoding="utf-8"))
    personas = receipt["persona_certification"]
    factory = receipt["factory_reconciliation"]

    assert personas["expected_personas"] == 39
    assert personas["observed_personas"] == 39
    assert personas["total_tests"] == 235
    assert personas["passed_tests"] == 235
    assert personas["held_tests"] == 0
    assert personas["failed_tests"] == 0
    assert personas["overall_state"] == "pass"

    assert factory["open_publisher_ticks_after_reconciliation"] == 0
    assert factory["publisher_tick_created_without_candidate"] is False
    assert factory["eligible_publish_candidates_at_final_readback"] == 0
    assert factory["no_candidate_behavior"] == "recorded_noop_and_stale_tick_cancellation"


def test_receipt_contains_no_secret_material_or_false_indexing_claim() -> None:
    raw = MANIFEST.read_text(encoding="utf-8")
    receipt = json.loads(raw)

    assert receipt["provider"]["credential_material_in_record"] is False
    assert receipt["source_authority"]["secret_material_in_repository"] is False
    assert receipt["public_projection"]["search_indexing_claimed"] is False
    assert "sk-" not in raw
    assert '"api_key"' not in raw
