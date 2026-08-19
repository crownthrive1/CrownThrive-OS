#!/usr/bin/env python3
"""Validate the CrownThrive THIVEBASE operational automation overlay."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/thivebase-operational-automation.v1.json"
CONTROL_CENTER = ROOT / "changelog/phase-2-99-roadmap-and-operational-watch-control-center.mdx"
RELAY = ROOT / "automation/institutional-hourly-agent-relay.mdx"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    if not MANIFEST.is_file():
        fail("Missing THIVEBASE operational automation manifest")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if data.get("manifest_id") != "ct.manifest.thivebase-operational-automation.v1":
        fail("Manifest identity drifted")
    if data.get("phase") != "2.99" or data.get("canonical_roadmap_generation") != "ten_phase_v1":
        fail("Phase/roadmap identity drifted")
    if data.get("governance_decision_id") != "CT-ADR-GOV-011":
        fail("Operational automation must inherit CT-ADR-GOV-011")

    heartbeat = data.get("heartbeat", {})
    if heartbeat.get("cadence") != "monthly":
        fail("THIVEBASE ecosystem heartbeat must remain monthly")
    if heartbeat.get("real_user_database_activity_required") is not True:
        fail("Heartbeat must require real user database activity")
    if heartbeat.get("required_first_database_call") != "public.thivebase_health_snapshot()":
        fail("Heartbeat must begin with public.thivebase_health_snapshot()")
    if heartbeat.get("required_project_health") != "ACTIVE_HEALTHY":
        fail("Heartbeat must explicitly verify ACTIVE_HEALTHY")
    if heartbeat.get("default_probe_mode") != "read_only_fail_closed":
        fail("Heartbeat default probe mode must remain read-only/fail-closed")
    if heartbeat.get("unknown_metric_policy") != "preserve_unknown_never_zero":
        fail("UNKNOWN metrics must never be normalized to zero")

    thresholds = heartbeat.get("capacity_thresholds_percent", {})
    expected = {
        "green_max_exclusive": 50,
        "watch_min": 50,
        "watch_max": 69,
        "plan_min": 70,
        "plan_max": 79,
        "action_needed_min": 80,
        "action_needed_max": 89,
        "scale_gate_min": 90,
    }
    if thresholds != expected:
        fail("THIVEBASE capacity thresholds drifted")
    if heartbeat.get("forecast_early_escalation") is not True:
        fail("Forecast-based early escalation must remain enabled")

    targets = {row.get("service_id"): row for row in data.get("service_targets", [])}
    required_targets = {
        "thivebase", "crownthrive_io", "thrivetools_seo", "collab_portal",
        "partnero", "adluxe_network", "adserver_online", "crownrewards",
        "reward_loyalty", "stripe", "github_main_perimeter", "locticians",
        "crownthrive_id", "onzauth",
    }
    missing = required_targets - set(targets)
    if missing:
        fail(f"Missing required heartbeat targets: {sorted(missing)}")
    for service_id, row in targets.items():
        if row.get("writes_enabled_by_heartbeat") is not False:
            fail(f"Heartbeat unexpectedly enables writes for {service_id}")

    version_policy = data.get("software_engine_version_policy", {})
    for key in (
        "current_vendor_release_is_default_target_reference",
        "target_release_never_proves_installed_release",
        "installed_version_requires_production_evidence",
        "historical_purchase_price_never_overwritten_by_current_marketplace_price",
        "channel_specific_prices_remain_separate",
    ):
        if version_policy.get(key) is not True:
            fail(f"Software-engine tracker invariant missing: {key}")

    rewards = data.get("reward_loyalty_boundary", {})
    if rewards.get("current_crownthrive_install") != "v4":
        fail("Reward Loyalty current CrownThrive install must remain v4 until evidence changes it")
    if rewards.get("vendor_target_version") != "5.27.0":
        fail("Reward Loyalty vendor target must remain v5.27.0 for this evidence snapshot")
    if rewards.get("production_v5_deployed") is not False:
        fail("Reward Loyalty v5 must not be represented as deployed")
    if rewards.get("v4_must_remain_intact_until_v5_gates_pass") is not True:
        fail("Reward Loyalty v4 preservation rule drifted")
    if rewards.get("v5_rest_api") != "session_token_bearer_user_context":
        fail("Reward Loyalty REST API boundary drifted")
    if rewards.get("v5_agent_api") != "x_agent_key_machine_to_machine_role_scopes":
        fail("Reward Loyalty Agent API boundary drifted")
    if rewards.get("v5_agent_tool_discovery") != "/api/agent/v1/tools?format=mcp":
        fail("Reward Loyalty MCP-format discovery contract drifted")

    collab = data.get("collab_portal_webhook_boundary", {})
    if collab.get("legacy_generic_receiver") != "retired_410":
        fail("Legacy Collab receiver must remain retired")
    if collab.get("strict_project_event_envelope") is not True:
        fail("Collab project envelope must remain strict")
    if collab.get("pinned_project_uid_required") is not True:
        fail("Collab project receiver must require pinned project identity")
    if collab.get("streaming_pre_read_body_limit_bytes") != 65536:
        fail("Collab pre-read body ceiling drifted")
    if collab.get("raw_payload_retention") is not False:
        fail("Collab raw webhook payload retention must remain disabled")
    if collab.get("event_driven_sync_enabled") is not False:
        fail("Collab event-driven sync must remain closed until live delivery integrity passes")
    if collab.get("live_provider_delivery_certified") is not False:
        fail("Collab live provider delivery must not be fabricated")

    delegates = data.get("delegated_subagents", {})
    required_delegates = {"integration_heartbeat", "credential_continuity", "vendor_engine_watch"}
    if set(delegates) != required_delegates:
        fail("Delegated THIVEBASE subagent set drifted")
    forbidden_tokens = {"provider_mutation", "credential_rotation", "sovereign_vote"}
    for name, row in delegates.items():
        if row.get("vote_eligible") is not False:
            fail(f"Operational subagent {name} must remain non-voting")
        allowed = set(row.get("allowed", []))
        if allowed & forbidden_tokens:
            fail(f"Operational subagent {name} received prohibited authority")

    serialized = json.dumps(data, sort_keys=True).lower()
    for forbidden_fragment in (
        "raw_secret_value", "plaintext_api_key", "webhook_secret_value", "credential_fingerprint_value"
    ):
        if forbidden_fragment in serialized:
            fail(f"Manifest contains forbidden secret-material field: {forbidden_fragment}")

    for path, fragment in (
        (CONTROL_CENTER, "THIVEBASE Monthly Heartbeat"),
        (RELAY, "THIVEBASE Monthly Heartbeat"),
    ):
        if not path.is_file() or fragment not in path.read_text(encoding="utf-8"):
            fail(f"Required operational heartbeat documentation missing from {path.relative_to(ROOT)}")

    print("THIVEBASE operational automation validation passed.")
    print("Monthly heartbeat: database activity + ACTIVE_HEALTHY + P0 read-only control checks.")
    print("Delegated subagents: 3 non-voting, read-first, no provider-write or sovereign authority.")
    print("Reward Loyalty: v4 preserved; v5.27.0 target only; REST/Agent API remain gated.")
    print("Collab Portal: split receivers hardened; live provider-delivery integrity still fail-closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
