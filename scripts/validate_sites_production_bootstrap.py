#!/usr/bin/env python3
"""Fail-closed validation for the public-safe production Sites bootstrap ledger."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/sites-production-bootstrap.v1.json"
EXPECTED_SURFACES = {
    "ct.surface.crownthrive-developer-marketplace.production",
    "ct.surface.kjv-visualized.production",
    "ct.surface.virality-music.production",
}
ALLOWED_STATES = {
    "full_cycle_pass",
    "write_readback_pass_rollback_pending",
    "local_build_pass_provider_write_pending",
}
SHA256_ID = re.compile(r"^ctfp:v1:sha256:[0-9a-f]{64}$")
FORBIDDEN_KEYS = {
    "provider_project_id",
    "provider_deployment_id",
    "vault_secret",
    "private_key",
    "service_role_key",
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def walk_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        found = set(value)
        for child in value.values():
            found.update(walk_keys(child))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for child in value:
            found.update(walk_keys(child))
        return found
    return set()


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("manifest_id") != "ct.manifest.sites-production-bootstrap.v1":
        fail("manifest identity drifted")
    if FORBIDDEN_KEYS & walk_keys(data):
        fail("public manifest contains a forbidden private-runtime key")

    authority = data.get("authority", {})
    contract = data.get("contract", {})
    if authority.get("phase_3_entry") != "blocked":
        fail("Phase 3 must remain blocked")
    if authority.get("originating_agent_may_self_certify") is not False:
        fail("originating agent may not self-certify")
    if contract.get("fail_closed") is not True:
        fail("consumer contract must fail closed")
    if contract.get("auto_update_enabled") is not False:
        fail("production auto-update must remain disabled")
    if contract.get("current_policy_canary") != "hold_not_currently_pass":
        fail("current-policy canary may not be represented as PASS")

    surfaces = data.get("surfaces")
    if not isinstance(surfaces, list) or len(surfaces) != 3:
        fail("exactly three production surfaces are required")
    indexed = {surface.get("surface_id"): surface for surface in surfaces}
    if set(indexed) != EXPECTED_SURFACES:
        fail("production surface set drifted")

    for surface_id, surface in indexed.items():
        if surface.get("state") not in ALLOWED_STATES:
            fail(f"{surface_id}: unsupported state")
        parsed = urlparse(str(surface.get("canonical_url", "")))
        if parsed.scheme != "https" or not parsed.netloc:
            fail(f"{surface_id}: canonical URL must be HTTPS")
        did = str(surface.get("consumer_did", ""))
        if not did.startswith("did:web:") or not did.endswith(":crownthrive:catalog-consumer"):
            fail(f"{surface_id}: invalid site-consumer DID")

        fingerprint = surface.get("fingerprint_id")
        if fingerprint is not None and not SHA256_ID.fullmatch(str(fingerprint)):
            fail(f"{surface_id}: fingerprint is not a SHA-256 commitment")

        if surface.get("state") == "full_cycle_pass":
            required_true = (
                "marker_present_after_reapply",
                "exact_surface_readback",
                "feed_reference_present",
                "proxy_body_header_digest_match",
                "rollback_marker_absent",
            )
            if any(surface.get(field) is not True for field in required_true):
                fail(f"{surface_id}: full-cycle proof is incomplete")
            if surface.get("rollback_endpoint_statuses") != [404, 404, 404]:
                fail(f"{surface_id}: rollback absence proof drifted")
            if surface.get("proxy_http_status") != 200 or surface.get("reapply_http_status") != 200:
                fail(f"{surface_id}: full-cycle HTTP proof is incomplete")

    if data.get("overall_disposition") != "hold_partial_provider_bootstrap":
        fail("overall disposition must remain HOLD until every surface completes the cycle")
    if not str(data.get("commerce_impact", "")).startswith("none_"):
        fail("Sites bootstrap may not imply commerce authorization")

    print("Sites production bootstrap public manifest validation: PASS")
    print("Disposition: HOLD / partial provider bootstrap; Phase 3 blocked; auto-update disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
