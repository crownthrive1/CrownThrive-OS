#!/usr/bin/env python3
"""Validate the Phase 2.99 ThrivePush/CrownPulse/CrownLytics control packet.

This validator is deterministic and network-free. It protects the public-safe
machine manifest, documentation presence, fail-closed provider/MCP posture,
highest-known-version staging policy and anti-secret boundary. It does not
claim authenticated provider certification or deployment of a staged target.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/push-pulse-lytics-api-control.v1.json"
DOCS = {
    "thrivepush": ROOT / "developers/thrivepush-api-adapter.mdx",
    "crownlytics": ROOT / "developers/crownlytics-api-adapter.mdx",
    "crownpulse_admin": ROOT / "developers/crownpulse-admin-api-adapter.mdx",
}
CHANGELOG = ROOT / "changelog/phase-2-99-thrivepush-crownpulse-crownlytics-api-reconciliation.mdx"
PLATFORM_STATE = ROOT / "portfolio/platform-state-register.mdx"
API_MATRIX = ROOT / "developers/platform-api-adapter-matrix.mdx"
WORKER = ROOT / "developers/assets/thrivepush/thrivepusher.js"
EXPECTED_WORKER_SHA = "19970f0e27cb3eb4d17fb093a25fb0efd7208b36e1336578616d96d8d6ef4788"
HEX_KEY_RE = re.compile(r"(?i)(?:bearer\s+|api[_ -]?key[^\n]{0,30})([a-f0-9]{32,64})")


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not MANIFEST.is_file():
        fail("Missing Push/Pulse/Lytics control manifest")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("manifest_version") != "1.1.0" or data.get("phase") != "2.99":
        fail("Unexpected manifest version/phase")
    if data.get("secret_values_in_manifest") is not False:
        fail("Manifest must never contain raw credential values")
    if data.get("phase_3_promotion") is not False:
        fail("API packet must not promote Phase 3")
    if data.get("version_policy") != "highest_known_version_is_upgrade_target":
        fail("Highest-known-version staging policy is missing from manifest")

    services = {s["service_id"]: s for s in data.get("services", [])}
    if set(services) != {"thrivepush", "crownlytics", "crownpulse_admin"}:
        fail(f"Unexpected service set: {set(services)}")

    for service_id, expected_tools in {"thrivepush": 13, "crownlytics": 11, "crownpulse_admin": 14}.items():
        service = services[service_id]
        if service.get("mcp_contracts_registered") != expected_tools:
            fail(f"Unexpected MCP contract count for {service_id}")
        if service.get("mcp_contracts_enabled") != 0:
            fail(f"MCP tools must remain disabled for {service_id}")
        if service.get("credential_state") != "blocked_pending_approved_secret_write":
            fail(f"Credential state must remain fail-closed for {service_id}")
        if not str(service.get("credential_ref", "")).startswith("vault:"):
            fail(f"Missing Vault reference for {service_id}")
        for field in ("installed_version", "highest_known_version", "target_version", "upgrade_intent", "upgrade_status"):
            if field not in service:
                fail(f"Missing version-governance field {field!r} for {service_id}")
        if service.get("upgrade_intent") != "update_to_highest_known":
            fail(f"Upgrade intent drifted for {service_id}")
        highest = service.get("highest_known_version")
        target = service.get("target_version")
        if highest is None:
            if target is not None:
                fail(f"Target version cannot be invented without highest-known evidence for {service_id}")
            if service.get("upgrade_status") != "not_staged_no_version_evidence":
                fail(f"Unknown-version service must remain unstaged for {service_id}")
        else:
            if target != highest:
                fail(f"Target version must equal highest-known version for {service_id}")

    if services["thrivepush"].get("provider_writes") != "closed":
        fail("ThrivePush writes must remain closed")
    if services["crownlytics"].get("provider_writes") != "closed":
        fail("CrownLytics writes must remain closed")
    crownpulse = services["crownpulse_admin"]
    if crownpulse.get("privileged_mutations") != "closed":
        fail("CrownPulse privileged mutations must remain closed")
    if crownpulse.get("installed_version") != "unverified":
        fail("CrownPulse installed version must not be inferred from update notice")
    if crownpulse.get("update_available_observed") != "v61.0.0":
        fail("CrownPulse update-available observation drifted")
    if crownpulse.get("highest_known_version") != "v61.0.0":
        fail("CrownPulse highest-known version must remain v61.0.0 until stronger evidence supersedes it")
    if crownpulse.get("target_version") != "v61.0.0":
        fail("CrownPulse staged target must equal highest-known v61.0.0")
    if crownpulse.get("upgrade_status") != "staged_pending_preflight":
        fail("CrownPulse v61.0.0 must remain staged pending preflight")

    invariants = data.get("invariants", {})
    if invariants.get("highest_known_version_is_required_upgrade_target") is not True:
        fail("Manifest must require highest-known version as upgrade target")
    if invariants.get("staging_is_not_deployment_proof") is not True:
        fail("Manifest must keep staging separate from deployment proof")

    if not WORKER.is_file() or sha256(WORKER) != EXPECTED_WORKER_SHA:
        fail("ThrivePush service-worker bytes/checksum drifted")
    if services["thrivepush"]["service_worker"].get("sha256") != EXPECTED_WORKER_SHA:
        fail("Worker checksum mismatch between manifest and repository asset")

    for service_id, path in DOCS.items():
        if not path.is_file():
            fail(f"Missing developer page for {service_id}: {path.relative_to(ROOT)}")
    for path in (CHANGELOG, PLATFORM_STATE, API_MATRIX):
        if not path.is_file():
            fail(f"Missing governed documentation: {path.relative_to(ROOT)}")

    public_files = list(DOCS.values()) + [CHANGELOG, PLATFORM_STATE, API_MATRIX, MANIFEST]
    for path in public_files:
        text = path.read_text(encoding="utf-8")
        if HEX_KEY_RE.search(text):
            fail(f"Possible raw API credential in public packet: {path.relative_to(ROOT)}")

    required_fragments = {
        DOCS["thrivepush"]: ["provider_writes", "closed", "thrivepusher.js"],
        DOCS["crownlytics"]: ["provider_writes", "closed", "crownlytics_api_key"],
        DOCS["crownpulse_admin"]: [
            "privileged_mutations",
            "installed_version: unverified",
            "highest_known_version: v61.0.0",
            "target_version: v61.0.0",
            "upgrade_status: staged_pending_preflight",
        ],
        CHANGELOG: [
            "mcp_contracts_registered: 38",
            "provider_writes: closed",
            "version_policy: highest_known_version_is_staged_target",
            "highest_known_version",
            "target_version",
        ],
        PLATFORM_STATE: [
            "## Highest-known version staging rule",
            "highest_known_version",
            "target_version",
            "upgrade_status: staged_pending_preflight",
        ],
        API_MATRIX: [
            "upgrade_intent: update_to_highest_known",
            "highest_known_version: null",
            "target_version: null",
            "target_version=v61.0.0",
        ],
    }
    for path, fragments in required_fragments.items():
        text = path.read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in text:
                fail(f"Required fragment {fragment!r} missing from {path.relative_to(ROOT)}")

    print(
        "Push/Pulse/Lytics API control validation PASSED: three services, "
        "38 MCP contracts all disabled, credential bindings fail-closed, "
        "provider mutations closed, highest-known version staging enforced, "
        "CrownPulse v61.0.0 staged without false installed-version proof, "
        "worker checksum pinned, no raw keys detected, Phase 3 not promoted."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
