from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_guard_module():
    path = ROOT / "scripts/verify_legacy_scheduler_archive.py"
    spec = importlib.util.spec_from_file_location("legacy_scheduler_guard", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_guard_accepts_plural_agents_and_explicit_prohibitions(tmp_path: Path) -> None:
    guard = _load_guard_module()
    page = tmp_path / "safe.mdx"
    page.write_text(
        "These agents may be invoked by the canonical relay clock.\n"
        "| Agent A | hourly :00 | no standalone clock |\n"
        "The external relay is not a replacement one-agent-one-clock scheduler.\n"
        "Do not create separate Agent A/B/C/D/S clocks.\n",
        encoding="utf-8",
    )
    assert guard.scan(tmp_path, None) == []


def test_guard_rejects_live_legacy_clock_reactivation(tmp_path: Path) -> None:
    guard = _load_guard_module()
    page = tmp_path / "unsafe.mdx"
    page.write_text(
        "Enable Agent A as an hourly external scheduler clock for production.\n",
        encoding="utf-8",
    )
    violations = guard.scan(tmp_path, None)
    assert len(violations) == 1
    assert violations[0]["kind"] == "legacy_scheduler_semantics"
