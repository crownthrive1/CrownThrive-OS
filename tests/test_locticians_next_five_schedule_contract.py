from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "penta" / "locticians-next-five-schedule.20260829.v1.json"
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260829011000_locticians_article_scheduler_convergence_guard_v1.sql"
)


def _load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_identity_and_provider_binding() -> None:
    data = _load()
    assert data["contract_id"] == "ct.pentamarketer.locticians.next-five-schedule.v1"
    assert data["state"] == "production_scheduled_provider_readback_verified"
    assert data["batch_ref"] == "locticians.next5.2026-08-29.v1"
    assert data["provider"]["publisher_principal"]["user_id"] == 5
    assert data["provider"]["post_type"]["data_id"] == 14
    assert data["provider"]["post_type"]["data_type"] == 20
    assert data["provider"]["date_encoding"] == "YYYYMMDDHHmmss"
    assert data["provider"]["delete_authority"] == "D3_HUMAN_RESERVED"
    assert data["provider"]["credential_material_in_record"] is False


def test_all_39_personas_are_certified() -> None:
    cert = _load()["persona_certification"]
    assert cert == {
        "run_id": "ff33c1cd-8094-4634-ae54-82e763881e08",
        "expected_personas": 39,
        "observed_personas": 39,
        "total_tests": 235,
        "passed_tests": 235,
        "held_tests": 0,
        "failed_tests": 0,
        "overall_state": "pass",
    }


def test_next_five_are_unique_scheduled_and_read_back() -> None:
    schedule = _load()["schedule"]
    assert len(schedule) == 5
    assert [item["sequence_no"] for item in schedule] == [1, 2, 3, 4, 5]
    assert [item["provider_post_id"] for item in schedule] == [4177, 4178, 4179, 4180, 4181]
    assert len({item["schedule_id"] for item in schedule}) == 5
    assert len({item["title"] for item in schedule}) == 5
    assert len({item["provider_filename"] for item in schedule}) == 5

    expected_dates = [
        "2026-08-29T10:00:00-04:00",
        "2026-08-30T10:00:00-04:00",
        "2026-08-31T10:00:00-04:00",
        "2026-09-01T10:00:00-04:00",
        "2026-09-02T10:00:00-04:00",
    ]
    assert [item["scheduled_for_et"] for item in schedule] == expected_dates

    for item in schedule:
        assert item["state"] == "scheduled"
        assert item["audit_decision"] == "approve"
        assert item["exact_readback_pass"] is True
        assert item["content_sha256"] == item["provider_content_sha256"]
        assert len(item["content_sha256"]) == 64
        int(item["content_sha256"], 16)
        assert datetime.fromisoformat(item["scheduled_for_et"]).utcoffset() is not None
        assert item["provider_filename"].startswith("blog/")


def test_simulation_and_automation_are_fail_closed() -> None:
    data = _load()
    simulation = data["simulation"]
    assert simulation["local_simulation"] == "pass"
    assert simulation["local_duplicate_count"] == 0
    assert simulation["external_provider_duplicate_checks"] == 5
    assert simulation["external_provider_duplicate_checks_passed"] == 5
    assert simulation["second_provider_readback_passed"] == 5
    assert simulation["second_provider_readback_failed"] == 0
    assert simulation["all_content_hashes_match"] is True
    assert simulation["all_provider_dates_match"] is True
    assert simulation["all_provider_identifiers_match"] is True

    governance = data["governance"]
    assert governance["automatic_retry"] is False
    assert governance["ambiguous_outcome_action"] == "quarantine"
    assert governance["image_rights_rule"] == "required_when_image_present"
    assert governance["this_batch_image_state"] == "not_applicable_image_absent"
    assert governance["maximum_autonomous_risk_class"] == "D2"


def test_dispatch_and_live_verifier_crons_are_declared() -> None:
    automation = _load()["automation"]
    assert automation["canonical_runtime"] == "ThriveBase direct-provider scheduler"
    assert automation["dispatch_cron"] == {
        "job_id": 228,
        "job_name": "ct-locticians-article-schedule-dispatch-v1",
        "schedule": "5,15,25,35,45,55 * * * *",
        "active": True,
    }
    assert automation["live_verifier_cron"] == {
        "job_id": 227,
        "job_name": "ct-locticians-article-live-verifier-v1",
        "schedule": "*/10 * * * *",
        "active": True,
    }
    retired = automation["retired_edge_function"]
    assert retired["state"] == "retired_non_mutating_410"
    assert len(retired["sha256"]) == 64


def test_convergence_guard_covers_critical_boundaries() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    required = (
        "user_id}'<>'5'",
        "data_id}'<>'14'",
        "data_type}'<>'20'",
        "LOCTICIANS_NEXT_FIVE_PROVIDER_READBACK_DRIFT",
        "ct-locticians-article-schedule-dispatch-v1",
        "ct-locticians-article-live-verifier-v1",
        "provider_post_id not between 4177 and 4181",
        "content_sha256<>provider_content_sha256",
        "image_rights_state<>'not_applicable_image_absent'",
    )
    for token in required:
        assert token in sql

    assert "locticians_brilliant_directories_api_key" not in _load().get("credential", {})
    assert hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
