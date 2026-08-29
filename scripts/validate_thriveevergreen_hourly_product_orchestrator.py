#!/usr/bin/env python3
"""Validate the public-safe ThriveEvergreen v1.1 observer projection."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/thriveevergreen-hourly-product-orchestrator.v1.json"
AUTHORITY = ROOT / "commerce/thriveevergreen.mdx"
AUTOMATION = ROOT / "automation/thriveevergreen-hourly-product-orchestration.mdx"
CHANGELOG = ROOT / "changelog/thriveevergreen-hourly-observer-v1-1-hardening-2026-08-23.mdx"
NAV = ROOT / "docs.json"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(text: str, fragment: str, source: Path) -> None:
    if fragment not in text:
        fail(f"missing {fragment!r} in {source.relative_to(ROOT)}")


def navigation_pages(nav: dict) -> list[str]:
    """Return every string route from the native Mintlify navigation tree.

    CrownThrive has used tabs with ``groups`` and tabs with group objects under
    ``pages``. Large documentation estates now also use nested groups so mobile
    sidebars remain bounded. Route-count validation must recurse through those
    valid presentation containers while preserving the exact-one-route gate.
    """
    routes: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, str):
            routes.append(node)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        for key in ("pages", "groups", "tabs", "dropdowns", "products", "versions", "languages"):
            value = node.get(key)
            if value is not None:
                walk(value)

    walk(nav.get("navigation", {}).get("tabs", []))
    return routes


def main() -> int:
    manifest = json.loads(read(MANIFEST))
    docs = {path: read(path) for path in (AUTHORITY, AUTOMATION, CHANGELOG)}

    expected = {
        "schema_version": "1.0.0",
        "component_id": "ct.component.thriveevergreen-hourly-product-orchestrator.v1",
        "component_semantic_version": "1.1.0",
        "component_state": "production_observer_active",
        "activation_certification": "ACTIVE_OBSERVER_WITH_FRESH_SLOT_CANARY_PENDING",
        "whole_platform_state": "specified_phase_2",
        "phase_2_99_hard_exit": "not_met",
        "phase_3_certified": False,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            fail(f"identity/state drift: {key}")

    authority = manifest["authority"]
    if authority.get("autonomy_ceiling") != "A2" or authority.get("delegation_ceiling") != "D2":
        fail("authority must remain A2/D2")
    if authority.get("d3_human_reserved") is not True:
        fail("D3 must remain human-reserved")
    for key in ("vote_eligible", "self_approval_allowed", "authority_manufacture_allowed"):
        if authority.get(key) is not False:
            fail(f"authority prohibition drift: {key}")

    runtime = manifest["runtime_execution"]
    runtime_expected = {
        "policy_state": "active",
        "agent_state": "active",
        "scheduler_state": "active",
        "direct_internal_execution_state": "revoked",
        "service_execution_path": "governed_wrapper_only",
    }
    for key, value in runtime_expected.items():
        if runtime.get(key) != value:
            fail(f"runtime drift: {key}")

    window = manifest["target_hourly_window"]
    window_expected = {
        "cadence_class": "hourly",
        "utc_window": True,
        "maximum_candidate_attempts": 1,
        "maximum_publication_ceiling": 0,
        "hold_consumes_window": True,
        "catch_up_burst_allowed": False,
        "idempotent_window": True,
    }
    for key, value in window_expected.items():
        if window.get(key) != value:
            fail(f"hourly policy drift: {key}")

    economic = manifest["economic_boundary"]
    if economic.get("verdicts") != ["ECAC", "HOLD", "DENY"]:
        fail("economic verdict vocabulary drift")
    for key, value in economic.items():
        if key.endswith("_authorized") or key == "production_effects_enabled":
            if value is not False:
                fail(f"economic effect must remain disabled: {key}")
    if economic.get("current_authorized_publications_per_hour") != 0:
        fail("authorized publication rate must remain zero")

    hardening = manifest["version_1_1_hardening"]
    hardening_expected = {
        "read_only_preview_zero_change_proof": "PASS",
        "shared_slot_structural_control": "PASS",
        "fresh_unconsumed_hour_persistence_canary": "PENDING",
        "publication_code_path_present": False,
        "production_write_or_effect_mode_rejected": True,
        "service_principal": "HOLD_HTTP_403",
        "dispatcher_rollback": "HOLD_LOGICAL_ROLLBACK_EXACT_HASH_MISMATCH",
    }
    for key, value in hardening_expected.items():
        if hardening.get(key) != value:
            fail(f"hardening projection drift: {key}")
    io_api = hardening["io_api_observation"]
    if io_api != {
        "economic_verdict": "HOLD",
        "pass_or_not_applicable_gates": 6,
        "hold_gates": 4,
        "publication_count": 0,
        "provider_write_count": 0,
    }:
        fail("IO API observation projection drift")
    dail = hardening["dail_pre_final_event"]
    if dail != {"ok": True, "checked_events": 968, "failure_count": 0}:
        fail("DAIL pre-final-event projection drift")
    final_dail = hardening.get("dail_post_documentation_final_event")
    if final_dail != {
        "ok": True,
        "checked_events": 971,
        "failure_count": 0,
        "head_matches_final_event": True,
        "integrity_state": "pass_with_documented_legacy_correction",
    }:
        fail("post-documentation DAIL verification drift")

    verification = manifest["verification"]
    if verification.get("state") != "ACTIVE_OBSERVER_WITH_FRESH_SLOT_CANARY_PENDING":
        fail("verification ceiling drift")
    if verification.get("fresh_slot_persistence_canary") != "PENDING":
        fail("fresh-slot pending verification drift")
    if verification.get("dail_post_documentation_final_event") != "PASS":
        fail("final DAIL verification PASS removed")
    if verification.get("dispatcher_exact_hash_rollback") != "HOLD":
        fail("dispatcher rollback HOLD removed")
    if verification.get("economic_publications") != 0 or verification.get("provider_writes") != 0:
        fail("economic/provider effect count must remain zero")

    required_docs = {
        AUTOMATION: ["ACTIVE_OBSERVER_WITH_FRESH_SLOT_CANARY_PENDING", "publication target is zero", "not a promise that", "fresh unconsumed-hour persistence canary", "HOLD` after HTTP `403`"],
        CHANGELOG: ["production_observer_active", "ACTIVE_OBSERVER_WITH_FRESH_SLOT_CANARY_PENDING", "checked_events=971", "Post-documentation final DAIL verification"],
    }
    for path, fragments in required_docs.items():
        for fragment in fragments:
            require(docs[path], fragment, path)

    nav = json.loads(read(NAV))
    pages = navigation_pages(nav)
    for route in (
        "automation/thriveevergreen-hourly-product-orchestration",
        "changelog/thriveevergreen-hourly-observer-v1-1-hardening-2026-08-23",
    ):
        if pages.count(route) != 1:
            fail(f"navigation route must appear exactly once: {route}")

    public_text = "\n".join([read(MANIFEST), *docs.values()])
    for pattern in (
        r"SUPABASE_SERVICE_ROLE_KEY",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"(?i)service[_ -]?role[_ -]?(?:key|secret)\s*[:=]",
        r"(?i)access[_ -]?token\s*[:=]",
        r"(?i)pg_cron\s*:",
        r"(?i)provider[_ -]?task[_ -]?id\s*[:=]",
        r"(?i)exact[_ -]?(?:cron|scheduler)[_ -]?(?:minute|offset)\s*[:=]\s*[0-9]",
    ):
        if re.search(pattern, public_text):
            fail(f"secret/internal schedule pattern detected: {pattern}")
    for claim in ("fully certified", "publishes one product per hour"):
        if claim in public_text.lower():
            fail(f"unsupported claim detected: {claim}")

    print(json.dumps({
        "status": "PASS",
        "component_state": manifest["component_state"],
        "certification_ceiling": manifest["activation_certification"],
        "target_candidate_attempts_per_hour": 1,
        "publication_target": 0,
        "economic_effects": "DENY",
        "fresh_slot_canary": "PENDING",
        "service_principal": "HOLD_HTTP_403",
        "dispatcher_exact_hash_rollback": "HOLD",
        "nav_entries": 2,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
