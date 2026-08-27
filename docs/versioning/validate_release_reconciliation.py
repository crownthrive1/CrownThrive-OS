#!/usr/bin/env python3
"""Validate the Phase 3 release reconciliation without performing provider writes."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/versioning/RELEASE_RECONCILIATION_MANIFEST.v1.json"
REGISTRY = ROOT / "docs/versioning/VERSION_REGISTRY.json"
POLICY = ROOT / "docs/versioning/CROWNTHRIVE_VERSIONING_POLICY.md"
CURRENT = ROOT / "docs/phase3/CURRENT_STATE.md"
GATE = ROOT / "docs/phase3/RELEASE_CONVERGENCE_GATE.md"
PUBLIC = ROOT / "start-here/current-operational-state.mdx"
LEDGER = ROOT / "docs/archive/RELEASE_SUPERSESSION_LEDGER.v1.json"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict:
    if not path.is_file():
        fail(f"missing file: {path.relative_to(ROOT)}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"expected JSON object: {path.relative_to(ROOT)}")
    return value


def require_text(path: Path, *fragments: str) -> None:
    if not path.is_file():
        fail(f"missing file: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    for fragment in fragments:
        if fragment not in text:
            fail(f"missing {fragment!r} in {path.relative_to(ROOT)}")


def main() -> int:
    manifest = load_json(MANIFEST)
    registry = load_json(REGISTRY)
    ledger = load_json(LEDGER)

    if manifest.get("schema_version") != "1.0.0":
        fail("release reconciliation schema drift")
    if manifest.get("manifest_id") != "ct.release.reconciliation.phase3.v1":
        fail("release reconciliation identity drift")

    institutional = manifest.get("institutional_state", {})
    if institutional.get("phase") != 3:
        fail("institutional phase must remain Phase 3")
    if institutional.get("phase_transition_authorized") is not False:
        fail("this reconciliation must not authorize a phase transition")
    if institutional.get("current_os_release_family") != "3.x":
        fail("current Phase 3 OS family must remain 3.x until exact adjudication")

    published = manifest.get("published_baseline", {})
    expected_published = {
        "release_id": "ct.os.v3.13.0.1",
        "version": "3.13.0.1",
        "tag": "v3.13.0.1",
        "lifecycle_state": "RELEASED",
    }
    for key, value in expected_published.items():
        if published.get(key) != value:
            fail(f"published baseline drift: {key}")
    provider = published.get("provider_observation", {})
    if provider.get("state") != "PASS":
        fail("v3.13.0.1 provider readback must remain PASS")
    if provider.get("published_at") != "2026-08-26T23:46:15Z":
        fail("v3.13.0.1 publication time drift")
    if provider.get("asset_count") != 5:
        fail("v3.13.0.1 provider asset count drift")
    if provider.get("asset_names_readback_in_this_record") is not True:
        fail("provider asset-name readback must remain recorded")
    if provider.get("asset_hashes_readback_in_this_record") is not True:
        fail("provider asset-digest readback must remain recorded")
    expected_assets = {
        "CrownThrive-OS-v3.13.0.1-package.tar.gz": (
            1316,
            "sha256:6dfa4eb266f1b6360c7a6e65555c656bcb4f8d96fc34927cb9a7b76d3a02e0af",
        ),
        "CrownThrive-OS-v3.13.0.1-package.zip": (
            1422,
            "sha256:0b38621e4d73ee53249834a1a213b32a1f39e13d9b129c384484d3f82ee1a01c",
        ),
        "MANIFEST.json": (
            2324,
            "sha256:e54fec372aae886807b7e2921090b0d0eb62767054698c70ac30a32b5fd9b4af",
        ),
        "RELEASE_NOTES.md": (
            662,
            "sha256:9575879db5b66ed924176381a8593420669c658592e5605870c5dd9141f22c98",
        ),
        "SHA256SUMS": (
            372,
            "sha256:37a101dbbc3a636ab1ebcecccfc69c1e537eecc7e411168a82e83b7673d76a38",
        ),
    }
    assets = {
        item.get("name"): (item.get("size_bytes"), item.get("digest"))
        for item in provider.get("assets", [])
        if isinstance(item, dict)
    }
    if assets != expected_assets:
        fail("v3.13.0.1 provider asset readback drift")
    source_tag = published.get("source_tag", {})
    if source_tag.get("commit_sha") != "3b5ab399cc4a3014554f95736fcea7032972989a":
        fail("v3.13.0.1 source tag commit drift")

    candidate = manifest.get("unpublished_candidate", {})
    expected_candidate = {
        "release_id": "ct.os.v3.14.0.0",
        "version": "3.14.0.0",
        "tag": "v3.14.0.0",
        "lifecycle_state": "CANDIDATE_HOLD",
        "commit_sha": "ede88f08c3c93eac12adec306811573bfff27a19",
        "tag_observed": False,
        "provider_release_observed": False,
        "supersedes_published_baseline": False,
    }
    for key, value in expected_candidate.items():
        if candidate.get(key) != value:
            fail(f"unpublished candidate drift: {key}")
    if not str(candidate.get("publication_attempt_state", "")).startswith("FAILED"):
        fail("v3.14.0.0 must retain its failed/incomplete publication state")

    intent = manifest.get("major_release_intent", {})
    if intent.get("release_class") != "major" or intent.get("state") != "HOLD":
        fail("major-release intent must remain HOLD")
    if intent.get("publish_authorized") is not False:
        fail("major release must not be authorized by the reconciliation record")
    if intent.get("target_version") is not None or intent.get("target_head_sha") is not None:
        fail("major target identity must remain unassigned pending exact D3 authority")
    if intent.get("provisional_engine_result") != "4.0.0.0":
        fail("four-part major-bump provisional result drift")
    if intent.get("phase_after_release") != 3:
        fail("major release intent must not advance the institutional phase")

    gates = {
        item.get("gate_id"): item
        for item in manifest.get("prepublication_gates", [])
        if isinstance(item, dict)
    }
    expected_gate_states = {
        "CT-MAJOR-001": "PASS",
        "CT-MAJOR-002": "PASS",
        "CT-MAJOR-003": "HOLD",
        "CT-MAJOR-004": "HOLD",
        "CT-MAJOR-005": "HOLD",
        "CT-MAJOR-009": "HOLD",
        "CT-MAJOR-011": "HOLD",
    }
    for gate_id, state in expected_gate_states.items():
        if gates.get(gate_id, {}).get("state") != state:
            fail(f"major release gate drift: {gate_id}")
    if len(gates) != 13:
        fail("major release prepublication gate set must contain exactly 13 gates")
    if any(item.get("state") == "PASS" for item in manifest.get("completion_gates", [])):
        fail("post-publication gates cannot PASS before a major provider write")

    if registry.get("registry_version") != "1.8.0":
        fail("version registry reconciliation version drift")
    if registry.get("institutional_generation") != "phase_3":
        fail("version registry must remain phase_3")
    if registry.get("umbrella_release") != "3.13.0.1":
        fail("version registry latest release drift")
    pending = registry.get("pending_release", {})
    if pending.get("version") != "3.14.0.0" or pending.get("lifecycle_state") != "CANDIDATE_HOLD":
        fail("version registry pending candidate drift")
    if pending.get("provider_release_observed") is not False:
        fail("version registry may not promote v3.14.0.0")

    components = {
        item.get("component_id"): item
        for item in registry.get("components", [])
        if isinstance(item, dict)
    }
    dail = components.get("ct.dail.evidence-spine", {})
    dail_expected = {
        "version": "2.0.0",
        "lifecycle_state": "controlled_test",
        "native_substrate_state": "deferred_target_architecture",
        "external_anchor_state": "schema_implemented_adapter_not_built",
    }
    for key, value in dail_expected.items():
        if dail.get(key) != value:
            fail(f"DAIL evidence-spine registry boundary drift: {key}")
    predecessor = dail.get("predecessor_baseline", {})
    if predecessor.get("lifecycle_state") != "bounded_production_within_existing_exact_scopes":
        fail("DAIL v1 bounded-production distinction was not preserved")

    if ledger.get("ledger_id") != "ct.archive.release-supersession.v1":
        fail("release supersession ledger identity drift")
    relationships = {
        item.get("relationship_id"): item
        for item in ledger.get("relationships", [])
        if isinstance(item, dict)
    }
    required_relationships = {
        "ct.supersession.release-registry-projection.20260827.v1",
        "ct.supersession.pentarelease-direct-fallback.20260826.v1",
        "ct.nonsupersession.release-candidate-v3.14.0.0.20260827.v1",
        "ct.supersession.phase3-entry-scheduler-topology.20260827.v1",
        "ct.lineage.dail-evidence-spine-v2.20260827.v1",
    }
    if not required_relationships.issubset(relationships):
        fail("release supersession ledger is missing required lineage")

    require_text(POLICY, "Policy version: 1.2.0", "v3.13.0.1", "Human-authorized major release gate")
    require_text(CURRENT, "latest provider-published CrownThrive OS release is `v3.13.0.1`", "`v3.14.0.0`", "Phase 3")
    require_text(
        GATE,
        "**Decision:** `HOLD`",
        "`CT-MAJOR-013`",
        "provider-computed SHA-256",
        "CrownThrive remains in Phase 3",
    )
    require_text(PUBLIC, "**OS release:** CrownThrive OS `3.13.0.1`", "generated `v3.14.0.0` is an unpublished candidate")

    print(json.dumps({
        "status": "PASS",
        "institutional_phase": 3,
        "published_baseline": "v3.13.0.1",
        "unpublished_candidate": "v3.14.0.0",
        "major_release_state": "HOLD",
        "publish_authorized": False,
        "dail_v2_state": "controlled_test",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
