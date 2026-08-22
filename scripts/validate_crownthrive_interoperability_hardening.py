#!/usr/bin/env python3
"""Validate the CrownThrive Interoperability Fabric v1.1 hardening checkpoint."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/crownthrive-interoperability-fabric.v1.1.json"
CHANGELOG = ROOT / "changelog/crownthrive-interoperability-hardening-2026-08-22.mdx"
SDK_VALIDATOR = ROOT / "scripts/validate_interop_adapter_sdk.py"
FABRIC_VALIDATOR = ROOT / "scripts/validate_crownthrive_interoperability_fabric.py"


def main() -> None:
    assert MANIFEST.is_file()
    assert CHANGELOG.is_file()
    assert SDK_VALIDATOR.is_file()
    assert FABRIC_VALIDATOR.is_file()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.1.0"
    assert data["plugin_id"] == "ct.plugin.crownthrive-interoperability-fabric"
    assert data["plugin_version"] == "1.0.0"
    assert data["state"] == "CONTROLLED_TEST_GOVERNED_HOLD"
    assert data["archetype"] == "tool_only"
    assert data["public_submission_state"] == "not_submitted"
    assert data["authenticated_external_canary"] == "pending"

    for key in (
        "provider_write_enabled",
        "checkout_enabled",
        "entitlement_active",
        "operative_license",
        "D3_auto",
        "sovereign_vote_effect",
        "direct_main_merge",
    ):
        assert data[key] is False, key

    counts = data["counts"]
    expected = {
        "plugin_packages": 21,
        "capabilities": 39,
        "canonical_contracts": 13,
        "bindings": 42,
        "routes": 15,
        "agents": 6,
        "protected_algorithms": 2,
        "independent_test_receipts": 12,
        "pricing_candidates": 10,
        "future_gap_issues": 8,
    }
    for key, value in expected.items():
        assert counts[key] >= value, (key, counts[key], value)

    hardening = data["hardening_completed"]
    assert hardening["adapter_sdk"]["state"] == "verified"
    assert hardening["adapter_sdk"]["provider_write_enabled"] is False
    assert hardening["adapter_sdk"]["raw_credentials_allowed"] is False
    assert hardening["contract_drift_detector"]["state"] == "verified"
    assert hardening["contract_drift_detector"]["observations"] == 117
    assert hardening["contract_drift_detector"]["fail"] == 0
    assert hardening["route_observability"]["state"] == "verified"
    assert hardening["route_observability"]["routes"] == 15
    assert hardening["route_observability"]["fail"] == 0
    assert hardening["route_observability"]["execution_performed"] is False
    assert hardening["route_observability"]["provider_write_performed"] is False
    assert hardening["database_subagent_runtime"]["agents"] == 6
    assert hardening["database_subagent_runtime"]["external_scheduler_slots_added"] == 0
    assert hardening["database_subagent_runtime"]["first_cron_fired_receipt"] == "pending"

    budget = hardening["request_budget_guard"]["semantics"]
    assert budget["-1"] == "unlimited_local_ceiling"
    assert budget["0"] == "disabled"
    assert budget["positive"] == "local_monthly_ceiling"
    assert budget["null"] == "unresolved_fail_closed"
    assert budget["provider_limits_billing_quotas_separate"] is True
    assert hardening["request_budget_guard"]["locticians_local_limit"] == 20000
    assert hardening["request_budget_guard"]["adserver_included_threshold"] == 3000000
    assert hardening["request_budget_guard"]["adserver_hard_stop"] is False

    positive = data["validated_examples"]["squarespace_to_crownlytics_product_catalog"]
    assert positive["compatibility_score"] >= 85
    assert positive["route_score"] >= 85
    assert positive["provider_write_performed"] is False
    negative = data["validated_examples"]["adluxe_to_crownlytics_campaign"]
    assert negative["route_state"] == "hold"
    assert set(negative["required_blockers"]) == {"source_binding_hold", "route_hold"}

    issue_state = data["current_issue_state"]
    assert issue_state["contract_drift_detector"] == "resolved"
    assert issue_state["route_observability"] == "resolved"
    assert issue_state["adapter_sdk"] == "resolved"
    assert issue_state["commercial_activation"] == "blocked_D3_human_reserved"

    drive = data["drive_human_master"]
    assert drive["document_id"] == "1NQx0PAigXSFwXa-GMbhYrv6srRwFg8s385QvcJgokFw"
    assert drive["readback_verified"] is True

    assert data["ci_state_at_checkpoint"] == "all_required_success"
    assert data["history_policy"] == "append_or_supersede_never_silent_delete"

    text = CHANGELOG.read_text(encoding="utf-8").lower()
    for phrase in (
        "controlled test",
        "not submitted",
        "provider writes",
        "first cron-fired",
        "d3/human-reserved",
        "append-or-supersede",
    ):
        assert phrase in text, phrase

    print("CrownThrive Interoperability Fabric hardening invariants: PASS")


if __name__ == "__main__":
    main()
