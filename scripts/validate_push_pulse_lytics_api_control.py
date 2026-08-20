#!/usr/bin/env python3
"""Validate the Phase 2.99 ThrivePush/CrownPulse/CrownLytics control packet.

This validator is deterministic and network-free. It protects the public-safe
machine manifest, documentation presence, fail-closed provider/MCP posture and
anti-secret boundary. It does not claim authenticated provider certification.
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
    if data.get("manifest_version") != "1.0.0" or data.get("phase") != "2.99":
        fail("Unexpected manifest version/phase")
    if data.get("secret_values_in_manifest") is not False:
        fail("Manifest must never contain raw credential values")
    if data.get("phase_3_promotion") is not False:
        fail("API packet must not promote Phase 3")

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

    if services["thrivepush"].get("provider_writes") != "closed":
        fail("ThrivePush writes must remain closed")
    if services["crownlytics"].get("provider_writes") != "closed":
        fail("CrownLytics writes must remain closed")
    if services["crownpulse_admin"].get("privileged_mutations") != "closed":
        fail("CrownPulse privileged mutations must remain closed")
    if services["crownpulse_admin"].get("installed_version") != "unverified":
        fail("CrownPulse installed version must not be inferred from update notice")
    if services["crownpulse_admin"].get("update_available_observed") != "v61.0.0":
        fail("CrownPulse update-available observation drifted")

    if not WORKER.is_file() or sha256(WORKER) != EXPECTED_WORKER_SHA:
        fail("ThrivePush service-worker bytes/checksum drifted")
    if services["thrivepush"]["service_worker"].get("sha256") != EXPECTED_WORKER_SHA:
        fail("Worker checksum mismatch between manifest and repository asset")

    for service_id, path in DOCS.items():
        if not path.is_file():
            fail(f"Missing developer page for {service_id}: {path.relative_to(ROOT)}")
    if not CHANGELOG.is_file():
        fail("Missing API reconciliation changelog")

    public_files = list(DOCS.values()) + [CHANGELOG, MANIFEST]
    for path in public_files:
        text = path.read_text(encoding="utf-8")
        if HEX_KEY_RE.search(text):
            fail(f"Possible raw API credential in public packet: {path.relative_to(ROOT)}")

    required_fragments = {
        DOCS["thrivepush"]: ["provider_writes", "closed", "thrivepusher.js"],
        DOCS["crownlytics"]: ["provider_writes", "closed", "crownlytics_api_key"],
        DOCS["crownpulse_admin"]: ["privileged_mutations", "closed", "installed_version: unverified"],
        CHANGELOG: ["mcp_contracts_registered: 38", "provider_writes: closed"],
    }
    for path, fragments in required_fragments.items():
        text = path.read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in text:
                fail(f"Required fragment {fragment!r} missing from {path.relative_to(ROOT)}")

    print(
        "Push/Pulse/Lytics API control validation PASSED: three services, "
        "38 MCP contracts all disabled, credential bindings fail-closed, "
        "provider mutations closed, worker checksum pinned, no raw keys detected, "
        "Phase 3 not promoted."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
