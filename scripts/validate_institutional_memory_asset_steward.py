#!/usr/bin/env python3
"""Fail-closed validation for the Institutional Memory & Asset Steward packet.

This validator intentionally uses only the Python standard library. It validates
the bounded public packet and provides a small JSON Schema evaluator for custody
records so the contract can be tested without installing dependencies.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


EXPECTED_FILES = (
    "developers/agent-templates/institutional-memory-asset-steward.agent.template.md",
    "developers/skill-templates/institutional-memory-asset-steward/SKILL.template.md",
    ".github/workflows/institutional-memory-asset-steward.yml",
    "automation/institutional-memory-asset-steward.mdx",
    "developers/manifests/institutional-memory-asset-steward.v1.json",
    "developers/schemas/institutional-asset-custody-record.v1.schema.json",
    "scripts/validate_institutional_memory_asset_steward.py",
    "changelog/phase-2-99-institutional-memory-asset-steward-seed.mdx",
)

EXPECTED_PACKET_FILE_COUNT = 8

EXPECTED_WORKFLOW_PATHS = EXPECTED_FILES + (
    ".github/agents/**",
    "**/SKILL.md",
)

RECOGNIZED_SKILL_ROOTS = (
    ".github/skills",
    ".claude/skills",
    ".agents/skills",
)

STEWARD_SEMANTIC_TERMS = ("institutional", "memory", "asset", "steward")

AGENT_PATH = EXPECTED_FILES[0]
SKILL_PATH = EXPECTED_FILES[1]
WORKFLOW_PATH = EXPECTED_FILES[2]
DOC_PATH = EXPECTED_FILES[3]
MANIFEST_PATH = EXPECTED_FILES[4]
SCHEMA_PATH = EXPECTED_FILES[5]
CHANGELOG_PATH = EXPECTED_FILES[7]

EXPECTED_ROLE_COLLISION_BOUNDARY = {
    "documentation_sentinel": "does_not_replace_drift_detection_or_read_only_evidence_ownership",
    "documentation_steward": "does_not_own_navigation_registry_merge_or_canonical_documentation_approval",
    "platform_registry_agent": "does_not_promote_provider_platform_or_integration_state",
    "evidence_auditor": "does_not_count_as_its_own_independent_verifier",
    "rights_and_governance_agent": "does_not_adjudicate_rights_provenance_license_or_canon",
    "publishing_agent": "does_not_publish_or_release_source_masters_or_products",
    "chief_of_staff_orchestrator": "does_not_self_assign_work_parentage_or_completion_authority",
}

EXPECTED_PROVIDER_PROFILE = {
    "profile_template_path": "developers/agent-templates/institutional-memory-asset-steward.agent.template.md",
    "skill_template_path": "developers/skill-templates/institutional-memory-asset-steward/SKILL.template.md",
    "activation_profile_target_path": ".github/agents/institutional-memory-asset-steward.agent.md",
    "activation_skill_target_path": ".github/skills/institutional-memory-asset-steward/SKILL.md",
    "target": "github-copilot",
    "candidate_templates_present": True,
    "candidate_branch_recognized_profile_present": False,
    "candidate_branch_recognized_skill_present": False,
    "default_branch_profile_present_at_baseline": False,
    "user_invocable": False,
    "model_invocation_disabled": True,
    "tools": ["read", "search"],
    "skill_inertness_basis": "outside_all_recognized_project_skill_roots",
    "skill_template_governance_annotations": {
        "x-crownthrive-user-invocable": False,
        "x-crownthrive-disable-model-invocation": True,
    },
    "skill_allowed_tools": ["read", "search"],
    "programmatic_invocation_authorized": False,
    "provider_capability_is_activation": False,
    "activation_requires_separate_exact_head_installation_change": True,
}

EXPECTED_PARENT_AND_INVENTORY = {
    "operational_parent_agent_id": "ct.relay.agent-a",
    "parent_relationship": "routing_and_orchestration_only_not_vote_or_approval_control",
    "parent_evidence_ref": "developers/manifests/agent-sovereign-governance.v1.json",
    "parent_state": "runtime_readback_verified_pending_inventory_reconciliation",
    "canonical_inventory_ref": "automation/agent-registry.mdx",
    "inventory_source_ref": MANIFEST_PATH,
    "public_agent_registry_entry_state": "pending_ordered_collision_reconciliation_not_registered",
    "runtime_binding_state": "prospective_disabled",
    "runtime_parent_agent_id_state": "ct.relay.agent-a_readback_verified",
    "activation_blocked_until_runtime_parent_and_inventory_verified": True,
}

EXPECTED_TOP_LEVEL_KEYS = {
    "activation_gates",
    "agent_id",
    "authority",
    "custody_topology",
    "documentation",
    "effective_state",
    "identity",
    "manifest_id",
    "manifest_version",
    "mission",
    "observed_at",
    "outputs",
    "packet_inventory",
    "parent_and_inventory",
    "phase",
    "provider_profile",
    "record_contract",
    "role_collision_boundary",
    "rollback",
    "self_healing",
    "source_baseline",
    "source_precedence",
    "state_model",
    "state_separation",
    "validation",
    "visibility",
    "workflow",
}

EXPECTED_LIFECYCLE_OBJECTS = {
    "phase": {
        "current_phase": 2,
        "current_subphase": "2.99",
        "phase_3_entry": "blocked_pending_phase_2_99_hard_exit_and_full_docs_reconciliation",
        "packet_advances_phase": False,
    },
    "identity": {
        "name": "Institutional Memory & Asset Steward",
        "role": "institutional_memory_source_master_lineage_and_custody_preparation",
        "owner_ref": "ct.owner.crownthrive-founding-member",
        "parent_control_plane": "ct.control-plane.crownthrive-institutional",
        "stable_across_provider_changes": True,
        "vote_eligible": False,
    },
    "authority": {
        "autonomy_class": "A1_prepare",
        "default_risk_class": "D1",
        "d0_d1": "deterministic_reversible_public_safe_preparation_only",
        "d2": {
            "may_prepare": True,
            "may_self_approve": False,
            "required": [
                "current_main_and_collision_reconciliation",
                "trusted_exact_changed_file_classification",
                "independent_verifier",
                "applicable_specialist_endorsements",
                "four_of_five_sovereign_approvals",
                "mandatory_agent_d_approval",
                "no_deny_or_block",
                "unchanged_required_controls_pass",
                "rollback_or_recovery_path",
                "documentation_and_downstream_phase_reconciliation",
            ],
        },
        "d3": {
            "permitted": False,
            "authority": "authorized_human_only",
            "prohibited_actions": [
                "legal_terms_or_binding_contract",
                "rights_grant_assignment_or_ownership_change",
                "production_credential_or_privileged_access_change",
                "destructive_or_irreversible_production_change",
                "money_movement_or_material_price_payout_change",
                "privacy_or_security_policy_exception",
                "cross_border_regulatory_activation",
                "public_release_of_restricted_material",
            ],
        },
        "github_or_provider_capability_is_authority": False,
        "quorum_can_override_d3": False,
    },
    "workflow": {
        "mode": "read_inventory_prepare_validate_handoff",
        "provider_mutation_default": "disabled",
        "read_before_write_required": True,
        "provider_readback_required_for_verified_custody": True,
        "idempotency_required_for_future_mutations": True,
        "unknown_outcome_fails_closed": True,
        "routine_private_metrics_committed_to_public_docs": False,
        "collision_check_required": True,
        "exact_head_review_required": True,
    },
    "self_healing": {
        "enabled_for": ["D0", "D1"],
        "default_mode": "detect_preserve_evidence_bounded_repair_rerun_original_gate_full_suite_independent_verify",
        "same_failure_requires_new_evidence_or_root_cause_reassessment": True,
        "validator_or_security_weakening_prohibited": True,
        "secret_reconstruction_prohibited": True,
        "master_deletion_or_replacement_prohibited": True,
        "self_approval_prohibited": True,
        "phase_promotion_prohibited": True,
    },
    "custody_topology": {
        "google_drive": {
            "service_id": "ct.service.google-drive",
            "role": "durable_human_operable_source_and_distribution_custody",
            "write_enabled_by_this_packet": False,
            "public_projection": "stable_identity_evidence_state_and_reference_digest_only",
            "forbidden_public_fields": [
                "private_folder_id",
                "private_file_id",
                "private_path",
                "signed_url",
            ],
        },
        "thivebase": {
            "service_id": "ct.service.thivebase",
            "role": "canonical_identity_digest_relationship_state_evidence_and_run_registry",
            "write_enabled_by_this_packet": False,
            "public_projection": "logical_contract_only",
            "forbidden_public_fields": [
                "service_role_secret",
                "private_schema_ddl",
                "private_project_id",
                "restricted_evidence_body",
            ],
        },
        "supabase_storage": {
            "service_id": "ct.service.supabase-storage",
            "role": "optional_private_binary_parity_and_controlled_delivery",
            "write_enabled_by_this_packet": False,
            "public_projection": "verification_state_and_digest_only",
            "forbidden_public_fields": [
                "bucket_internal_id",
                "object_path",
                "signed_url",
                "access_token",
            ],
        },
        "github": {
            "service_id": "ct.repository.crownthrive-support",
            "role": "versioned_public_safe_contract_schema_validator_and_correction_history",
            "write_enabled_by_this_packet": False,
            "raw_masters_allowed": False,
            "secrets_allowed": False,
        },
        "mintlify": {
            "service_id": "ct.documentation.crown-thrive",
            "role": "searchable_public_safe_institutional_projection",
            "write_enabled_by_this_packet": False,
            "documentation_proves_runtime": False,
        },
    },
    "documentation": {
        "operating_page": DOC_PATH,
        "checkpoint": CHANGELOG_PATH,
        "hidden": True,
        "noindex": True,
        "docs_json_changed_by_this_packet": False,
        "docs_impact": "docs_delta_prepared_hidden_not_canonical",
    },
    "validation": {
        "workflow": WORKFLOW_PATH,
        "self_test_required": True,
        "institutional_docs_validation_required": True,
        "agent_governance_validation_required": True,
        "github_actions_runtime_policy_required": True,
        "all_remote_actions_full_commit_sha_pinned": True,
        "target_github_actions_runtime": "node24",
    },
}

EXPECTED_ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
}

EXPECTED_ACTION_VERSIONS = {
    "actions/checkout": "v7.0.1",
    "actions/setup-python": "v7",
}

CT_ID = re.compile(r"^ct\.[a-z0-9][a-z0-9._-]*$")
RECORD_ID = re.compile(r"^ct\.memory\.asset\.[a-z0-9][a-z0-9._-]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|service[_-]?role[_-]?key|"
        r"client[_-]?secret|password)\b\s*[:=]\s*['\"][A-Za-z0-9+/_.=-]{12,}['\"]"
    ),
)

PRIVATE_LOCATOR_PATTERNS = (
    re.compile(
        r"(?i)https?://(?:drive|docs)\.google\.com/(?:"
        r"file/d/|drive/(?:u/\d+/)?folders/|document/d/|spreadsheets/d/|"
        r"presentation/d/|open\?id=)[A-Za-z0-9_-]{10,}"
    ),
    re.compile(r"(?i)https?://[a-z0-9-]+\.supabase\.co/storage/v1/object/"),
    re.compile(r"(?i)\bsupabase(?:_storage)?://\S+"),
    re.compile(
        r"(?i)\b(?:private[_-]?)?(?:drive[_-]?)?(?:file|folder|object|bucket|project)"
        r"[_-]?id\s*[:=]\s*['\"]?[A-Za-z0-9_-]{10,}"
    ),
    re.compile(r"(?i)\bobject[_-]?path\s*[:=]\s*['\"]?[^\s'\"]{3,}"),
    re.compile(
        r"(?i)(?:[?&](?:token|sig|signature|x-amz-signature|x-amz-credential|apikey)="
        r"[A-Za-z0-9%+/_=-]{8,})"
    ),
)


def add_error(errors: list[str], message: str) -> None:
    errors.append(message)


def read_text(root: Path, relative_path: str, errors: list[str]) -> str:
    path = root / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        add_error(errors, f"{relative_path}: cannot read UTF-8 text: {exc}")
        return ""


def load_json(root: Path, relative_path: str, errors: list[str]) -> dict[str, Any]:
    text = read_text(root, relative_path, errors)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        add_error(errors, f"{relative_path}: invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        add_error(errors, f"{relative_path}: top-level value must be an object")
        return {}
    return value


def scalar_frontmatter(text: str, relative_path: str, errors: list[str]) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        add_error(errors, f"{relative_path}: missing opening YAML frontmatter delimiter")
        return {}
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        add_error(errors, f"{relative_path}: missing closing YAML frontmatter delimiter")
        return {}

    result: dict[str, str] = {}
    for line in lines[1:end]:
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        result[key.strip()] = raw_value.strip().strip("'\"")
    return result


def require_equal(
    errors: list[str], actual: Any, expected: Any, location: str
) -> None:
    if actual != expected:
        add_error(errors, f"{location}: expected {expected!r}, found {actual!r}")


def nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def validate_required_files(root: Path, errors: list[str]) -> None:
    if (
        len(EXPECTED_FILES) != EXPECTED_PACKET_FILE_COUNT
        or len(set(EXPECTED_FILES)) != EXPECTED_PACKET_FILE_COUNT
    ):
        add_error(errors, "packet inventory: EXPECTED_FILES must contain exactly eight unique paths")

    for relative_path in EXPECTED_FILES:
        path = root / relative_path
        if not path.is_file():
            add_error(errors, f"{relative_path}: required packet file is missing")

    # In the standalone packet, these shared or private surfaces must not be
    # bundled. In a full repository they may already exist, so their absence is
    # instead enforced by the packet manifest and workflow path set.
    if not (root / "AGENTS.md").exists():
        actual_files = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        expected_files = set(EXPECTED_FILES)
        if actual_files != expected_files:
            unexpected = sorted(actual_files - expected_files)
            missing = sorted(expected_files - actual_files)
            add_error(
                errors,
                f"packet inventory: exact standalone surface mismatch; unexpected={unexpected!r}, missing={missing!r}",
            )
        if (root / "docs.json").exists():
            add_error(errors, "docs.json: shared navigation must not be in the bounded packet")
        migrations = root / "supabase" / "migrations"
        if migrations.exists():
            add_error(errors, "supabase/migrations: private implementation is outside this packet")

    validate_recognized_installations(root, errors)


def validate_recognized_installations(root: Path, errors: list[str]) -> None:
    agents_root = root / ".github" / "agents"
    if agents_root.exists():
        for path in agents_root.rglob("*.md"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            semantic_fingerprint = all(
                re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE)
                for term in STEWARD_SEMANTIC_TERMS
            )
            if (
                "ct.agent.institutional-memory-asset-steward" in text
                or semantic_fingerprint
            ):
                add_error(
                    errors,
                    f"{path.relative_to(root)}: recognized provider profile for the inert steward is forbidden",
                )

    for relative_root in RECOGNIZED_SKILL_ROOTS:
        skills_root = root / relative_root
        if not skills_root.exists():
            continue
        for path in skills_root.rglob("SKILL.md"):
            if not path.is_file():
                continue
            skill_errors: list[str] = []
            text = read_text(root, path.relative_to(root).as_posix(), skill_errors)
            errors.extend(skill_errors)
            frontmatter = scalar_frontmatter(text, path.relative_to(root).as_posix(), errors)
            semantic_fingerprint = all(
                re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE)
                for term in STEWARD_SEMANTIC_TERMS
            )
            if (
                frontmatter.get("name") == "institutional-memory-asset-steward"
                or semantic_fingerprint
            ):
                add_error(
                    errors,
                    f"{path.relative_to(root)}: recognized provider skill for the inert steward is forbidden",
                )


def validate_frontmatter(root: Path, errors: list[str]) -> None:
    agent_text = read_text(root, AGENT_PATH, errors)
    agent = scalar_frontmatter(agent_text, AGENT_PATH, errors)
    require_equal(errors, agent.get("name"), "Institutional Memory & Asset Steward", f"{AGENT_PATH}: name")
    require_equal(errors, agent.get("target"), "github-copilot", f"{AGENT_PATH}: target")
    require_equal(errors, agent.get("user-invocable"), "false", f"{AGENT_PATH}: user-invocable")
    require_equal(errors, agent.get("disable-model-invocation"), "true", f"{AGENT_PATH}: disable-model-invocation")
    if not re.search(r"(?m)^\s+institutional-id:\s+ct\.agent\.institutional-memory-asset-steward\s*$", agent_text):
        add_error(errors, f"{AGENT_PATH}: stable institutional ID is missing")
    if not re.search(r"(?m)^\s+vote-eligible:\s+['\"]?false['\"]?\s*$", agent_text):
        add_error(errors, f"{AGENT_PATH}: agent must be explicitly non-voting")
    tools_line = re.sub(r"\s+", "", agent.get("tools", "")).lower()
    require_equal(errors, tools_line, '["read","search"]', f"{AGENT_PATH}: tools")

    skill_text = read_text(root, SKILL_PATH, errors)
    skill = scalar_frontmatter(skill_text, SKILL_PATH, errors)
    require_equal(
        errors,
        skill.get("name"),
        "institutional-memory-asset-steward",
        f"{SKILL_PATH}: name",
    )
    if not skill.get("description"):
        add_error(errors, f"{SKILL_PATH}: triggering description is required")
    require_equal(errors, skill.get("x-crownthrive-user-invocable"), "false", f"{SKILL_PATH}: x-crownthrive-user-invocable")
    require_equal(errors, skill.get("x-crownthrive-disable-model-invocation"), "true", f"{SKILL_PATH}: x-crownthrive-disable-model-invocation")
    skill_tools = re.sub(r"\s+", "", skill.get("allowed-tools", "")).lower()
    require_equal(errors, skill_tools, '["read","search"]', f"{SKILL_PATH}: allowed-tools")
    if "provider writes" not in skill_text.lower() and "provider mutation" not in skill_text.lower():
        add_error(errors, f"{SKILL_PATH}: provider-write boundary is not explicit")
    for phrase in ("non-voting", "A1", "D1", "D2", "D3"):
        if phrase not in skill_text:
            add_error(errors, f"{SKILL_PATH}: governance phrase {phrase!r} is missing")

    for relative_path in (DOC_PATH, CHANGELOG_PATH):
        text = read_text(root, relative_path, errors)
        frontmatter = scalar_frontmatter(text, relative_path, errors)
        require_equal(errors, frontmatter.get("hidden"), "true", f"{relative_path}: hidden")
        require_equal(errors, frontmatter.get("noindex"), "true", f"{relative_path}: noindex")


def validate_manifest_data(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    checks = (
        (manifest.get("manifest_version"), "1.0.0", "manifest_version"),
        (manifest.get("manifest_id"), "ct.manifest.institutional-memory-asset-steward.v1", "manifest_id"),
        (manifest.get("agent_id"), "ct.agent.institutional-memory-asset-steward", "agent_id"),
        (manifest.get("effective_state"), "candidate_public_packet_not_activated", "effective_state"),
        (manifest.get("visibility"), "PUBLIC_STANDARD", "visibility"),
        (nested(manifest, "packet_inventory", "file_count"), 8, "packet_inventory.file_count"),
        (nested(manifest, "packet_inventory", "files"), list(EXPECTED_FILES), "packet_inventory.files"),
        (nested(manifest, "source_baseline", "repository"), "crownthrive1/CrownThrive-Support", "source_baseline.repository"),
        (nested(manifest, "source_baseline", "branch"), "main", "source_baseline.branch"),
        (nested(manifest, "source_baseline", "mintlify_deploy_branch"), "main", "source_baseline.mintlify_deploy_branch"),
        (nested(manifest, "phase", "current_subphase"), "2.99", "phase.current_subphase"),
        (nested(manifest, "phase", "packet_advances_phase"), False, "phase.packet_advances_phase"),
        (nested(manifest, "identity", "parent_control_plane"), "ct.control-plane.crownthrive-institutional", "identity.parent_control_plane"),
        (nested(manifest, "identity", "vote_eligible"), False, "identity.vote_eligible"),
        (nested(manifest, "authority", "autonomy_class"), "A1_prepare", "authority.autonomy_class"),
        (nested(manifest, "authority", "default_risk_class"), "D1", "authority.default_risk_class"),
        (nested(manifest, "authority", "d2", "may_prepare"), True, "authority.d2.may_prepare"),
        (nested(manifest, "authority", "d2", "may_self_approve"), False, "authority.d2.may_self_approve"),
        (nested(manifest, "authority", "d3", "permitted"), False, "authority.d3.permitted"),
        (nested(manifest, "authority", "d3", "authority"), "authorized_human_only", "authority.d3.authority"),
        (nested(manifest, "authority", "github_or_provider_capability_is_authority"), False, "authority.github_or_provider_capability_is_authority"),
        (nested(manifest, "authority", "quorum_can_override_d3"), False, "authority.quorum_can_override_d3"),
        (nested(manifest, "record_contract", "schema_path"), SCHEMA_PATH, "record_contract.schema_path"),
        (nested(manifest, "record_contract", "validator_path"), EXPECTED_FILES[6], "record_contract.validator_path"),
        (nested(manifest, "record_contract", "raw_secret_fields_permitted"), False, "record_contract.raw_secret_fields_permitted"),
        (nested(manifest, "record_contract", "raw_private_locator_fields_permitted"), False, "record_contract.raw_private_locator_fields_permitted"),
        (nested(manifest, "workflow", "provider_mutation_default"), "disabled", "workflow.provider_mutation_default"),
        (nested(manifest, "workflow", "mode"), "read_inventory_prepare_validate_handoff", "workflow.mode"),
        (nested(manifest, "documentation", "operating_page"), DOC_PATH, "documentation.operating_page"),
        (nested(manifest, "documentation", "checkpoint"), CHANGELOG_PATH, "documentation.checkpoint"),
        (nested(manifest, "documentation", "hidden"), True, "documentation.hidden"),
        (nested(manifest, "documentation", "noindex"), True, "documentation.noindex"),
        (nested(manifest, "documentation", "docs_json_changed_by_this_packet"), False, "documentation.docs_json_changed_by_this_packet"),
        (nested(manifest, "validation", "workflow"), WORKFLOW_PATH, "validation.workflow"),
        (nested(manifest, "validation", "self_test_required"), True, "validation.self_test_required"),
        (nested(manifest, "validation", "all_remote_actions_full_commit_sha_pinned"), True, "validation.all_remote_actions_full_commit_sha_pinned"),
        (nested(manifest, "validation", "target_github_actions_runtime"), "node24", "validation.target_github_actions_runtime"),
    )
    for actual, expected, location in checks:
        require_equal(errors, actual, expected, f"{MANIFEST_PATH}: {location}")

    require_equal(
        errors,
        set(manifest),
        EXPECTED_TOP_LEVEL_KEYS,
        f"{MANIFEST_PATH}: top-level keys",
    )
    for object_name, expected_object in EXPECTED_LIFECYCLE_OBJECTS.items():
        require_equal(
            errors,
            manifest.get(object_name),
            expected_object,
            f"{MANIFEST_PATH}: {object_name}",
        )

    require_equal(
        errors,
        manifest.get("provider_profile"),
        EXPECTED_PROVIDER_PROFILE,
        f"{MANIFEST_PATH}: provider_profile",
    )
    require_equal(
        errors,
        manifest.get("parent_and_inventory"),
        EXPECTED_PARENT_AND_INVENTORY,
        f"{MANIFEST_PATH}: parent_and_inventory",
    )

    baseline_commit = nested(manifest, "source_baseline", "commit")
    if not isinstance(baseline_commit, str) or not FULL_COMMIT_SHA.fullmatch(baseline_commit):
        add_error(errors, f"{MANIFEST_PATH}: source_baseline.commit must be a full commit SHA")

    required_d2 = set(nested(manifest, "authority", "d2", "required") or [])
    for gate in (
        "independent_verifier",
        "four_of_five_sovereign_approvals",
        "mandatory_agent_d_approval",
        "no_deny_or_block",
        "rollback_or_recovery_path",
    ):
        if gate not in required_d2:
            add_error(errors, f"{MANIFEST_PATH}: authority.d2.required lacks {gate!r}")

    expected_activation_gates = {
        "exact_head_governance_acceptance",
        "public_restricted_ip_classification",
        "canonical_parent_and_inventory_binding",
        "role_collision_boundary_acceptance",
        "separate_profile_and_skill_installation_activation_change",
        "private_runtime_implementation_packet",
        "least_privilege_secret_references_outside_public_files",
        "read_before_write_and_readback_controls",
        "adversarial_and_recovery_test_fixtures",
        "registered_owner_budget_rate_limit_retention_backup_and_vendor_exit",
        "collision_safe_navigation_and_agent_registry_reconciliation",
    }
    activation_gate_list = manifest.get("activation_gates") or []
    if (
        not isinstance(activation_gate_list, list)
        or len(activation_gate_list) != len(expected_activation_gates)
        or set(activation_gate_list) != expected_activation_gates
    ):
        add_error(errors, f"{MANIFEST_PATH}: activation_gates must exactly match the fail-closed gate set")

    require_equal(
        errors,
        manifest.get("role_collision_boundary"),
        EXPECTED_ROLE_COLLISION_BOUNDARY,
        f"{MANIFEST_PATH}: role_collision_boundary",
    )

    expected_rollback = {
        "public_packet": "revert_the_eight_additive_paths",
        "github_templates": "revert_the_uninstalled_templates; no_recognized_agent_or_skill_path_exists_in_this_candidate",
        "prospective_runtime_binding": "retain_as_disabled_history_or_retire_remove_through_governed_D1_runtime_reconciliation_if_candidate_is_abandoned",
        "provider_rollback": "no_provider_write_capability_was_enabled_but_external_prospective_binding_requires_explicit_reconciliation",
        "evidence_preservation_required": True,
    }
    require_equal(errors, manifest.get("rollback"), expected_rollback, f"{MANIFEST_PATH}: rollback")

    topology = manifest.get("custody_topology")
    expected_planes = {"google_drive", "thivebase", "supabase_storage", "github", "mintlify"}
    if not isinstance(topology, dict):
        add_error(errors, f"{MANIFEST_PATH}: custody_topology must be an object")
    else:
        for plane in sorted(expected_planes):
            entry = topology.get(plane)
            if not isinstance(entry, dict):
                add_error(errors, f"{MANIFEST_PATH}: custody_topology.{plane} is required")
            elif entry.get("write_enabled_by_this_packet") is not False:
                add_error(errors, f"{MANIFEST_PATH}: custody_topology.{plane}.write_enabled_by_this_packet must be false")
        github = topology.get("github", {})
        if github.get("raw_masters_allowed") is not False:
            add_error(errors, f"{MANIFEST_PATH}: custody_topology.github.raw_masters_allowed must be false")
        if github.get("secrets_allowed") is not False:
            add_error(errors, f"{MANIFEST_PATH}: custody_topology.github.secrets_allowed must be false")

    return errors


def walk_property_names(schema: Any) -> Iterable[str]:
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            yield from properties.keys()
        for value in schema.values():
            yield from walk_property_names(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from walk_property_names(value)


def validate_schema_contract(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    require_equal(errors, schema.get("$schema"), "https://json-schema.org/draft/2020-12/schema", f"{SCHEMA_PATH}: $schema")
    require_equal(errors, schema.get("$id"), "urn:crownthrive:schema:institutional-asset-custody-record:v1", f"{SCHEMA_PATH}: $id")
    require_equal(errors, schema.get("type"), "object", f"{SCHEMA_PATH}: type")
    require_equal(errors, schema.get("additionalProperties"), False, f"{SCHEMA_PATH}: additionalProperties")

    required = set(schema.get("required", []))
    for field in (
        "record_id",
        "asset_id",
        "asset_kind",
        "visibility",
        "lifecycle_state",
        "implementation_state",
        "evidence_state",
        "custody_state",
        "rights_state",
        "commerce_state",
        "release_state",
        "source_records",
        "versions",
        "custody_bindings",
        "docs_impact",
    ):
        if field not in required:
            add_error(errors, f"{SCHEMA_PATH}: required lacks {field!r}")

    definitions = schema.get("$defs")
    for name in ("sourceRecord", "versionRecord", "custodyBinding", "relationship", "evidenceRef", "unknownRecord"):
        definition = definitions.get(name) if isinstance(definitions, dict) else None
        if not isinstance(definition, dict):
            add_error(errors, f"{SCHEMA_PATH}: $defs.{name} is required")
        elif definition.get("additionalProperties") is not False:
            add_error(errors, f"{SCHEMA_PATH}: $defs.{name}.additionalProperties must be false")

    require_equal(
        errors,
        nested(
            schema,
            "$defs",
            "sourceRecord",
            "properties",
            "public_reference",
            "x-crownthrive-private-provider-locators",
        ),
        "prohibited",
        f"{SCHEMA_PATH}: public_reference private-provider-locator policy",
    )

    forbidden_exact = {
        "api_key",
        "access_token",
        "refresh_token",
        "service_role_key",
        "client_secret",
        "password",
        "private_key",
        "signed_url",
        "private_file_id",
        "private_folder_id",
        "bucket_id",
        "object_path",
        "project_id",
    }
    for property_name in walk_property_names(schema):
        if property_name.lower() in forbidden_exact:
            add_error(errors, f"{SCHEMA_PATH}: forbidden public field {property_name!r}")
    return errors


def valid_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "null":
        return value is None
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def validate_instance(
    value: Any,
    node: dict[str, Any],
    root_schema: dict[str, Any],
    location: str,
    errors: list[str],
) -> None:
    reference = node.get("$ref")
    if isinstance(reference, str):
        prefix = "#/$defs/"
        if not reference.startswith(prefix):
            add_error(errors, f"{location}: unsupported schema reference {reference!r}")
            return
        definition = nested(root_schema, "$defs", reference[len(prefix):])
        if not isinstance(definition, dict):
            add_error(errors, f"{location}: unresolved schema reference {reference!r}")
            return
        validate_instance(value, definition, root_schema, location, errors)
        return

    expected_type = node.get("type")
    if isinstance(expected_type, str) and not type_matches(value, expected_type):
        add_error(errors, f"{location}: expected type {expected_type}, found {type(value).__name__}")
        return
    if isinstance(expected_type, list) and not any(
        isinstance(item, str) and type_matches(value, item) for item in expected_type
    ):
        add_error(errors, f"{location}: expected one of types {expected_type!r}")
        return

    if "const" in node and value != node["const"]:
        add_error(errors, f"{location}: value does not match const {node['const']!r}")
    if "enum" in node and value not in node["enum"]:
        add_error(errors, f"{location}: value {value!r} is not in the allowed enum")

    if isinstance(value, dict):
        properties = node.get("properties", {})
        required = node.get("required", [])
        for key in required:
            if key not in value:
                add_error(errors, f"{location}.{key}: required property is missing")
        if node.get("additionalProperties") is False and isinstance(properties, dict):
            for key in value:
                if key not in properties:
                    add_error(errors, f"{location}.{key}: additional property is forbidden")
        if isinstance(properties, dict):
            for key, child in properties.items():
                if key in value and isinstance(child, dict):
                    validate_instance(value[key], child, root_schema, f"{location}.{key}", errors)

    if isinstance(value, list):
        minimum = node.get("minItems")
        if isinstance(minimum, int) and len(value) < minimum:
            add_error(errors, f"{location}: requires at least {minimum} item(s)")
        if node.get("uniqueItems") is True:
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(set(encoded)) != len(encoded):
                add_error(errors, f"{location}: items must be unique")
        child = node.get("items")
        if isinstance(child, dict):
            for index, item in enumerate(value):
                validate_instance(item, child, root_schema, f"{location}[{index}]", errors)

    if isinstance(value, str):
        minimum = node.get("minLength")
        maximum = node.get("maxLength")
        if isinstance(minimum, int) and len(value) < minimum:
            add_error(errors, f"{location}: string is shorter than {minimum}")
        if isinstance(maximum, int) and len(value) > maximum:
            add_error(errors, f"{location}: string is longer than {maximum}")
        pattern = node.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            add_error(errors, f"{location}: value does not match {pattern!r}")
        if node.get("format") == "date-time" and not valid_datetime(value):
            add_error(errors, f"{location}: invalid RFC 3339 date-time")

    if isinstance(value, int) and not isinstance(value, bool):
        minimum = node.get("minimum")
        maximum = node.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            add_error(errors, f"{location}: value is below minimum {minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            add_error(errors, f"{location}: value is above maximum {maximum}")


def validate_record_semantics(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    versions = record.get("versions", [])
    if isinstance(versions, list):
        for index, version in enumerate(versions):
            if not isinstance(version, dict):
                continue
            if version.get("digest_state") == "verified" and not (
                isinstance(version.get("sha256"), str) and SHA256.fullmatch(version["sha256"])
            ):
                add_error(errors, f"record.versions[{index}]: verified digest requires SHA-256")

    bindings = record.get("custody_bindings", [])
    verified: dict[str, dict[str, Any]] = {}
    if isinstance(bindings, list):
        for index, binding in enumerate(bindings):
            if not isinstance(binding, dict):
                continue
            state = binding.get("verification_state")
            provider = binding.get("provider")
            if state in {"read_verified", "digest_verified"} and isinstance(provider, str):
                verified[provider] = binding
                if not binding.get("evidence_ref"):
                    add_error(errors, f"record.custody_bindings[{index}]: verified custody requires evidence_ref")
                if binding.get("reference_class") == "private_reference_digest" and not (
                    isinstance(binding.get("reference_digest"), str)
                    and SHA256.fullmatch(binding["reference_digest"])
                ):
                    add_error(errors, f"record.custody_bindings[{index}]: private reference requires a digest")

    state = record.get("custody_state")
    if state == "drive_read_verified" and "google_drive" not in verified:
        add_error(errors, "record.custody_state: drive_read_verified requires verified google_drive readback")
    if state == "drive_and_registry_verified":
        for provider in ("google_drive", "thivebase_registry"):
            if provider not in verified:
                add_error(errors, f"record.custody_state: drive_and_registry_verified requires verified {provider}")
    if state == "dual_verified":
        for provider in ("google_drive", "thivebase_registry", "supabase_storage"):
            if provider not in verified:
                add_error(errors, f"record.custody_state: dual_verified requires verified {provider}")
        storage = verified.get("supabase_storage")
        if storage and storage.get("verification_state") != "digest_verified":
            add_error(errors, "record.custody_state: dual_verified requires Supabase binary digest parity")

    unknowns = record.get("unknowns", [])
    if isinstance(unknowns, list):
        for index, unknown in enumerate(unknowns):
            if isinstance(unknown, dict) and (
                not unknown.get("owner_ref") or not unknown.get("reopen_trigger")
            ):
                add_error(errors, f"record.unknowns[{index}]: unknown requires owner and reopen trigger")
    return errors


def iter_record_strings(value: Any, location: str = "record") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_record_strings(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_record_strings(child, f"{location}[{index}]")
    elif isinstance(value, str):
        yield location, value


def validate_public_safe_record_values(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for location, value in iter_record_strings(record):
        if any(pattern.search(value) for pattern in SECRET_PATTERNS):
            add_error(errors, f"{location}: credential-like value is forbidden")
        if any(pattern.search(value) for pattern in PRIVATE_LOCATOR_PATTERNS):
            add_error(errors, f"{location}: private provider locator is forbidden")
    return errors


def validate_record(record: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    validate_instance(record, schema, schema, "record", errors)
    errors.extend(validate_record_semantics(record))
    errors.extend(validate_public_safe_record_values(record))
    return errors


def validate_workflow(root: Path, errors: list[str]) -> None:
    text = read_text(root, WORKFLOW_PATH, errors)
    if not re.search(r"(?ms)^permissions:\s*\n\s+contents:\s+read\s*$", text):
        add_error(errors, f"{WORKFLOW_PATH}: top-level contents: read permission is required")
    if re.search(r"(?m)^\s+[A-Za-z0-9_-]+:\s+write\s*$", text):
        add_error(errors, f"{WORKFLOW_PATH}: write permissions are forbidden")
    if "${{ secrets." in text:
        add_error(errors, f"{WORKFLOW_PATH}: secret context is forbidden")

    found_actions: dict[str, str] = {}
    for action, reference in re.findall(r"(?m)^\s*uses:\s*([^@\s]+)@([^\s#]+)", text):
        if not FULL_COMMIT_SHA.fullmatch(reference):
            add_error(errors, f"{WORKFLOW_PATH}: {action} must use a full immutable commit SHA")
        found_actions[action] = reference
    for action, expected_sha in EXPECTED_ACTIONS.items():
        require_equal(errors, found_actions.get(action), expected_sha, f"{WORKFLOW_PATH}: {action}")
        expected_version = EXPECTED_ACTION_VERSIONS[action]
        expected_line = f"uses: {action}@{expected_sha} # {expected_version}"
        if expected_line not in text:
            add_error(
                errors,
                f"{WORKFLOW_PATH}: {action} must retain version comment {expected_version}",
            )

    workflow_lines = text.splitlines()
    path_blocks: list[list[str]] = []
    for index, line in enumerate(workflow_lines):
        if line != "    paths:":
            continue
        paths: list[str] = []
        cursor = index + 1
        while cursor < len(workflow_lines) and workflow_lines[cursor].startswith("      - "):
            match = re.fullmatch(r'      - "([^"]+)"', workflow_lines[cursor])
            if not match:
                add_error(errors, f"{WORKFLOW_PATH}: malformed path filter line {workflow_lines[cursor]!r}")
                break
            paths.append(match.group(1))
            cursor += 1
        path_blocks.append(paths)

    if len(path_blocks) != 2:
        add_error(errors, f"{WORKFLOW_PATH}: expected exactly two paths blocks, found {len(path_blocks)}")
    for index, paths in enumerate(path_blocks):
        require_equal(
            errors,
            paths,
            list(EXPECTED_WORKFLOW_PATHS),
            f"{WORKFLOW_PATH}: paths block {index + 1}",
        )

    required_commands = (
        "python -m py_compile scripts/validate_institutional_memory_asset_steward.py",
        "python scripts/validate_institutional_memory_asset_steward.py --self-test",
        "python scripts/validate_institutional_memory_asset_steward.py",
        "python scripts/validate_docs.py",
        "python scripts/validate_agent_sovereign_governance.py",
        "python scripts/validate_github_actions_runtime_policy.py",
    )
    for command in required_commands:
        if command not in text:
            add_error(errors, f"{WORKFLOW_PATH}: required command missing: {command}")

    forbidden_commands = (
        r"\bgit\s+push\b",
        r"\bgh\s+pr\s+(?:create|merge|close|edit)\b",
        r"\bsupabase\s+(?:db\s+push|migration\s+up|functions\s+deploy|secrets\s+set)\b",
        r"\bcurl\b[^\n]*\s-X\s*(?:POST|PUT|PATCH|DELETE)\b",
    )
    for pattern in forbidden_commands:
        if re.search(pattern, text, flags=re.IGNORECASE):
            add_error(errors, f"{WORKFLOW_PATH}: provider mutation command is forbidden")


def validate_secret_absence(root: Path, errors: list[str]) -> None:
    for relative_path in EXPECTED_FILES:
        path = root / relative_path
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                add_error(errors, f"{relative_path}:{line}: credential-like material is forbidden")
        for pattern in PRIVATE_LOCATOR_PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                add_error(errors, f"{relative_path}:{line}: private provider locator is forbidden")


def validate_packet(root: Path) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    validate_required_files(root, errors)
    validate_frontmatter(root, errors)
    manifest = load_json(root, MANIFEST_PATH, errors)
    schema = load_json(root, SCHEMA_PATH, errors)
    if manifest:
        errors.extend(validate_manifest_data(manifest))
    if schema:
        errors.extend(validate_schema_contract(schema))
    validate_workflow(root, errors)
    validate_secret_absence(root, errors)
    return errors, manifest, schema


def sample_binding(provider: str, state: str = "digest_verified") -> dict[str, Any]:
    return {
        "provider": provider,
        "service_id": f"ct.service.{provider.replace('_', '-')}",
        "reference_class": "private_reference_digest",
        "reference_digest": "a" * 64,
        "verification_state": state,
        "observed_at": "2026-08-20T19:05:50Z",
        "evidence_ref": f"ct.evidence.{provider.replace('_', '-')}.readback",
    }


def valid_sample_record() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "record_id": "ct.memory.asset.sample-source-master",
        "asset_id": "ct.asset.sample-source-master",
        "asset_kind": "editable_source_master",
        "canonical_name": "Sample governed source master",
        "owner_ref": "ct.owner.sample-steward",
        "visibility": "restricted",
        "lifecycle_state": "held",
        "implementation_state": "prepared",
        "evidence_state": "verified",
        "custody_state": "drive_and_registry_verified",
        "rights_state": "pending_validation",
        "commerce_state": "not_applicable",
        "release_state": "not_applicable",
        "source_records": [
            {
                "source_id": "ct.source.sample-attestation",
                "source_class": "founder_attestation",
                "authority_rank": 4,
                "state": "available",
                "observed_at": "2026-08-20T19:05:50Z",
                "sha256": "b" * 64,
                "public_reference": None,
            }
        ],
        "versions": [
            {
                "version_id": "ct.version.sample-source-master.v1",
                "version_label": "v1",
                "digest_state": "verified",
                "sha256": "c" * 64,
                "media_type": "application/octet-stream",
                "byte_size": 1,
                "source_master": True,
                "distribution_file": False,
                "supersedes_version_id": None,
            }
        ],
        "custody_bindings": [
            sample_binding("google_drive", "read_verified"),
            sample_binding("thivebase_registry", "read_verified"),
        ],
        "unknowns": [
            {
                "field": "rights_scope",
                "state": "specialist_review_required",
                "reason": "Rights scope requires independent evidence.",
                "owner_ref": "ct.owner.rights-review",
                "reopen_trigger": "Approved rights evidence is registered.",
            }
        ],
        "observed_at": "2026-08-20T19:05:50Z",
        "docs_impact": "docs_delta_opened",
    }


def expect_failure(name: str, errors: list[str], self_test_errors: list[str]) -> None:
    if not errors:
        add_error(self_test_errors, f"self-test {name}: unsafe mutation was not rejected")


def run_self_test(
    packet_errors: list[str], manifest: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if packet_errors:
        errors.append("self-test prerequisite: packet validation failed")
        return errors

    valid_record = valid_sample_record()
    valid_errors = validate_record(valid_record, schema)
    if valid_errors:
        errors.extend(f"self-test valid record: {error}" for error in valid_errors)

    dual_without_storage = copy.deepcopy(valid_record)
    dual_without_storage["custody_state"] = "dual_verified"
    expect_failure(
        "dual custody without storage parity",
        validate_record(dual_without_storage, schema),
        errors,
    )

    vote_mutation = copy.deepcopy(manifest)
    vote_mutation["identity"]["vote_eligible"] = True
    expect_failure("vote eligibility escalation", validate_manifest_data(vote_mutation), errors)

    phase_promotion = copy.deepcopy(manifest)
    phase_promotion["phase"]["current_phase"] = 3
    phase_promotion["phase"]["phase_3_entry"] = "approved"
    expect_failure("phase promotion", validate_manifest_data(phase_promotion), errors)

    d3_mutation = copy.deepcopy(manifest)
    d3_mutation["authority"]["d3"]["permitted"] = True
    expect_failure("D3 escalation", validate_manifest_data(d3_mutation), errors)

    provider_mutation = copy.deepcopy(manifest)
    provider_mutation["custody_topology"]["google_drive"]["write_enabled_by_this_packet"] = True
    expect_failure("provider write escalation", validate_manifest_data(provider_mutation), errors)

    user_invocation = copy.deepcopy(manifest)
    user_invocation["provider_profile"]["user_invocable"] = True
    expect_failure("user invocation escalation", validate_manifest_data(user_invocation), errors)

    model_invocation = copy.deepcopy(manifest)
    model_invocation["provider_profile"]["model_invocation_disabled"] = False
    expect_failure("model invocation escalation", validate_manifest_data(model_invocation), errors)

    edit_tool = copy.deepcopy(manifest)
    edit_tool["provider_profile"]["tools"].append("edit")
    expect_failure("agent edit tool escalation", validate_manifest_data(edit_tool), errors)

    recognized_profile = copy.deepcopy(manifest)
    recognized_profile["provider_profile"]["candidate_branch_recognized_profile_present"] = True
    expect_failure("recognized agent profile installation", validate_manifest_data(recognized_profile), errors)

    recognized_skill = copy.deepcopy(manifest)
    recognized_skill["provider_profile"]["candidate_branch_recognized_skill_present"] = True
    expect_failure("recognized skill installation", validate_manifest_data(recognized_skill), errors)

    unknown_provider_activation = copy.deepcopy(manifest)
    unknown_provider_activation["provider_profile"]["activation_authorized"] = True
    expect_failure(
        "unknown provider activation field",
        validate_manifest_data(unknown_provider_activation),
        errors,
    )

    authority_activation = copy.deepcopy(manifest)
    authority_activation["authority"]["activation_authorized"] = True
    expect_failure(
        "unknown authority activation field",
        validate_manifest_data(authority_activation),
        errors,
    )

    top_level_activation = copy.deepcopy(manifest)
    top_level_activation["activation_authorized"] = True
    expect_failure(
        "unknown top-level activation field",
        validate_manifest_data(top_level_activation),
        errors,
    )

    parent_control_plane_drift = copy.deepcopy(manifest)
    parent_control_plane_drift["identity"]["parent_control_plane"] = "ct.control-plane.untrusted"
    expect_failure(
        "parent control plane drift",
        validate_manifest_data(parent_control_plane_drift),
        errors,
    )

    parent_escalation = copy.deepcopy(manifest)
    parent_escalation["parent_and_inventory"]["parent_relationship"] = "vote_and_approval_control"
    expect_failure("parent authority escalation", validate_manifest_data(parent_escalation), errors)

    inventory_promotion = copy.deepcopy(manifest)
    inventory_promotion["parent_and_inventory"]["public_agent_registry_entry_state"] = "registered"
    expect_failure("unverified inventory promotion", validate_manifest_data(inventory_promotion), errors)

    parent_gate_removed = copy.deepcopy(manifest)
    parent_gate_removed["parent_and_inventory"]["activation_blocked_until_runtime_parent_and_inventory_verified"] = False
    expect_failure("parent and inventory activation gate removal", validate_manifest_data(parent_gate_removed), errors)

    unknown_parent_control = copy.deepcopy(manifest)
    unknown_parent_control["parent_and_inventory"]["vote_or_approval_control"] = True
    expect_failure(
        "unknown parent authority field",
        validate_manifest_data(unknown_parent_control),
        errors,
    )

    activation_gate_removed = copy.deepcopy(manifest)
    activation_gate_removed["activation_gates"].pop()
    expect_failure("activation gate removal", validate_manifest_data(activation_gate_removed), errors)

    workflow_mode_escalation = copy.deepcopy(manifest)
    workflow_mode_escalation["workflow"]["mode"] = "mutate_and_publish"
    expect_failure("workflow mode escalation", validate_manifest_data(workflow_mode_escalation), errors)

    exact_head_gate_removed = copy.deepcopy(manifest)
    exact_head_gate_removed["workflow"]["exact_head_review_required"] = False
    expect_failure(
        "exact-head review gate removal",
        validate_manifest_data(exact_head_gate_removed),
        errors,
    )

    self_healing_phase_promotion = copy.deepcopy(manifest)
    self_healing_phase_promotion["self_healing"]["phase_promotion_prohibited"] = False
    expect_failure(
        "self-healing phase promotion",
        validate_manifest_data(self_healing_phase_promotion),
        errors,
    )

    new_write_provider = copy.deepcopy(manifest)
    new_write_provider["custody_topology"]["new_provider"] = {
        "write_enabled_by_this_packet": True
    }
    expect_failure(
        "unknown write-enabled provider",
        validate_manifest_data(new_write_provider),
        errors,
    )

    public_route_activation = copy.deepcopy(manifest)
    public_route_activation["documentation"]["public_route_activated"] = True
    expect_failure(
        "documentation route activation",
        validate_manifest_data(public_route_activation),
        errors,
    )

    governance_validation_removed = copy.deepcopy(manifest)
    governance_validation_removed["validation"]["agent_governance_validation_required"] = False
    expect_failure(
        "agent governance validation removal",
        validate_manifest_data(governance_validation_removed),
        errors,
    )

    rollback_removed = copy.deepcopy(manifest)
    rollback_removed["rollback"].pop("prospective_runtime_binding")
    expect_failure("external binding rollback removal", validate_manifest_data(rollback_removed), errors)

    collision_removed = copy.deepcopy(manifest)
    collision_removed["role_collision_boundary"].pop("evidence_auditor")
    expect_failure("role collision boundary removal", validate_manifest_data(collision_removed), errors)

    packet_inventory_extra = copy.deepcopy(manifest)
    packet_inventory_extra["packet_inventory"]["files"].append("unexpected.txt")
    packet_inventory_extra["packet_inventory"]["file_count"] = 9
    expect_failure("packet inventory expansion", validate_manifest_data(packet_inventory_extra), errors)

    secret_field = copy.deepcopy(valid_record)
    secret_field["api_key"] = "not-a-real-secret"
    expect_failure("schema secret field", validate_record(secret_field, schema), errors)

    secret_value = copy.deepcopy(valid_record)
    secret_value["source_records"][0]["public_reference"] = (
        "gh" + "p_" + ("A" * 40)
    )
    expect_failure("secret in allowed value", validate_record(secret_value, schema), errors)

    private_locator = copy.deepcopy(valid_record)
    private_locator["source_records"][0]["public_reference"] = (
        "https://drive." + "google.com/file/d/" + ("A" * 24)
    )
    expect_failure("private locator in allowed value", validate_record(private_locator, schema), errors)

    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_root = Path(temporary_directory)
        renamed_agent = temporary_root / ".github" / "agents" / "memory-steward.md"
        renamed_agent.parent.mkdir(parents=True)
        renamed_agent.write_text(
            "---\nname: renamed\n---\nct.agent.institutional-memory-asset-steward\n",
            encoding="utf-8",
        )
        recognized_errors: list[str] = []
        validate_recognized_installations(temporary_root, recognized_errors)
        expect_failure("renamed recognized agent installation", recognized_errors, errors)

    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_root = Path(temporary_directory)
        renamed_agent = temporary_root / ".github" / "agents" / "memory-steward.agent.md"
        renamed_agent.parent.mkdir(parents=True)
        renamed_agent.write_text(
            "---\nname: Institutional Memory and Asset Steward\ndescription: preserved\n---\n",
            encoding="utf-8",
        )
        recognized_errors = []
        validate_recognized_installations(temporary_root, recognized_errors)
        expect_failure(
            "institutional-ID-stripped recognized agent installation",
            recognized_errors,
            errors,
        )

    for recognized_root in RECOGNIZED_SKILL_ROOTS:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            renamed_skill = temporary_root / recognized_root / "memory-steward" / "SKILL.md"
            renamed_skill.parent.mkdir(parents=True)
            renamed_skill.write_text(
                "---\nname: institutional-memory-asset-steward\ndescription: test\n---\n",
                encoding="utf-8",
            )
            recognized_errors = []
            validate_recognized_installations(temporary_root, recognized_errors)
            expect_failure(
                f"renamed recognized skill installation under {recognized_root}",
                recognized_errors,
                errors,
            )

    for recognized_root in RECOGNIZED_SKILL_ROOTS:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            renamed_skill = temporary_root / recognized_root / "memory-steward" / "SKILL.md"
            renamed_skill.parent.mkdir(parents=True)
            renamed_skill.write_text(
                "---\nname: renamed-steward\ndescription: preserved\n---\n"
                "# Institutional Memory and Asset Steward\n",
                encoding="utf-8",
            )
            recognized_errors = []
            validate_recognized_installations(temporary_root, recognized_errors)
            expect_failure(
                f"name-stripped recognized skill installation under {recognized_root}",
                recognized_errors,
                errors,
            )

    verified_without_digest = copy.deepcopy(valid_record)
    verified_without_digest["versions"][0]["sha256"] = None
    expect_failure("verified version without digest", validate_record(verified_without_digest, schema), errors)

    if not RECORD_ID.fullmatch(valid_record["record_id"]):
        add_error(errors, "self-test fixture: record_id regex invariant failed")
    if not CT_ID.fullmatch(valid_record["asset_id"]):
        add_error(errors, "self-test fixture: asset_id regex invariant failed")
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository or standalone packet root (default: validator parent repository)",
    )
    parser.add_argument(
        "--record",
        action="append",
        type=Path,
        default=[],
        help="Additional custody record JSON file to validate; may be repeated",
    )
    parser.add_argument("--self-test", action="store_true", help="Run adversarial validator tests")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = args.root.resolve()
    packet_errors, manifest, schema = validate_packet(root)
    errors = list(packet_errors)

    for record_path in args.record:
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            add_error(errors, f"{record_path}: cannot load record JSON: {exc}")
            continue
        if not isinstance(record, dict):
            add_error(errors, f"{record_path}: record must be a JSON object")
            continue
        errors.extend(f"{record_path}: {error}" for error in validate_record(record, schema))

    if args.self_test:
        errors.extend(run_self_test(packet_errors, manifest, schema))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"FAIL: {len(errors)} institutional steward validation error(s)", file=sys.stderr)
        return 1

    if args.self_test:
        print("PASS: institutional memory and asset steward self-test")
    print("PASS: institutional memory and asset steward packet validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
