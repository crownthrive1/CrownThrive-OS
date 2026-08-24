#!/usr/bin/env python3
"""Validate CrownThrive's highest-known-version staging policy.

This validator is deterministic and network-free. It ensures that known newer
software versions are documented as upgrade targets without converting staging
into installed/deployed/production proof. Unknown versions remain explicit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/highest-known-version-policy.v1.json"
PLATFORM_STATE = ROOT / "portfolio/platform-state-register.mdx"
API_MATRIX = ROOT / "developers/platform-api-adapter-matrix.mdx"
CROWNPULSE_DOC = ROOT / "developers/crownpulse-admin-api-adapter.mdx"
API_CONTROL = ROOT / "developers/manifests/push-pulse-lytics-api-control.v1.json"


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def require_fragments(path: Path, fragments: list[str]) -> None:
    if not path.is_file():
        fail(f"Missing governed file: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    for fragment in fragments:
        if fragment not in text:
            fail(f"Required fragment {fragment!r} missing from {path.relative_to(ROOT)}")


def main() -> int:
    if not MANIFEST.is_file():
        fail("Missing highest-known-version policy manifest")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("manifest_version") != "1.0.0":
        fail("Unexpected highest-known-version manifest version")
    if data.get("policy_id") != "ct.policy.highest-known-version-staging.v1":
        fail("Unexpected version-policy ID")
    if data.get("phase_3_promotion") is not False:
        fail("Version staging must not promote Phase 3")

    rules = data.get("rules", {})
    required_true = [
        "highest_known_version_becomes_target_immediately",
        "installed_version_is_independent_fact",
        "installed_version_may_be_unverified",
        "target_version_must_equal_highest_known_version_when_known",
        "unknown_highest_known_version_requires_null_target",
        "staging_is_not_installation_or_deployment_proof",
        "production_upgrade_requires_preflight",
        "newer_authoritative_evidence_advances_target_prospectively",
        "historical_installed_and_target_versions_are_preserved",
    ]
    for key in required_true:
        if rules.get(key) is not True:
            fail(f"Required version-policy invariant is not true: {key}")

    targets = data.get("known_targets", [])
    by_platform = {row.get("platform_id"): row for row in targets}
    expected = {
        "ct.platform.crownpulse": ("v61.0.0", "staged_pending_preflight"),
        "ct.platform.crownrewards": ("5.27.0", "staged_pending_preflight"),
        "ct.platform.thrivetools-opt": ("v4.0.0", "staged_pending_installed_version_resolution"),
    }
    if set(by_platform) != set(expected):
        fail(f"Unexpected known-target platform set: {set(by_platform)}")

    for platform_id, (version, status) in expected.items():
        row = by_platform[platform_id]
        if row.get("highest_known_version") != version:
            fail(f"Highest-known version drifted for {platform_id}")
        if row.get("target_version") != version:
            fail(f"Target must equal highest-known version for {platform_id}")
        if row.get("upgrade_status") != status:
            fail(f"Upgrade staging state drifted for {platform_id}")
        if not row.get("service_ids"):
            fail(f"Known target lacks service mapping: {platform_id}")
        if not row.get("evidence_ref"):
            fail(f"Known target lacks evidence reference: {platform_id}")

    require_fragments(
        PLATFORM_STATE,
        [
            "## Highest-known version staging rule",
            "highest_known_version",
            "target_version",
            "staged_pending_preflight",
            "Staging is not proof that the version is installed, deployed or production-certified",
        ],
    )
    require_fragments(
        API_MATRIX,
        [
            "installed_version: unverified",
            "highest_known_version: null",
            "target_version: null",
            "upgrade_intent: update_to_highest_known",
            "target_version=v61.0.0",
        ],
    )
    require_fragments(
        CROWNPULSE_DOC,
        [
            "highest_known_version: v61.0.0",
            "target_version: v61.0.0",
            "installed_version: unverified",
            "upgrade_status: staged_pending_preflight",
        ],
    )

    if not API_CONTROL.is_file():
        fail("Missing Push/Pulse/Lytics API control manifest")
    api = json.loads(API_CONTROL.read_text(encoding="utf-8"))
    if api.get("version_policy") != "highest_known_version_is_upgrade_target":
        fail("API control manifest does not inherit the global version rule")
    services = {s.get("service_id"): s for s in api.get("services", [])}
    pulse = services.get("crownpulse_admin", {})
    if pulse.get("installed_version") != "unverified":
        fail("CrownPulse installed version must remain independently unverified")
    if pulse.get("highest_known_version") != "v61.0.0" or pulse.get("target_version") != "v61.0.0":
        fail("CrownPulse API control must stage v61.0.0")

    print(
        "Highest-known version policy PASSED: known software releases are staged as "
        "targets, installed/deployed truth remains independent, CrownPulse v61.0.0, "
        "CrownRewards 5.27.0 and ThriveTools OPT v4.0.0 are pinned as current targets."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
