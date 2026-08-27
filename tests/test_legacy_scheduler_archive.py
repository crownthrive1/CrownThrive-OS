from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_article_is_historical_only() -> None:
    text = (ROOT / "knowledge/legacy-abcds-scheduler-scaffolding-archive.mdx").read_text()
    assert "RETIRED_SCHEDULING_SCAFFOLDING" in text
    assert "Authority:** none" in text
    assert "Do not reactivate" in text
    assert "reactivation_allowed: false" in text


def test_archive_record_has_no_authority() -> None:
    data = json.loads(
        (ROOT / "governance/archive/legacy-abcds-scheduler-scaffolding.v1.json").read_text()
    )
    assert data["execution_authority"] == "none"
    assert data["implementation_authority"] == "none"
    assert data["reactivation_prohibited"] is True
    assert data["drive_destination"]["provider_write_state"] == "VERIFIED"


def test_migration_is_append_preserving_and_bounded() -> None:
    sql = (
        ROOT
        / "supabase/migrations/20260827164000_archive_legacy_abcds_scheduler_scaffolding_v1.sql"
    ).read_text().lower()

    for forbidden in ("delete from", "truncate ", "drop table", "force push"):
        assert forbidden not in sql

    assert "execution_state = 'retired'" in sql
    assert "external_task_id = null" in sql
    assert "historical_reference_only" in sql
    assert "drop function chlom_runtime.agent_a_emergency_portfolio_cycle_v2" in sql
    assert "drop function chlom_runtime.agent_a_portfolio_preflight" in sql
    assert "drop function chlom_runtime.agent_a_start_portfolio_cycle" in sql
    assert "ct.schedule.external-evidence-relay.hourly.v1" in sql
    assert "archive_drive_package_file_id" in sql


def test_validation_script_checks_zero_live_paths() -> None:
    sql = (ROOT / "scripts/validate-legacy-abcds-scheduler-archive.sql").read_text().lower()
    assert "legacy_functions_remaining" in sql
    assert "schedule_rows_with_provider_task_id" in sql
    assert "schedule_rows_with_parent_relay_alias" in sql
    assert "canonical_relay_active" in sql
    assert "archive_evidence_present" in sql


def test_workflow_has_no_recurring_clock() -> None:
    workflow = (
        ROOT / ".github/workflows/legacy-scheduler-scaffolding-recurrence-guard.yml"
    ).read_text().lower()
    assert "\n  schedule:" not in workflow
    assert "pull_request:" in workflow
    assert "branches: [main]" in workflow
    assert "verify_legacy_scheduler_archive.py" in workflow


def test_historical_page_is_removed_from_current_automation_navigation() -> None:
    docs = json.loads((ROOT / "docs.json").read_text())
    serialized = json.dumps(docs)
    assert "knowledge/legacy-abcds-scheduler-scaffolding-archive" in serialized
