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


def validate_authority_boundary(authority: dict[str, object]) -> None:
    if "founder_authorized_provider_mutation" in authority:
        fail("a bare founder-authorized boolean cannot institutionalize provider mutation authority")
    if authority.get("provider_mutation_authority_effective") is not False:
        fail("provider mutation authority must remain ineffective without governed attestation")
    if authority.get("provider_mutation_authority_state") != "hold_pending_named_signer_attestation":
        fail("provider mutation authority must remain HOLD pending named-signer attestation")
    if authority.get("typed_name_attestation_ref") is not None:
        fail("this public packet may not invent or embed an unattested signer reference")
    if authority.get("required_human_question") != "Who is signing their name to this override?":
        fail("the #150 missing-signer question drifted")


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("manifest_id") != "ct.manifest.sites-production-bootstrap.v1":
        fail("manifest identity drifted")
    if FORBIDDEN_KEYS & walk_keys(data):
        fail("public manifest contains a forbidden private-runtime key")

    authority = data.get("authority", {})
    contract = data.get("contract", {})
    runtime = data.get("runtime_observation", {})
    if not isinstance(authority, dict):
        fail("authority block must be an object")
    validate_authority_boundary(authority)
    if authority.get("phase_3_entry") != "blocked":
        fail("Phase 3 must remain blocked")
    if authority.get("originating_agent_may_self_certify") is not False:
        fail("originating agent may not self-certify")
    if contract.get("fail_closed") is not True:
        fail("consumer contract must fail closed")
    if contract.get("verified_surface_runtime_arming_allowed") is not True:
        fail("full-cycle surfaces must be allowed to retain bounded runtime arming")
    if contract.get("unverified_surface_auto_update_enabled") is not False:
        fail("an unverified surface may not enable automatic updates")
    if contract.get("publication_authority_created") is not False:
        fail("Sites bootstrap must not create publication authority")
    if contract.get("runtime_reconciliation_required") is not True:
        fail("runtime reconciliation must remain mandatory")
    if contract.get("current_policy_canary") != "hold_not_currently_pass":
        fail("current-policy canary may not be represented as PASS")
    if "agent_d" not in str(contract.get("release_authority", "")):
        fail("release authority must retain Agent D in the independent gate")
    if runtime.get("evidence_class") != "sanitized_connected_control_plane_read":
        fail("runtime evidence class drifted")
    if runtime.get("verified_authority_receipts") != 0:
        fail("this exact packet cannot claim a verified authority receipt")
    if runtime.get("accepted_releases") != 0 or runtime.get("published_releases") != 0:
        fail("this exact packet cannot claim an accepted or published release")

    surfaces = data.get("surfaces")
    if not isinstance(surfaces, list) or len(surfaces) != 3:
        fail("exactly three production surfaces are required")
    indexed = {surface.get("surface_id"): surface for surface in surfaces}
    if set(indexed) != EXPECTED_SURFACES:
        fail("production surface set drifted")

    for surface_id, surface in indexed.items():
        state = surface.get("state")
        if state not in ALLOWED_STATES:
            fail(f"{surface_id}: unsupported state")
        parsed = urlparse(str(surface.get("canonical_url", "")))
        if parsed.scheme != "https" or not parsed.netloc:
            fail(f"{surface_id}: canonical URL must be HTTPS")
        did = str(surface.get("consumer_did", ""))
        if not did.startswith("did:web:") or not did.endswith(":crownthrive:catalog-consumer"):
            fail(f"{surface_id}: invalid site-consumer DID")
        if surface.get("provider_mutation_route_armed") is not False:
            fail(f"{surface_id}: provider mutation route must remain unarmed")

        fingerprint = surface.get("fingerprint_id")
        if fingerprint is not None and not SHA256_ID.fullmatch(str(fingerprint)):
            fail(f"{surface_id}: fingerprint is not a SHA-256 commitment")

        if state == "full_cycle_pass":
            required_true = (
                "runtime_consumer_verified",
                "runtime_route_armed",
                "marker_present_after_reapply",
                "exact_surface_readback",
                "feed_reference_present",
                "proxy_body_header_digest_match",
                "rollback_marker_absent",
            )
            if any(surface.get(field) is not True for field in required_true):
                fail(f"{surface_id}: full-cycle proof or bounded runtime arming is incomplete")
            if surface.get("rollback_endpoint_statuses") != [404, 404, 404]:
                fail(f"{surface_id}: rollback absence proof drifted")
            if surface.get("proxy_http_status") != 200 or surface.get("reapply_http_status") != 200:
                fail(f"{surface_id}: full-cycle HTTP proof is incomplete")
        else:
            if surface.get("runtime_consumer_verified") is not False:
                fail(f"{surface_id}: incomplete surface cannot be consumer-verified")
            if surface.get("runtime_route_armed") is not False:
                fail(f"{surface_id}: incomplete surface cannot be runtime-armed")

    virality = indexed["ct.surface.virality-music.production"]
    if virality.get("soundcloud_api") != "REMOVED_BY_FOUNDER_OVERRIDE":
        fail("Virality SoundCloud API founder override drifted")

    if data.get("overall_disposition") != "hold_partial_provider_bootstrap_and_authority_attestation":
        fail("overall disposition must remain HOLD until provider and authority gaps close")
    if not str(data.get("commerce_impact", "")).startswith("none_"):
        fail("Sites bootstrap may not imply commerce authorization")

    print("Sites production bootstrap public manifest validation: PASS")
    print("Disposition: HOLD / partial provider bootstrap and authority attestation; Phase 3 blocked.")
    print("Full-cycle surfaces may retain bounded consumer arming; provider mutation routes remain disabled.")
    print("Bootstrap state does not create release, commerce, founder-override, or sovereign publication authority.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
