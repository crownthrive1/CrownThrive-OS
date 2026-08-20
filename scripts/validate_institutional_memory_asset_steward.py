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
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


EXPECTED_FILES = (
    ".github/agents/institutional-memory-asset-steward.agent.md",
    ".github/skills/institutional-memory-asset-steward/SKILL.md",
    ".github/workflows/institutional-memory-asset-steward.yml",
    "automation/institutional-memory-asset-steward.mdx",
    "developers/manifests/institutional-memory-asset-steward.v1.json",
    "developers/schemas/institutional-asset-custody-record.v1.schema.json",
    "scripts/validate_institutional_memory_asset_steward.py",
    "changelog/phase-2-99-institutional-memory-asset-steward-seed.mdx",
)

AGENT_PATH = EXPECTED_FILES[0]
SKILL_PATH = EXPECTED_FILES[1]
WORKFLOW_PATH = EXPECTED_FILES[2]
DOC_PATH = EXPECTED_FILES[3]
MANIFEST_PATH = EXPECTED_FILES[4]
SCHEMA_PATH = EXPECTED_FILES[5]
CHANGELOG_PATH = EXPECTED_FILES[7]

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
    for relative_path in EXPECTED_FILES:
        path = root / relative_path
        if not path.is_file():
            add_error(errors, f"{relative_path}: required packet file is missing")

    # In the standalone packet, these shared or private surfaces must not be
    # bundled. In a full repository they may already exist, so their absence is
    # instead enforced by the packet manifest and workflow path set.
    if not (root / "AGENTS.md").exists():
        if (root / "docs.json").exists():
            add_error(errors, "docs.json: shared navigation must not be in the bounded packet")
        migrations = root / "supabase" / "migrations"
        if migrations.exists():
            add_error(errors, "supabase/migrations: private implementation is outside this packet")


def validate_frontmatter(root: Path, errors: list[str]) -> None:
    agent_text = read_text(root, AGENT_PATH, errors)
    agent = scalar_frontmatter(agent_text, AGENT_PATH, errors)
    require_equal(errors, agent.get("name"), "Institutional Memory & Asset Steward", f"{AGENT_PATH}: name")
    require_equal(errors, agent.get("target"), "github-copilot", f"{AGENT_PATH}: target")
    require_equal(errors, agent.get("user-invocable"), "true", f"{AGENT_PATH}: user-invocable")
    require_equal(errors, agent.get("disable-model-invocation"), "false", f"{AGENT_PATH}: disable-model-invocation")
    if not re.search(r"(?m)^\s+institutional-id:\s+ct\.agent\.institutional-memory-asset-steward\s*$", agent_text):
        add_error(errors, f"{AGENT_PATH}: stable institutional ID is missing")
    if not re.search(r"(?m)^\s+vote-eligible:\s+['\"]?false['\"]?\s*$", agent_text):
        add_error(errors, f"{AGENT_PATH}: agent must be explicitly non-voting")
    tools_line = agent.get("tools", "")
    for tool in ("read", "search", "edit"):
        if tool not in tools_line:
            add_error(errors, f"{AGENT_PATH}: required tool {tool!r} is missing")
    if any(tool in tools_line.lower() for tool in ("execute", "shell", "terminal")):
        add_error(errors, f"{AGENT_PATH}: execution tools are outside the public preparation profile")

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
        (nested(manifest, "source_baseline", "repository"), "crownthrive1/CrownThrive-Support", "source_baseline.repository"),
        (nested(manifest, "source_baseline", "branch"), "main", "source_baseline.branch"),
        (nested(manifest, "source_baseline", "mintlify_deploy_branch"), "main", "source_baseline.mintlify_deploy_branch"),
        (nested(manifest, "phase", "current_subphase"), "2.99", "phase.current_subphase"),
        (nested(manifest, "phase", "packet_advances_phase"), False, "phase.packet_advances_phase"),
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


def validate_record(record: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    validate_instance(record, schema, schema, "record", errors)
    errors.extend(validate_record_semantics(record))
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

    for relative_path in EXPECTED_FILES:
        if relative_path not in text:
            add_error(errors, f"{WORKFLOW_PATH}: path filter lacks {relative_path!r}")

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

    d3_mutation = copy.deepcopy(manifest)
    d3_mutation["authority"]["d3"]["permitted"] = True
    expect_failure("D3 escalation", validate_manifest_data(d3_mutation), errors)

    provider_mutation = copy.deepcopy(manifest)
    provider_mutation["custody_topology"]["google_drive"]["write_enabled_by_this_packet"] = True
    expect_failure("provider write escalation", validate_manifest_data(provider_mutation), errors)

    secret_field = copy.deepcopy(valid_record)
    secret_field["api_key"] = "not-a-real-secret"
    expect_failure("schema secret field", validate_record(secret_field, schema), errors)

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
