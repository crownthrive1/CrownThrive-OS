#!/usr/bin/env python3
"""Validate the human-authorized CrownThrive OS v4 release contract.

The validator consumes public source terms plus live provider evidence. It never
accepts chat text, an agent/quorum decision, or a green workflow as D3 authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_REPOSITORY = "crownthrive1/CrownThrive-Support"
EXPECTED_VERSION = "4.0.0.0"
EXPECTED_TAG = "v4.0.0.0"
EXPECTED_TITLE = "CrownThrive OS 4.0.0.0 — Human-Authorized Major Release"
EXPECTED_PACKAGE = "releases/4.0.0.0"
EXPECTED_TERMS_PATH = ".github/release-terms/crownthrive-os-v4.0.0.0.json"
EXPECTED_APPROVAL_MARKER = "CROWNTHRIVE_D3_MAJOR_RELEASE_APPROVED"
EXPECTED_APPROVER = "crownthrive1"
EXPECTED_CANDIDATE_SHA = "ede88f08c3c93eac12adec306811573bfff27a19"
EXPECTED_CANDIDATE_BRANCH = "refs/remotes/origin/pentarelease/auto-3.14.0.0-33024509722"
EXPECTED_BASELINE_TAG_SHA = "3b5ab399cc4a3014554f95736fcea7032972989a"
EXPECTED_BASELINE_SOURCE_SHA = "eb2662b57e47384a85bdaa97df5a7ad9c13c78f2"
EXPECTED_GATE_PREDICATES = {
    "CT-MAJOR-001": "provider_published_baseline_reconciled",
    "CT-MAJOR-002": "institutional_phase_remains_phase_3",
    "CT-MAJOR-003": "v3.14.0.0_candidate_has_explicit_immutable_disposition",
    "CT-MAJOR-004": "exact_d3_human_release_authority_recorded",
    "CT-MAJOR-005": "phase_and_release_family_namespace_reconciled",
    "CT-MAJOR-006": "exact_target_head_frozen_and_clean",
    "CT-MAJOR-007": "governed_merge_and_required_check_context_pass_at_exact_head",
    "CT-MAJOR-008": "applicable_tests_docs_security_and_secret_scans_pass",
    "CT-MAJOR-009": "inherited_holds_are_resolved_or_explicitly_carried_forward",
    "CT-MAJOR-010": "release_package_notes_manifest_and_checksums_built_for_exact_head",
    "CT-MAJOR-011": "managed_release_projections_match_intended_baseline",
    "CT-MAJOR-012": "provider_write_topology_and_idempotent_promotion_path_verified",
    "CT-MAJOR-013": "rollback_correction_and_supersession_path_bound",
}
EXPECTED_ASSETS = [
    "CrownThrive-OS-v4.0.0.0-package.zip",
    "CrownThrive-OS-v4.0.0.0-package.tar.gz",
    "SHA256SUMS",
    "MANIFEST.json",
    "RELEASE_NOTES.md",
]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN_SOURCE_KEYS = {
    "chat_text",
    "raw_chat",
    "chat_hash",
    "conversation_text",
    "conversation_sha256",
    "prompt_text",
    "session_id",
    "user_pii",
}
FORBIDDEN_SOURCE_FRAGMENTS = (
    "chatgpt.com/share/",
    "chat://",
    "conversation://",
    "raw conversation",
    "raw chat transcript",
)


class MajorReleaseValidationError(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise MajorReleaseValidationError(reason)


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing_json:{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MajorReleaseValidationError(f"invalid_json:{path}") from exc
    require(isinstance(value, dict), f"json_object_required:{path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_time(value: str, field: str) -> datetime:
    require(isinstance(value, str) and value, f"{field}_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MajorReleaseValidationError(f"{field}_invalid") from exc
    require(parsed.tzinfo is not None, f"{field}_timezone_required")
    return parsed.astimezone(timezone.utc)


def safe_source_path(root: Path, value: str, field: str) -> Path:
    require(isinstance(value, str) and value, f"{field}_required")
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts, f"{field}_unsafe")
    resolved = (root / path).resolve()
    require(resolved.is_relative_to(root.resolve()), f"{field}_outside_repository")
    return resolved


def validate_no_private_conversation(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            require(str(key).lower() not in FORBIDDEN_SOURCE_KEYS, f"private_conversation_key:{path}.{key}")
            validate_no_private_conversation(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_no_private_conversation(item, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        require(
            not any(fragment in lowered for fragment in FORBIDDEN_SOURCE_FRAGMENTS),
            f"private_conversation_reference:{path}",
        )


def validate_terms(terms: dict[str, Any], *, ready: bool) -> tuple[datetime | None, datetime | None]:
    require(terms.get("schema_version") == "1.0.0", "terms_schema_version")
    require(terms.get("terms_id") == "ct.pentarelease.major.v4.0.0.0.terms", "terms_id")
    require(terms.get("terms_version") == "1.0.0", "terms_version")
    require(terms.get("repository") == EXPECTED_REPOSITORY, "terms_repository")

    release = terms.get("release", {})
    require(release.get("release_class") == "major", "terms_release_class")
    require(release.get("version") == EXPECTED_VERSION, "terms_version_identity")
    require(release.get("tag") == EXPECTED_TAG, "terms_tag")
    require(release.get("version_scheme") == "crownthrive_extended", "terms_version_scheme")

    content_binding = terms.get("content_binding", {})
    require(
        content_binding.get("mode") == "provider_pull_request_head_plus_public_terms_sha256",
        "terms_content_binding_mode",
    )
    require(content_binding.get("source_sha_in_terms") is False, "terms_self_referential_sha_prohibited")
    require(content_binding.get("content_change_after_approval_prohibited") is True, "terms_content_freeze")

    compatibility = terms.get("compatibility_effect", {})
    require(isinstance(compatibility.get("summary"), str) and compatibility["summary"].strip(), "compatibility_effect")
    require(compatibility.get("component_versions_remain_independent") is True, "component_version_independence")
    require(compatibility.get("component_states_promoted") is False, "component_state_non_promotion")

    namespaces = terms.get("institutional_namespaces", {})
    require(namespaces.get("institutional_phase_before") == 3, "phase_before")
    require(namespaces.get("institutional_phase_after") == 3, "phase_after")
    require(namespaces.get("phase_transition_authorized") is False, "phase_transition_prohibited")
    require(namespaces.get("os_release_family_before") == "3.x", "os_family_before")
    require(namespaces.get("os_release_family_after") == "4.x", "os_family_after")
    require(
        namespaces.get("os_4x_effective_only_after_v4_provider_readback") is True,
        "os_4x_readback_condition",
    )

    abandoned = terms.get("abandoned_candidate", {})
    require(abandoned.get("version") == "3.14.0.0", "abandoned_candidate_version")
    require(abandoned.get("tag") == "v3.14.0.0", "abandoned_candidate_tag")
    require(abandoned.get("commit_sha") == EXPECTED_CANDIDATE_SHA, "abandoned_candidate_sha")
    require(abandoned.get("branch_ref") == EXPECTED_CANDIDATE_BRANCH, "abandoned_candidate_branch")
    require(abandoned.get("state") == "ABANDONED_INVALID_LINEAGE_CANDIDATE", "abandoned_candidate_state")
    require(abandoned.get("provider_tag_observed") is False, "abandoned_candidate_tag_absence")
    require(abandoned.get("provider_release_observed") is False, "abandoned_candidate_release_absence")
    require(abandoned.get("branch_and_commit_preserved") is True, "abandoned_candidate_preservation")
    require(abandoned.get("tag_and_version_reuse_prohibited") is True, "abandoned_candidate_reuse")

    authority = terms.get("authority_boundaries", {})
    for key in (
        "human_founder_only",
        "surrogate_used",
        "silence_is_authority",
        "agent_authority",
        "quorum_substitution",
        "D3_auto",
        "provider_release_creates_authority",
    ):
        expected = key == "human_founder_only"
        require(authority.get(key) is expected, f"terms_authority_boundary:{key}")
    require(authority.get("provider_write_scope_only") is True, "provider_write_scope")

    privacy = terms.get("privacy", {})
    require(privacy.get("public_terms_only") is True, "public_terms_only")
    require(privacy.get("chat_transcript_included") is False, "chat_transcript_prohibited")
    require(privacy.get("private_conversation_digest_included") is False, "chat_digest_prohibited")
    validate_no_private_conversation(terms)

    validity = terms.get("validity", {})
    if ready:
        requested_at = parse_time(validity.get("requested_at"), "terms_requested_at")
        not_before = parse_time(validity.get("not_before"), "terms_not_before")
        expires_at = parse_time(validity.get("expires_at"), "terms_expires_at")
        require(requested_at <= not_before < expires_at, "terms_validity_window")
        require(
            isinstance(validity.get("single_use_nonce"), str) and validity["single_use_nonce"].strip(),
            "terms_single_use_nonce",
        )
        return not_before, expires_at
    require(validity.get("requested_at") is None, "template_terms_requested_at_must_be_unassigned")
    require(validity.get("not_before") is None, "template_terms_not_before_must_be_unassigned")
    require(validity.get("expires_at") is None, "template_terms_expiry_must_be_unassigned")
    require(validity.get("single_use_nonce") is None, "template_terms_nonce_must_be_unassigned")
    return None, None


def validate_file_binding(root: Path, binding: dict[str, Any], field: str, *, ready: bool) -> None:
    path = safe_source_path(root, binding.get("path"), f"{field}_path")
    digest = binding.get("sha256")
    if not ready:
        require(digest is None, f"template_{field}_digest_must_be_unassigned")
        return
    require(isinstance(digest, str) and SHA256_RE.fullmatch(digest) is not None, f"{field}_digest")
    require(path.is_file(), f"{field}_missing")
    require(sha256_file(path) == digest, f"{field}_digest_mismatch")


def validate_request(
    root: Path,
    request: dict[str, Any],
    terms_path: Path,
    terms_sha256: str,
    *,
    ready: bool,
) -> None:
    require(request.get("schema_version") == "1.0.0", "request_schema_version")
    require(request.get("request_id") == "ct.os.v4.0.0.0.major", "request_id")
    require(request.get("release_id") == "ct.os.v4.0.0.0", "release_id")
    require(request.get("repository") == EXPECTED_REPOSITORY, "request_repository")
    require(request.get("release_class") == "major", "request_release_class")
    require(request.get("authority_class") == "D3_HUMAN_RESERVED", "request_authority_class")
    require(request.get("version") == EXPECTED_VERSION, "request_version")
    require(request.get("tag") == EXPECTED_TAG, "request_tag")
    require(request.get("version_scheme") == "crownthrive_extended", "request_version_scheme")
    require(request.get("title") == EXPECTED_TITLE, "request_title")
    require(request.get("package") == EXPECTED_PACKAGE, "request_package")
    require(request.get("target_binding") == "github_event_merge_sha", "request_target_binding")
    require(request.get("draft") is False, "request_draft")
    require(request.get("prerelease") is False, "request_prerelease")

    baseline = request.get("published_baseline", {})
    require(baseline.get("tag") == "v3.13.0.1", "baseline_tag")
    require(baseline.get("tag_sha") == EXPECTED_BASELINE_TAG_SHA, "baseline_tag_sha")
    require(baseline.get("source_baseline_sha") == EXPECTED_BASELINE_SOURCE_SHA, "baseline_source_sha")

    terms = request.get("authority_terms", {})
    require(terms.get("path") == EXPECTED_TERMS_PATH, "request_terms_path")
    if ready:
        require(
            terms_path == (root / EXPECTED_TERMS_PATH).resolve(),
            "loaded_terms_path",
        )
        require(terms.get("sha256") == terms_sha256, "request_terms_digest_mismatch")
    else:
        require(terms.get("sha256") is None, "template_terms_digest_must_be_unassigned")

    authority = request.get("authority", {})
    expected_authority = {
        "approval_marker": EXPECTED_APPROVAL_MARKER,
        "authorized_actor_login": EXPECTED_APPROVER,
        "authorized_actor_association": "OWNER",
        "authority_subject_role": "ct.role.founder",
        "human_founder_only": True,
        "surrogate_used": False,
        "silence_is_authority": False,
        "agent_authority": False,
        "quorum_substitution": False,
        "D3_auto": False,
        "provider_evidence_resolution": "event_merge_pull_request_review_or_comment",
    }
    for key, value in expected_authority.items():
        require(authority.get(key) == value, f"request_authority:{key}")
    candidate = request.get("candidate_binding", {})
    require(candidate.get("mode") == "provider_event_pull_request_head", "candidate_binding_mode")
    for key in ("frozen_head_sha", "pull_request_number", "provider_approval_id"):
        require(candidate.get(key) is None, f"source_{key}_must_be_unassigned")

    abandoned = request.get("abandoned_candidate", {})
    require(abandoned.get("commit_sha") == EXPECTED_CANDIDATE_SHA, "request_abandoned_candidate_sha")
    require(abandoned.get("state") == "ABANDONED_INVALID_LINEAGE_CANDIDATE", "request_abandoned_state")
    require(abandoned.get("preserve_evidence") is True, "request_abandoned_preservation")
    require(abandoned.get("reuse_prohibited") is True, "request_abandoned_reuse")

    namespaces = request.get("institutional_namespaces", {})
    require(namespaces.get("institutional_phase") == 3, "request_phase")
    require(namespaces.get("phase_transition_authorized") is False, "request_phase_transition")
    require(namespaces.get("os_release_family_after_readback") == "4.x", "request_os_family")
    require(
        namespaces.get("os_4x_effective_only_after_v4_provider_readback") is True,
        "request_os_4x_readback_condition",
    )

    gates = request.get("prepublication_gates")
    require(isinstance(gates, list) and len(gates) == 13, "prepublication_gate_count")
    indexed: dict[str, dict[str, Any]] = {}
    for gate in gates:
        require(isinstance(gate, dict), "prepublication_gate_object")
        gate_id = gate.get("gate_id")
        require(gate_id in EXPECTED_GATE_PREDICATES, f"unexpected_gate:{gate_id}")
        require(gate_id not in indexed, f"duplicate_gate:{gate_id}")
        require(gate.get("predicate") == EXPECTED_GATE_PREDICATES[gate_id], f"gate_predicate:{gate_id}")
        require(gate.get("state") in {"PASS", "HOLD", "UNKNOWN"}, f"gate_state:{gate_id}")
        evidence_refs = gate.get("evidence_refs")
        require(isinstance(evidence_refs, list), f"gate_evidence_refs:{gate_id}")
        if ready:
            require(gate["state"] == "PASS", f"gate_not_pass:{gate_id}")
            require(bool(evidence_refs), f"gate_evidence_missing:{gate_id}")
        indexed[gate_id] = gate
    require(set(indexed) == set(EXPECTED_GATE_PREDICATES), "prepublication_gate_identity")

    artifacts = request.get("artifact_policy", {})
    require(artifacts.get("mode") == "governed_package_and_checksums", "artifact_policy_mode")
    require(artifacts.get("required_assets") == EXPECTED_ASSETS, "artifact_policy_assets")
    controls = request.get("publisher_controls", {})
    for key in (
        "append_only",
        "blind_edit_prohibited",
        "blind_clobber_prohibited",
        "provider_readback_required",
        "downloaded_checksum_verification_required",
        "partial_retry_identity_match_required",
    ):
        require(controls.get(key) is True, f"publisher_control:{key}")

    validate_file_binding(root, request.get("carry_forward_holds", {}), "hold_ledger", ready=ready)
    require(request.get("carry_forward_holds", {}).get("states_promoted") is False, "hold_non_promotion")
    validate_file_binding(root, request.get("rollback_correction", {}), "rollback_correction", ready=ready)

    if ready:
        require(
            isinstance(request.get("idempotency_key"), str) and request["idempotency_key"].strip(),
            "idempotency_key_required",
        )
        parse_time(request.get("requested_at"), "request_requested_at")
        package = root / EXPECTED_PACKAGE
        require((package / "MANIFEST.json").is_file(), "major_manifest_missing")
        require((package / "RELEASE_NOTES.md").is_file(), "major_release_notes_missing")
        manifest = load_json(package / "MANIFEST.json")
        require(manifest.get("version") == EXPECTED_VERSION, "major_manifest_version")
        require(manifest.get("tag") == EXPECTED_TAG, "major_manifest_tag")
        require(manifest.get("target_ref") == "github_event_merge_sha", "major_manifest_target_binding")
        require(manifest.get("institutional_phase") == 3, "major_manifest_phase")
        require(
            manifest.get("os_4x_effective_only_after_v4_provider_readback") is True,
            "major_manifest_os_4x_condition",
        )
    else:
        require(request.get("idempotency_key") is None, "template_idempotency_key_must_be_unassigned")
        require(request.get("requested_at") is None, "template_requested_at_must_be_unassigned")
    validate_no_private_conversation(request)


def parse_approval_body(body: str) -> dict[str, str]:
    require(isinstance(body, str), "approval_body")
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    require(EXPECTED_APPROVAL_MARKER in lines, "approval_marker_missing")
    parsed: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def validate_provider_evidence(
    evidence: dict[str, Any],
    request_sha256: str,
    terms_sha256: str,
    not_before: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    require(evidence.get("repository") == EXPECTED_REPOSITORY, "provider_repository")
    event_name = evidence.get("event_name")
    require(event_name in {"push", "workflow_dispatch"}, "major_event_name")
    if event_name == "push":
        require(evidence.get("event_ref") == "refs/heads/main", "major_event_ref")
        require(isinstance(evidence.get("partial_retry"), bool), "push_retry_state")
    else:
        require(evidence.get("partial_retry") is True, "dispatch_must_be_partial_retry")
    merge_sha = evidence.get("event_sha")
    require(isinstance(merge_sha, str) and GIT_SHA_RE.fullmatch(merge_sha) is not None, "event_merge_sha")

    pull_request = evidence.get("pull_request", {})
    require(pull_request.get("state") == "closed", "provider_pr_state")
    require(pull_request.get("merged") is True, "provider_pr_merged")
    require(pull_request.get("base_ref") == "main", "provider_pr_base")
    require(pull_request.get("merge_commit_sha") == merge_sha, "provider_pr_merge_sha")
    require(pull_request.get("head_repository") == EXPECTED_REPOSITORY, "provider_pr_head_repository")
    merged_at = parse_time(pull_request.get("merged_at"), "provider_pr_merged_at")
    head_sha = pull_request.get("head_sha")
    require(isinstance(head_sha, str) and GIT_SHA_RE.fullmatch(head_sha) is not None, "provider_pr_head_sha")
    require(isinstance(pull_request.get("number"), int) and pull_request["number"] > 0, "provider_pr_number")

    check_runs = evidence.get("check_runs", [])
    require(isinstance(check_runs, list), "provider_check_runs")
    gate_checks = [
        item
        for item in check_runs
        if isinstance(item, dict)
        and item.get("name") == "CrownThrive governed merge gate"
        and item.get("head_sha") == head_sha
        and item.get("status") == "completed"
        and item.get("conclusion") == "success"
    ]
    require(bool(gate_checks), "governed_merge_gate_provider_readback")

    required_checks = evidence.get("required_checks", [])
    require(isinstance(required_checks, list) and required_checks, "provider_required_checks")
    require(
        all(
            isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and item["name"]
            and item.get("state") == "SUCCESS"
            for item in required_checks
        ),
        "provider_required_check_failure",
    )
    require(
        evidence.get("approval_consumption") == "unconsumed_or_same_release_identity",
        "provider_approval_consumption",
    )

    expected_marker_fields = {
        "candidate_head_sha": head_sha,
        "version": EXPECTED_VERSION,
        "tag": EXPECTED_TAG,
        "terms_sha256": terms_sha256,
        "request_sha256": request_sha256,
    }
    valid_approvals: list[dict[str, Any]] = []
    for kind, records in (("review", evidence.get("reviews", [])), ("comment", evidence.get("comments", []))):
        require(isinstance(records, list), f"provider_{kind}s")
        for record in records:
            if not isinstance(record, dict):
                continue
            if record.get("actor_login") != EXPECTED_APPROVER or record.get("author_association") != "OWNER":
                continue
            if record.get("revoked") is not False:
                continue
            if kind == "review" and (
                record.get("state") != "APPROVED"
                or record.get("commit_id") != head_sha
                or record.get("dismissed") is not False
            ):
                continue
            try:
                fields = parse_approval_body(record.get("body", ""))
            except MajorReleaseValidationError:
                continue
            if any(fields.get(key) != value for key, value in expected_marker_fields.items()):
                continue
            approved_at = parse_time(record.get("approved_at"), "provider_approval_time")
            provider_id = str(record.get("provider_id"))
            if not provider_id or provider_id in {"None", "null"}:
                continue
            if not_before <= approved_at <= min(expires_at, merged_at):
                valid_approvals.append(
                    {
                        "kind": kind,
                        "provider_id": provider_id,
                        "approved_at": approved_at.isoformat().replace("+00:00", "Z"),
                    }
                )
    require(bool(valid_approvals), "exact_owner_d3_approval_missing")
    valid_approvals.sort(key=lambda item: (item["approved_at"], item["kind"], item["provider_id"]))
    return {
        "candidate_head_sha": head_sha,
        "merge_commit_sha": merge_sha,
        "pull_request_number": pull_request["number"],
        "approval": valid_approvals[-1],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--terms", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--mode", choices=("template", "ready"), required=True)
    parser.add_argument("--provider-evidence")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.repository_root).resolve()
    request_path = Path(args.request).resolve()
    terms_path = Path(args.terms).resolve()
    request = load_json(request_path)
    terms = load_json(terms_path)
    ready = args.mode == "ready"
    not_before, expires_at = validate_terms(terms, ready=ready)
    terms_sha256 = sha256_file(terms_path)
    request_sha256 = sha256_file(request_path)
    validate_request(root, request, terms_path, terms_sha256, ready=ready)

    result: dict[str, Any] = {
        "schema": "ct.pentarelease.major-validation.v1",
        "version": EXPECTED_VERSION,
        "tag": EXPECTED_TAG,
        "institutional_phase": 3,
        "os_release_family_effect": "4.x_after_verified_v4_provider_readback_only",
        "request_sha256": request_sha256,
        "terms_sha256": terms_sha256,
        "provider_write_authorized": False,
    }
    if ready:
        require(args.provider_evidence is not None, "provider_evidence_required")
        provider = load_json(Path(args.provider_evidence))
        binding = validate_provider_evidence(
            provider,
            request_sha256,
            terms_sha256,
            not_before,
            expires_at,
        )
        result.update(
            {
                "status": "PASS_EXACT_HUMAN_D3_MAJOR_RELEASE",
                "provider_write_authorized": True,
                **binding,
            }
        )
    else:
        require(args.provider_evidence is None, "template_must_not_include_provider_evidence")
        result["status"] = "HOLD_TEMPLATE_UNASSIGNED"

    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MajorReleaseValidationError as exc:
        raise SystemExit(f"HOLD: {exc}") from exc
