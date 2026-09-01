"""Deterministic survival contracts for CrownThrive Penta Family members.

This module is dependency-free so the survival gate can run in CI, recovery
shells, and minimal control-plane environments without an LLM or provider SDK.
It validates declarations, produces deterministic receipts, audits family-wide
coverage, ratchets changed/new members, and gates exact production releases.

The model may propose work. It never supplies identity, durable state,
authority, queue/lease safety, evidence, or release truth.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence

SCHEMA_ID = "ct.penta.survival-contract.v1"
PROOF_SCHEMA_ID = "ct.penta.survival-proof-bundle.v1"
VALIDATION_SCHEMA_ID = "ct.penta.survival-validation-receipt.v1"
PROOF_VALIDATION_SCHEMA_ID = "ct.penta.survival-proof-validation-receipt.v1"
COVERAGE_SCHEMA_ID = "ct.penta.survival-coverage-receipt.v1"
RATCHET_SCHEMA_ID = "ct.penta.survival-ratchet-receipt.v1"
RELEASE_SCHEMA_ID = "ct.penta.survival-release-gate-receipt.v1"
DEFAULT_POLICY = "data/penta/survival-policy.v1.json"
DEFAULT_REGISTRY = "data/penta/survival-contracts.registry.json"
DEFAULT_PROOF_DIR = "penta/survival/evidence"
DEFAULT_TEST_PLAN = "tests/survival/model-off-survival-test-plan.v1.json"
PRODUCTION_MATURITIES = {"certified", "production"}
ALLOWED_MATURITIES = {"specified", "implemented", "certified", "production", "hold", "retired"}
DECLARATION_MATURITIES = set(ALLOWED_MATURITIES)
ATTESTATION_STATES = {"declared", "verified", "hold", "failed", "expired"}
MODEL_MODES = {"none", "optional", "proposal_required"}
DEGRADED_MODES = {
    "full_deterministic_service",
    "deterministic_core_only",
    "read_only",
    "queue_and_hold",
    "fail_closed",
}
VERIFICATION_METHODS = {
    "governed_ci_oidc",
    "penta_certifier",
    "accountable_human_dual_control",
}
PROOF_CASE_STATES = {"pass", "not_applicable"}
UNCONDITIONAL_PROOF_CASES = {
    "identity.restart-stability",
    "state.durable-rehydrate",
    "dail.history-continuity",
    "chlom.authority-continuity",
    "penta-certifier.exact-subject",
    "model.unavailable-degraded-mode",
    "crash.commit-receipt-boundaries",
    "recovery.backup-restore-isolation",
}
REQUIRED_RESTART_CASES = {
    "graceful_restart",
    "crash_before_commit",
    "crash_after_commit_before_receipt",
    "queue_redelivery",
    "lease_owner_loss",
    "model_unavailable",
    "model_replaced",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
PENTA_ID_RE = re.compile(r"^penta\.[a-z0-9][a-z0-9.-]*$")
PLACEHOLDER_TOKENS = ("todo", "tbd", "example", "placeholder", "pending:", "replace-me", "<")


class PentaSurvivalError(ValueError):
    """Raised for invalid policy, registry, contract, or release evidence."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PentaSurvivalError(f"cannot read JSON: {path}") from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PentaSurvivalError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaSurvivalError(f"JSON root must be an object: {path}")
    return value


def _git_json(root: Path, ref: str, rel: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "show", f"{ref}:{rel}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PentaSurvivalError(f"cannot read {rel} from git ref {ref}") from exc
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise PentaSurvivalError(f"invalid JSON for {rel} at {ref}: {exc}") from exc
    if not isinstance(value, dict):
        raise PentaSurvivalError(f"JSON root must be an object for {rel} at {ref}")
    return value


def _git_changed_files(root: Path, base_ref: str) -> list[str]:
    """Return deterministic repository-relative paths changed from base to HEAD."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMRT", f"{base_ref}...HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PentaSurvivalError(f"cannot calculate changed paths from git ref {base_ref}") from exc
    paths: list[str] = []
    for raw in proc.stdout.splitlines():
        value = raw.strip().replace("\\", "/")
        if value:
            paths.append(_safe_rel_path(value))
    return sorted(set(paths))


def _safe_rel_path(rel: str, *, prefix: str | None = None) -> str:
    if not isinstance(rel, str) or not rel.strip():
        raise PentaSurvivalError("path reference must be a non-empty string")
    value = rel.strip().replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise PentaSurvivalError(f"unsafe repository-relative path: {rel!r}")
    normalized = str(path)
    if prefix and not normalized.startswith(prefix.rstrip("/") + "/"):
        raise PentaSurvivalError(f"path must be under {prefix}/: {rel!r}")
    return normalized


def _parse_time(value: Any, field: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be an ISO-8601 timestamp")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} must be an ISO-8601 timestamp")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{field} must include a timezone")
        return None
    return parsed.astimezone(timezone.utc)


def _is_placeholder(value: str) -> bool:
    folded = value.casefold()
    return any(token in folded for token in PLACEHOLDER_TOKENS)


def _required_object(parent: Mapping[str, Any], key: str, errors: list[str]) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def _required_list(parent: Mapping[str, Any], key: str, errors: list[str], *, nonempty: bool = True) -> list[Any]:
    value = parent.get(key)
    if not isinstance(value, list) or (nonempty and not value):
        errors.append(f"{key} must be {'a non-empty' if nonempty else 'an'} array")
        return []
    return value


def _string_list(
    parent: Mapping[str, Any],
    key: str,
    errors: list[str],
    *,
    nonempty: bool = True,
    production: bool = False,
) -> list[str]:
    values = _required_list(parent, key, errors, nonempty=nonempty)
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key}[{index}] must be a non-empty string")
            continue
        item = value.strip()
        if production and _is_placeholder(item):
            errors.append(f"{key}[{index}] may not be a placeholder for production/certified maturity")
        normalized.append(item)
    if len(normalized) != len(set(normalized)):
        errors.append(f"{key} must not contain duplicate values")
    return normalized


def _required_string(parent: Mapping[str, Any], key: str, errors: list[str], *, production: bool = False) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{key} must be a non-empty string")
        return ""
    value = value.strip()
    if production and _is_placeholder(value):
        errors.append(f"{key} may not be a placeholder for a production/certified contract")
    return value


def _required_bool(parent: Mapping[str, Any], key: str, expected: bool, errors: list[str]) -> None:
    value = parent.get(key)
    if value is not expected:
        errors.append(f"{key} must be {str(expected).lower()}")


def _required_sha256(parent: Mapping[str, Any], key: str, errors: list[str], *, production: bool = False) -> str:
    value = _required_string(parent, key, errors, production=production)
    if value and not SHA256_RE.fullmatch(value):
        errors.append(f"{key} must be a lowercase SHA-256 digest")
    if production and value == "0" * 64:
        errors.append(f"{key} may not be an all-zero digest for production/certified maturity")
    return value


def _proof_refs(parent: Mapping[str, Any], key: str, errors: list[str], *, production: bool) -> list[str]:
    refs = _required_list(parent, key, errors)
    normalized: list[str] = []
    for index, value in enumerate(refs):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key}[{index}] must be a non-empty string")
            continue
        ref = value.strip()
        if production and _is_placeholder(ref):
            errors.append(f"{key}[{index}] may not be a placeholder for production/certified maturity")
        normalized.append(ref)
    if len(normalized) != len(set(normalized)):
        errors.append(f"{key} must not contain duplicate references")
    return normalized


def _validate_probe(probe: Mapping[str, Any], prefix: str, errors: list[str], *, production: bool) -> None:
    _required_string(probe, "probe_ref", errors, production=production)
    _required_string(probe, "success_semantics", errors, production=production)
    _required_string(probe, "failure_semantics", errors, production=production)
    timeout = probe.get("timeout_seconds")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        errors.append(f"{prefix}.timeout_seconds must be a positive integer")


def _validate_function_set(section: Mapping[str, Any], errors: list[str], *, production: bool) -> None:
    mode = _required_string(section, "mode", errors)
    if mode not in {"declared", "not_applicable"}:
        errors.append("deterministic_functions.mode must be declared or not_applicable")
    functions = section.get("functions")
    if not isinstance(functions, list):
        errors.append("deterministic_functions.functions must be an array")
        functions = []
    if mode == "declared" and not functions:
        errors.append("deterministic_functions.functions must be non-empty when mode=declared")
    if mode == "not_applicable":
        _required_string(section, "not_applicable_reason", errors, production=production)
        if functions:
            errors.append("deterministic_functions.functions must be empty when mode=not_applicable")
    seen: set[tuple[str, str]] = set()
    for index, value in enumerate(functions):
        if not isinstance(value, dict):
            errors.append(f"deterministic_functions.functions[{index}] must be an object")
            continue
        name = _required_string(value, "name", errors, production=production)
        version = _required_string(value, "version", errors, production=production)
        if version and not SEMVER_RE.fullmatch(version):
            errors.append(f"deterministic function {name or index} version must be semver")
        key = (name, version)
        if key in seen:
            errors.append(f"duplicate deterministic function identity: {name}@{version}")
        seen.add(key)
        _required_sha256(value, "implementation_sha256", errors, production=production)
        _required_string(value, "input_schema_ref", errors, production=production)
        _required_string(value, "output_schema_ref", errors, production=production)
        _required_string(value, "replay_vectors_ref", errors, production=production)
        _required_sha256(value, "replay_vectors_sha256", errors, production=production)
        _required_bool(value, "replay_on_stored_inputs", True, errors)
        _required_bool(value, "side_effects_isolated", True, errors)
        _required_bool(value, "deterministic_boundary", True, errors)
        side_effect_mode = _required_string(value, "side_effect_mode", errors)
        if side_effect_mode not in {"pure", "effect_planned", "effect_adapter"}:
            errors.append(f"deterministic function {name or index} has invalid side_effect_mode")
        _proof_refs(value, "proof_refs", errors, production=production)
    compiled_hash = _required_sha256(section, "compiled_behavior_hash", errors, production=production)
    function_set_hash = _required_sha256(section, "function_set_sha256", errors, production=production)
    if functions:
        calculated = digest(functions)
        if function_set_hash and function_set_hash != calculated:
            errors.append("deterministic_functions.function_set_sha256 does not match canonical functions array")
    _proof_refs(section, "proof_refs", errors, production=production)


def _validate_queues(section: Mapping[str, Any], errors: list[str], *, production: bool) -> None:
    uses = section.get("uses_queues")
    if not isinstance(uses, bool):
        errors.append("queues.uses_queues must be boolean")
        return
    bindings = section.get("bindings")
    if not isinstance(bindings, list):
        errors.append("queues.bindings must be an array")
        bindings = []
    if uses and not bindings:
        errors.append("queues.bindings must be non-empty when uses_queues=true")
    if not uses:
        _required_string(section, "not_applicable_reason", errors, production=production)
        if bindings:
            errors.append("queues.bindings must be empty when uses_queues=false")
    seen: set[str] = set()
    for index, value in enumerate(bindings):
        if not isinstance(value, dict):
            errors.append(f"queues.bindings[{index}] must be an object")
            continue
        queue_id = _required_string(value, "queue_id", errors, production=production)
        if queue_id in seen:
            errors.append(f"duplicate queue_id: {queue_id}")
        seen.add(queue_id)
        _required_bool(value, "durable", True, errors)
        _required_bool(value, "stable_job_ids", True, errors)
        _required_bool(value, "idempotent_consumer", True, errors)
        _required_string(value, "idempotency_key_ref", errors, production=production)
        _required_string(value, "retry_policy_ref", errors, production=production)
        _required_string(value, "dead_letter_queue_ref", errors, production=production)
        delivery = _required_string(value, "delivery_semantics", errors)
        if delivery not in {"at_least_once_idempotent", "exactly_once_effect", "transactional_outbox"}:
            errors.append(f"queue {queue_id or index} has invalid delivery_semantics")
        ordering = _required_string(value, "ordering", errors)
        if ordering not in {"none", "partition", "global"}:
            errors.append(f"queue {queue_id or index} has invalid ordering")
        _proof_refs(value, "proof_refs", errors, production=production)
    _proof_refs(section, "proof_refs", errors, production=production)


def _validate_leases(section: Mapping[str, Any], errors: list[str], *, production: bool) -> None:
    uses = section.get("uses_leases")
    if not isinstance(uses, bool):
        errors.append("leases.uses_leases must be boolean")
        return
    bindings = section.get("bindings")
    if not isinstance(bindings, list):
        errors.append("leases.bindings must be an array")
        bindings = []
    if uses and not bindings:
        errors.append("leases.bindings must be non-empty when uses_leases=true")
    if not uses:
        _required_string(section, "not_applicable_reason", errors, production=production)
        if bindings:
            errors.append("leases.bindings must be empty when uses_leases=false")
    seen: set[str] = set()
    for index, value in enumerate(bindings):
        if not isinstance(value, dict):
            errors.append(f"leases.bindings[{index}] must be an object")
            continue
        lease_id = _required_string(value, "lease_id", errors, production=production)
        if lease_id in seen:
            errors.append(f"duplicate lease_id: {lease_id}")
        seen.add(lease_id)
        ttl = value.get("ttl_seconds")
        renewal = value.get("renewal_seconds")
        if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0:
            errors.append(f"lease {lease_id or index} ttl_seconds must be a positive integer")
        if not isinstance(renewal, int) or isinstance(renewal, bool) or renewal <= 0:
            errors.append(f"lease {lease_id or index} renewal_seconds must be a positive integer")
        if isinstance(ttl, int) and isinstance(renewal, int) and renewal >= ttl:
            errors.append(f"lease {lease_id or index} renewal_seconds must be less than ttl_seconds")
        _required_bool(value, "fencing_token", True, errors)
        _required_bool(value, "stale_owner_rejected", True, errors)
        _required_string(value, "clock_source_ref", errors, production=production)
        _required_string(value, "conflict_test_ref", errors, production=production)
        _proof_refs(value, "proof_refs", errors, production=production)
    _proof_refs(section, "proof_refs", errors, production=production)


def evaluate_contract(
    contract: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a deterministic validation receipt without executing side effects."""
    errors: list[str] = []
    warnings: list[str] = []
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    schema = _required_string(contract, "schema", errors)
    if schema != SCHEMA_ID:
        errors.append(f"schema must be {SCHEMA_ID}")
    contract_version = _required_string(contract, "contract_version", errors)
    if contract_version and not SEMVER_RE.fullmatch(contract_version):
        errors.append("contract_version must be semver")
    contract_id = _required_string(contract, "contract_id", errors)
    if contract_id and not re.fullmatch(r"^ct\.penta\.survival\.[a-z0-9][a-z0-9.-]*\.v[0-9]+$", contract_id):
        errors.append("contract_id must use ct.penta.survival.<identity>.v<integer> form")
    penta_id = _required_string(contract, "penta_id", errors)
    if penta_id and not PENTA_ID_RE.fullmatch(penta_id):
        errors.append("penta_id must use canonical penta.* machine-key form")
    canonical_name = _required_string(contract, "canonical_name", errors)
    environment = _required_string(contract, "environment", errors)
    if environment != "production":
        errors.append("environment must be production")
    maturity = _required_string(contract, "maturity", errors)
    if maturity not in ALLOWED_MATURITIES:
        errors.append("maturity is invalid")
    production = maturity in PRODUCTION_MATURITIES

    release = _required_object(contract, "release_binding", errors)
    binding_mode = _required_string(release, "binding_mode", errors)
    if binding_mode != "external_exact_subject_proof":
        errors.append("release_binding.binding_mode must be external_exact_subject_proof")
    _required_string(release, "exact_source_ref", errors, production=production)
    source_commit = _required_string(release, "source_commit", errors, production=production)
    if source_commit and not GIT_SHA_RE.fullmatch(source_commit):
        errors.append("release_binding.source_commit must be a lowercase 40-character Git SHA")
    if production and source_commit == "0" * 40:
        errors.append("release_binding.source_commit may not be all-zero for production/certified maturity")
    artifact_sha = _required_sha256(release, "artifact_sha256", errors, production=production)
    doctrine_version = _required_string(release, "doctrine_version", errors, production=production)
    compiled_hash = _required_sha256(release, "compiled_behavior_hash", errors, production=production)
    runtime_version = _required_string(release, "runtime_version", errors, production=production)
    if runtime_version and not SEMVER_RE.fullmatch(runtime_version):
        errors.append("release_binding.runtime_version must be semver")
    _required_string(release, "build_id", errors, production=production)

    identity = _required_object(contract, "persistent_identity", errors)
    stable_id = _required_string(identity, "stable_id", errors, production=production)
    if stable_id and penta_id and stable_id != penta_id:
        errors.append("persistent_identity.stable_id must equal penta_id")
    _required_string(identity, "identity_registry_ref", errors, production=production)
    _required_bool(identity, "survives_process_restart", True, errors)
    _required_bool(identity, "survives_node_replacement", True, errors)
    _required_bool(identity, "provider_independent", True, errors)
    _required_bool(identity, "model_independent", True, errors)
    _proof_refs(identity, "proof_refs", errors, production=production)

    state = _required_object(contract, "persistent_state", errors)
    _required_bool(state, "externalized", True, errors)
    _required_bool(state, "in_memory_authoritative", False, errors)
    _required_bool(state, "survives_restart", True, errors)
    _required_string(state, "authoritative_store_ref", errors, production=production)
    _required_string(state, "state_schema_version", errors, production=production)
    _required_string(state, "checkpoint_strategy_ref", errors, production=production)
    _required_string(state, "backup_ref", errors, production=production)
    _required_string(state, "restore_test_ref", errors, production=production)
    for field in ("rpo_seconds", "rto_seconds"):
        value = state.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"persistent_state.{field} must be a non-negative integer")
    _proof_refs(state, "proof_refs", errors, production=production)

    functions = _required_object(contract, "deterministic_functions", errors)
    _validate_function_set(functions, errors, production=production)
    function_compiled = functions.get("compiled_behavior_hash")
    if isinstance(function_compiled, str) and compiled_hash and function_compiled != compiled_hash:
        errors.append("deterministic_functions.compiled_behavior_hash must equal release_binding.compiled_behavior_hash")

    queues = _required_object(contract, "queues", errors)
    _validate_queues(queues, errors, production=production)
    leases = _required_object(contract, "leases", errors)
    _validate_leases(leases, errors, production=production)

    recovery = _required_object(contract, "recovery", errors)
    _required_string(recovery, "strategy_ref", errors, production=production)
    _required_string(recovery, "backup_restore_test_ref", errors, production=production)
    _required_string(recovery, "isolation_recovery_test_ref", errors, production=production)
    _required_string(recovery, "dependency_rebuild_ref", errors, production=production)
    for field in ("recovery_point_objective_seconds", "recovery_time_objective_seconds"):
        value = recovery.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"recovery.{field} must be a non-negative integer")
    _required_bool(recovery, "recovery_without_model", True, errors)
    _proof_refs(recovery, "proof_refs", errors, production=production)

    evidence = _required_object(contract, "evidence", errors)
    _required_string(evidence, "bundle_id", errors, production=production)
    _required_string(evidence, "bundle_ref", errors, production=production)
    _required_bool(evidence, "immutable", True, errors)
    _required_bool(evidence, "content_addressed", True, errors)
    _required_bool(evidence, "release_bound", True, errors)
    evidence_as_of = _parse_time(evidence.get("evidence_as_of"), "evidence.evidence_as_of", errors)
    expires_at = _parse_time(evidence.get("expires_at"), "evidence.expires_at", errors)
    if evidence_as_of and expires_at and expires_at <= evidence_as_of:
        errors.append("evidence.expires_at must be after evidence.evidence_as_of")
    if production and expires_at and expires_at <= now:
        errors.append("production/certified survival evidence is expired")
    subject = _required_object(evidence, "subject", errors)
    subject_source = _required_string(subject, "source_commit", errors, production=production)
    subject_artifact = _required_sha256(subject, "artifact_sha256", errors, production=production)
    subject_doctrine = _required_string(subject, "doctrine_version", errors, production=production)
    subject_compiled = _required_sha256(subject, "compiled_behavior_hash", errors, production=production)
    subject_functions = _required_sha256(subject, "function_set_sha256", errors, production=production)
    subject_runtime = _required_string(subject, "runtime_version", errors, production=production)
    subject_build = _required_string(subject, "build_id", errors, production=production)
    if subject_runtime and not SEMVER_RE.fullmatch(subject_runtime):
        errors.append("evidence.subject.runtime_version must be semver")
    if source_commit and subject_source and source_commit != subject_source:
        errors.append("evidence.subject.source_commit must equal release_binding.source_commit")
    if artifact_sha and subject_artifact and artifact_sha != subject_artifact:
        errors.append("evidence.subject.artifact_sha256 must equal release_binding.artifact_sha256")
    if doctrine_version and subject_doctrine and doctrine_version != subject_doctrine:
        errors.append("evidence.subject.doctrine_version must equal release_binding.doctrine_version")
    if compiled_hash and subject_compiled and compiled_hash != subject_compiled:
        errors.append("evidence.subject.compiled_behavior_hash must equal release_binding.compiled_behavior_hash")
    function_set_hash = functions.get("function_set_sha256")
    if isinstance(function_set_hash, str) and subject_functions and function_set_hash != subject_functions:
        errors.append("evidence.subject.function_set_sha256 must equal deterministic_functions.function_set_sha256")
    if runtime_version and subject_runtime and runtime_version != subject_runtime:
        errors.append("evidence.subject.runtime_version must equal release_binding.runtime_version")
    build_id = release.get("build_id")
    if isinstance(build_id, str) and subject_build and build_id != subject_build:
        errors.append("evidence.subject.build_id must equal release_binding.build_id")
    _proof_refs(evidence, "receipt_refs", errors, production=production)
    _proof_refs(evidence, "negative_test_refs", errors, production=production)
    _proof_refs(evidence, "stress_test_refs", errors, production=production)
    _proof_refs(evidence, "restart_test_refs", errors, production=production)
    _required_string(evidence, "model_off_test_ref", errors, production=production)
    evidence_manifest_sha = _required_sha256(evidence, "manifest_sha256", errors, production=production)

    authority = _required_object(contract, "authority_enforcement", errors)
    _required_string(authority, "deterministic_boundary_ref", errors, production=production)
    _required_string(authority, "chlom_ref", errors, production=production)
    _required_string(authority, "dail_ref", errors, production=production)
    _required_bool(authority, "model_can_authorize", False, errors)
    _required_bool(authority, "model_can_mutate_authoritative_state", False, errors)
    _required_bool(authority, "fail_closed", True, errors)
    _required_bool(authority, "exact_candidate_sha_required", True, errors)
    _required_bool(authority, "candidate_certified_production_sha_equal", True, errors)
    _required_bool(authority, "provider_write_requires_certified_binding", True, errors)
    _required_bool(authority, "provider_write_requires_readback", True, errors)
    _required_bool(authority, "append_only_audit_required", True, errors)
    _required_bool(authority, "receipt_chain_required", True, errors)
    _proof_refs(authority, "proof_refs", errors, production=production)

    health = _required_object(contract, "health_check", errors)
    for key in ("liveness", "readiness", "survival"):
        probe = _required_object(health, key, errors)
        _validate_probe(probe, f"health_check.{key}", errors, production=production)
    _required_bool(health, "dependency_state_exposed", True, errors)
    _required_bool(health, "authority_state_exposed", True, errors)
    _required_bool(health, "queue_state_exposed", True, errors)
    _required_bool(health, "lease_state_exposed", True, errors)
    _required_bool(health, "model_state_separate", True, errors)
    _required_bool(health, "degraded_state_exposed", True, errors)
    _proof_refs(health, "proof_refs", errors, production=production)

    model = _required_object(contract, "model_dependency", errors)
    model_mode = _required_string(model, "mode", errors)
    if model_mode not in MODEL_MODES:
        errors.append("model_dependency.mode is invalid")
    _required_string(model, "purpose", errors, production=production)
    _required_bool(model, "deterministic_authority_independent", True, errors)
    _required_bool(model, "durable_state_independent", True, errors)
    _required_bool(model, "queue_and_lease_safety_independent", True, errors)
    _required_bool(model, "model_output_untrusted", True, errors)
    _required_bool(model, "direct_tool_execution", False, errors)
    _required_bool(model, "direct_provider_execution", False, errors)
    _proof_refs(model, "proof_refs", errors, production=production)
    if model_mode != "none":
        _required_string(model, "model_adapter_ref", errors, production=production)

    degraded = _required_object(contract, "degraded_without_model", errors)
    degraded_mode = _required_string(degraded, "mode", errors)
    if degraded_mode not in DEGRADED_MODES:
        errors.append("degraded_without_model.mode is invalid")
    _string_list(degraded, "allowed_operations", errors, production=production)
    forbidden = _string_list(degraded, "forbidden_operations", errors, production=production)
    required_forbidden = {"model_authorization", "model_direct_mutation", "model_direct_provider_write"}
    if not required_forbidden.issubset({str(item) for item in forbidden}):
        errors.append("degraded_without_model.forbidden_operations must retain all model authority prohibitions")
    _required_bool(degraded, "state_integrity_preserved", True, errors)
    _required_bool(degraded, "authority_enforcement_preserved", True, errors)
    _required_bool(degraded, "queue_and_lease_safety_preserved", True, errors)
    _required_string(degraded, "health_state", errors, production=production)
    _proof_refs(degraded, "proof_refs", errors, production=production)
    if model_mode == "proposal_required" and degraded_mode == "full_deterministic_service":
        errors.append("proposal_required model dependency cannot claim full_deterministic_service without the model")

    replacement = _required_object(contract, "replaceable_model", errors)
    applicable = replacement.get("applicable")
    if not isinstance(applicable, bool):
        errors.append("replaceable_model.applicable must be boolean")
        applicable = False
    _required_bool(replacement, "replaceable", True, errors)
    _required_bool(replacement, "replacement_preserves_identity", True, errors)
    _required_bool(replacement, "replacement_preserves_state", True, errors)
    _required_bool(replacement, "replacement_preserves_authority", True, errors)
    _required_bool(replacement, "replacement_preserves_replay", True, errors)
    if applicable:
        _required_string(replacement, "adapter_contract_ref", errors, production=production)
        _required_string(replacement, "compatibility_test_ref", errors, production=production)
        _proof_refs(replacement, "proof_refs", errors, production=production)
    else:
        _required_string(replacement, "not_applicable_reason", errors, production=production)
        if model_mode != "none":
            errors.append("replaceable_model.applicable must be true when model_dependency.mode is not none")

    restart = _required_object(contract, "restart_behavior", errors)
    _required_bool(restart, "identity_preserved", True, errors)
    _required_bool(restart, "state_reloaded_from_authoritative_store", True, errors)
    _required_bool(restart, "in_flight_work_reconciled", True, errors)
    _required_bool(restart, "stable_job_ids_preserved", True, errors)
    _required_bool(restart, "duplicate_effects_prevented", True, errors)
    _required_bool(restart, "stale_leases_fenced", True, errors)
    _required_bool(restart, "authority_rechecked", True, errors)
    cases = _string_list(restart, "tested_cases", errors, production=production)
    case_set = set(cases)
    missing_cases = sorted(REQUIRED_RESTART_CASES - case_set)
    if missing_cases:
        errors.append("restart_behavior.tested_cases missing: " + ", ".join(missing_cases))
    _required_string(restart, "restart_matrix_ref", errors, production=production)
    _required_string(restart, "chaos_test_ref", errors, production=production)
    _proof_refs(restart, "proof_refs", errors, production=production)

    attestation = _required_object(contract, "attestation", errors)
    attestation_state = _required_string(attestation, "status", errors)
    if attestation_state not in ATTESTATION_STATES:
        errors.append("attestation.status is invalid")
    _required_string(attestation, "declared_by", errors, production=production)
    _parse_time(attestation.get("declared_at"), "attestation.declared_at", errors)
    independent = attestation.get("verifier_independent")
    if not isinstance(independent, bool):
        errors.append("attestation.verifier_independent must be boolean")
    attested_manifest = _required_sha256(attestation, "evidence_bundle_sha256", errors, production=production)
    if evidence_manifest_sha and attested_manifest and evidence_manifest_sha != attested_manifest:
        errors.append("attestation.evidence_bundle_sha256 must equal evidence.manifest_sha256")
    if attestation_state == "verified":
        _required_string(attestation, "verified_by", errors, production=True)
        _parse_time(attestation.get("verified_at"), "attestation.verified_at", errors)
        if independent is not True and not production:
            errors.append("verified survival attestation requires an independent verifier")
    if production:
        if attestation_state != "verified":
            errors.append("certified/production maturity requires attestation.status=verified")
        if independent is not True:
            errors.append("certified/production maturity requires an independent verifier")

    if policy:
        validate_policy(policy)
        required = set(policy.get("required_sections") or [])
        missing = sorted(required - set(contract))
        if missing:
            errors.append("contract missing policy-required sections: " + ", ".join(missing))

    unique_errors = sorted(set(errors))
    unique_warnings = sorted(set(warnings))
    if unique_errors:
        disposition = "HOLD_FAIL_CLOSED"
    elif attestation_state == "verified":
        # A declaration may claim verification, but only repository-bound proof
        # validation may convert that claim into VERIFIED.
        disposition = "VERIFICATION_CLAIM"
    elif attestation_state == "declared":
        disposition = "DECLARED"
    else:
        disposition = "HOLD_FAIL_CLOSED"
    production_eligible = False
    model_independent_authority = (
        authority.get("model_can_authorize") is False
        and authority.get("model_can_mutate_authoritative_state") is False
        and authority.get("fail_closed") is True
        and model.get("deterministic_authority_independent") is True
        and model.get("durable_state_independent") is True
        and model.get("queue_and_lease_safety_independent") is True
        and model.get("direct_tool_execution") is False
        and model.get("direct_provider_execution") is False
        and degraded.get("authority_enforcement_preserved") is True
    )
    report: dict[str, Any] = {
        "schema": VALIDATION_SCHEMA_ID,
        "contract_id": contract_id,
        "penta_id": penta_id,
        "canonical_name": canonical_name,
        "maturity": maturity,
        "contract_sha256": digest(contract),
        "disposition": disposition,
        "production_eligible": production_eligible,
        "repository_proof_required": production,
        "repository_proof_verified": False,
        "self_asserted_verification_accepted": False,
        "model_independent_authority": model_independent_authority,
        "errors": unique_errors,
        "warnings": unique_warnings,
    }
    report["receipt_sha256"] = digest(report)
    return report


def validate_contract(contract: Mapping[str, Any], *, policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    report = evaluate_contract(contract, policy=policy)
    if report["errors"]:
        raise PentaSurvivalError("; ".join(report["errors"]))
    return report


def validate_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("policy_id") != "ct.penta.survival-policy.v1":
        raise PentaSurvivalError("unexpected survival policy_id")
    if policy.get("policy_version") != "1.0.0":
        raise PentaSurvivalError("unexpected survival policy_version")
    if policy.get("applies_to_all_registered_pentas") is not True:
        raise PentaSurvivalError("survival policy must apply to all registered Pentas")
    if policy.get("family_registry_ref") != "data/penta/family.registry.json":
        raise PentaSurvivalError("survival policy family_registry_ref is incorrect")
    if policy.get("contract_schema_ref") != "schemas/penta/penta-survival-contract-v1.schema.json":
        raise PentaSurvivalError("survival policy contract_schema_ref is incorrect")
    if policy.get("contract_registry_ref") != DEFAULT_REGISTRY:
        raise PentaSurvivalError("survival policy contract_registry_ref is incorrect")
    if policy.get("proof_schema_ref") != "schemas/penta/penta-survival-proof-v1.schema.json":
        raise PentaSurvivalError("survival policy proof_schema_ref is incorrect")
    if policy.get("proof_directory") != DEFAULT_PROOF_DIR:
        raise PentaSurvivalError("survival policy proof_directory is incorrect")
    plan_hash = policy.get("model_off_test_plan_sha256")
    if not isinstance(plan_hash, str) or not SHA256_RE.fullmatch(plan_hash):
        raise PentaSurvivalError("survival policy model_off_test_plan_sha256 is invalid")
    production_rule = policy.get("production_rule")
    if not isinstance(production_rule, dict):
        raise PentaSurvivalError("production_rule must be an object")
    if set(production_rule.get("maturities_requiring_verified_contract") or []) != PRODUCTION_MATURITIES:
        raise PentaSurvivalError("production verified-contract maturities must be exactly certified + production")
    required_true = (
        "missing_contract_holds_promotion",
        "invalid_contract_holds_promotion",
        "expired_evidence_holds_promotion",
        "exact_release_binding_required",
        "independent_verification_required",
        "no_model_authority",
        "no_grandfathered_new_authority",
        "content_addressed_executed_proof_required",
        "self_asserted_verification_forbidden",
        "candidate_metadata_split_required",
    )
    for key in required_true:
        if production_rule.get(key) is not True:
            raise PentaSurvivalError(f"production_rule.{key} must be true")
    if production_rule.get("failure_disposition") != "HOLD_FAIL_CLOSED":
        raise PentaSurvivalError("survival failure disposition must be HOLD_FAIL_CLOSED")
    adoption = policy.get("adoption")
    if not isinstance(adoption, dict):
        raise PentaSurvivalError("adoption must be an object")
    if adoption.get("mode") != "RATCHET_TO_ZERO":
        raise PentaSurvivalError("survival adoption must ratchet to zero")
    if adoption.get("runtime_kill_switch") is not False:
        raise PentaSurvivalError("survival adoption cannot silently kill existing runtime")
    if adoption.get("promotion_gate") is not True or adoption.get("release_gate") is not True:
        raise PentaSurvivalError("survival adoption must gate promotion and release")
    if adoption.get("waivers") != "not_supported":
        raise PentaSurvivalError("survival contract waivers are not supported")
    required_sections = policy.get("required_sections")
    expected_sections = {
        "persistent_identity",
        "persistent_state",
        "deterministic_functions",
        "queues",
        "leases",
        "recovery",
        "evidence",
        "authority_enforcement",
        "health_check",
        "model_dependency",
        "degraded_without_model",
        "replaceable_model",
        "restart_behavior",
    }
    if set(required_sections or []) != expected_sections:
        raise PentaSurvivalError("required_sections do not match the PENTA_SURVIVAL_CONTRACT footprint")



def evaluate_proof_bundle(
    bundle: Mapping[str, Any],
    contract: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate immutable executed proof against one exact contract subject."""
    errors: list[str] = []
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    if bundle.get("schema") != PROOF_SCHEMA_ID:
        errors.append(f"proof schema must be {PROOF_SCHEMA_ID}")
    proof_version = _required_string(bundle, "proof_version", errors)
    if proof_version and not SEMVER_RE.fullmatch(proof_version):
        errors.append("proof_version must be semver")
    _required_string(bundle, "proof_id", errors, production=True)
    penta_id = _required_string(bundle, "penta_id", errors, production=True)
    if penta_id and not PENTA_ID_RE.fullmatch(penta_id):
        errors.append("proof penta_id must use canonical penta.* machine-key form")
    if penta_id and penta_id != contract.get("penta_id"):
        errors.append("proof penta_id does not match contract")

    release = contract.get("release_binding") if isinstance(contract.get("release_binding"), dict) else {}
    functions = contract.get("deterministic_functions") if isinstance(contract.get("deterministic_functions"), dict) else {}
    subject = _required_object(bundle, "subject", errors)
    subject_pairs = (
        ("source_commit", release.get("source_commit")),
        ("artifact_sha256", release.get("artifact_sha256")),
        ("doctrine_version", release.get("doctrine_version")),
        ("compiled_behavior_hash", release.get("compiled_behavior_hash")),
        ("function_set_sha256", functions.get("function_set_sha256")),
        ("runtime_version", release.get("runtime_version")),
        ("build_id", release.get("build_id")),
    )
    for field, expected in subject_pairs:
        actual = _required_string(subject, field, errors, production=True)
        if field in {"artifact_sha256", "compiled_behavior_hash", "function_set_sha256"} and actual and not SHA256_RE.fullmatch(actual):
            errors.append(f"proof subject.{field} must be a lowercase SHA-256 digest")
        if field == "source_commit" and actual and not GIT_SHA_RE.fullmatch(actual):
            errors.append("proof subject.source_commit must be a lowercase 40-character Git SHA")
        if field == "runtime_version" and actual and not SEMVER_RE.fullmatch(actual):
            errors.append("proof subject.runtime_version must be semver")
        if actual and expected is not None and actual != expected:
            errors.append(f"proof subject.{field} does not match contract")

    test_plan_ref = _required_string(bundle, "test_plan_ref", errors, production=True)
    if test_plan_ref != DEFAULT_TEST_PLAN:
        errors.append(f"proof test_plan_ref must be {DEFAULT_TEST_PLAN}")
    test_plan_sha = _required_sha256(bundle, "test_plan_sha256", errors, production=True)
    expected_plan_sha = digest(plan)
    if test_plan_sha and test_plan_sha != expected_plan_sha:
        errors.append("proof test_plan_sha256 does not match canonical test plan")

    executed_at = _parse_time(bundle.get("executed_at"), "proof.executed_at", errors)
    verified_at = _parse_time(bundle.get("verified_at"), "proof.verified_at", errors)
    expires_at = _parse_time(bundle.get("expires_at"), "proof.expires_at", errors)
    if executed_at and verified_at and verified_at < executed_at:
        errors.append("proof.verified_at must not precede proof.executed_at")
    if verified_at and expires_at and expires_at <= verified_at:
        errors.append("proof.expires_at must be after proof.verified_at")
    if expires_at and expires_at <= now:
        errors.append("proof bundle is expired")

    evidence = contract.get("evidence") if isinstance(contract.get("evidence"), dict) else {}
    attestation = contract.get("attestation") if isinstance(contract.get("attestation"), dict) else {}
    expected_as_of = _parse_time(evidence.get("evidence_as_of"), "evidence.evidence_as_of", errors)
    expected_expires = _parse_time(evidence.get("expires_at"), "evidence.expires_at", errors)
    if verified_at and expected_as_of and verified_at != expected_as_of:
        errors.append("proof.verified_at must equal contract evidence.evidence_as_of")
    if expires_at and expected_expires and expires_at != expected_expires:
        errors.append("proof.expires_at must equal contract evidence.expires_at")
    attested_at = _parse_time(attestation.get("verified_at"), "attestation.verified_at", errors)
    if verified_at and attested_at and verified_at != attested_at:
        errors.append("proof.verified_at must equal contract attestation.verified_at")

    verifier = _required_object(bundle, "verifier", errors)
    verifier_id = _required_string(verifier, "verifier_id", errors, production=True)
    _required_bool(verifier, "independent", True, errors)
    _required_string(verifier, "identity_ref", errors, production=True)
    method = _required_string(verifier, "verification_method", errors)
    if method not in VERIFICATION_METHODS:
        errors.append("proof verifier.verification_method is invalid")
    _required_string(verifier, "verification_run_ref", errors, production=True)
    _required_string(verifier, "receipt_chain_ref", errors, production=True)
    if verifier_id and verifier_id in {contract.get("penta_id"), attestation.get("declared_by")}:
        errors.append("proof verifier must be independent from the subject and declarer")
    if verifier_id and attestation.get("verified_by") != verifier_id:
        errors.append("proof verifier_id must equal contract attestation.verified_by")
    if attestation.get("verifier_independent") is not True:
        errors.append("contract attestation must declare an independent verifier")

    plan_cases = plan.get("cases") if isinstance(plan.get("cases"), list) else []
    expected_case_ids = [str(case.get("case_id")) for case in plan_cases if isinstance(case, dict)]
    if not expected_case_ids or len(expected_case_ids) != len(set(expected_case_ids)):
        errors.append("canonical proof test plan has invalid or duplicate case IDs")
    cases = bundle.get("cases")
    if not isinstance(cases, list):
        errors.append("proof cases must be an array")
        cases = []
    case_index: dict[str, Mapping[str, Any]] = {}
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"proof cases[{index}] must be an object")
            continue
        case_id = _required_string(case, "case_id", errors, production=True)
        if case_id in case_index:
            errors.append(f"duplicate proof case_id: {case_id}")
        case_index[case_id] = case
        status = _required_string(case, "status", errors)
        if status not in PROOF_CASE_STATES:
            errors.append(f"proof case {case_id or index} has invalid status")
        _parse_time(case.get("observed_at"), f"proof case {case_id or index}.observed_at", errors)
        _required_string(case, "receipt_ref", errors, production=True)
        _required_sha256(case, "receipt_sha256", errors, production=True)
        assertion_count = case.get("assertion_count")
        passed_count = case.get("passed_assertion_count")
        if not isinstance(assertion_count, int) or isinstance(assertion_count, bool) or assertion_count <= 0:
            errors.append(f"proof case {case_id or index}.assertion_count must be positive")
        if not isinstance(passed_count, int) or isinstance(passed_count, bool) or passed_count < 0:
            errors.append(f"proof case {case_id or index}.passed_assertion_count must be non-negative")
        if status == "pass" and isinstance(assertion_count, int) and passed_count != assertion_count:
            errors.append(f"proof case {case_id or index} did not pass every assertion")
        if status == "not_applicable":
            _required_string(case, "not_applicable_reason", errors, production=True)
            if passed_count not in {0, None}:
                errors.append(f"proof case {case_id or index} not_applicable must have zero passed assertions")
        elif "not_applicable_reason" in case:
            errors.append(f"proof case {case_id or index} pass must not carry not_applicable_reason")

    missing = sorted(set(expected_case_ids) - set(case_index))
    extra = sorted(set(case_index) - set(expected_case_ids))
    if missing:
        errors.append("proof cases missing: " + ", ".join(missing))
    if extra:
        errors.append("proof cases not in canonical plan: " + ", ".join(extra))

    required_pass = set(UNCONDITIONAL_PROOF_CASES)
    queues = contract.get("queues") if isinstance(contract.get("queues"), dict) else {}
    leases = contract.get("leases") if isinstance(contract.get("leases"), dict) else {}
    model = contract.get("model_dependency") if isinstance(contract.get("model_dependency"), dict) else {}
    if functions.get("mode") == "declared":
        required_pass.add("determinism.replay")
    if queues.get("uses_queues") is True:
        required_pass.update({"queue.redelivery-idempotency", "penta-queue.work-state-survival"})
    if leases.get("uses_leases") is True:
        required_pass.add("lease.owner-loss-fencing")
    if model.get("mode") != "none":
        required_pass.add("model.replacement-compatibility")
    subject_specific = {
        "penta.dnd": "penta-dnd.ttl-conflict-survival",
        "penta.queue": "penta-queue.work-state-survival",
        "penta.pm": "penta-pm.ownership-survival",
        "penta.self": "penta-self.case-survival",
        "penta.cos": "cos.phase-cursor-survival",
    }
    if penta_id in subject_specific:
        required_pass.add(subject_specific[penta_id])
    for case_id in sorted(required_pass):
        case = case_index.get(case_id)
        if not case or case.get("status") != "pass":
            errors.append(f"proof case {case_id} must pass for this contract")

    summary = _required_object(bundle, "summary", errors)
    pass_count = sum(1 for case in case_index.values() if case.get("status") == "pass")
    na_count = sum(1 for case in case_index.values() if case.get("status") == "not_applicable")
    expected_summary = {
        "case_count": len(case_index),
        "pass_count": pass_count,
        "not_applicable_count": na_count,
        "fail_count": 0,
        "all_applicable_cases_pass": True,
        "authority_manufactured": False,
        "production_promoted": False,
        "provider_write_performed": False,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            errors.append(f"proof summary.{key} must equal {expected!r}")

    unique_errors = sorted(set(errors))
    output: dict[str, Any] = {
        "schema": PROOF_VALIDATION_SCHEMA_ID,
        "proof_id": bundle.get("proof_id"),
        "penta_id": penta_id,
        "proof_bundle_sha256": digest(bundle),
        "test_plan_sha256": expected_plan_sha,
        "verifier_id": verifier_id,
        "disposition": "PASS" if not unique_errors else "HOLD_FAIL_CLOSED",
        "errors": unique_errors,
    }
    output["receipt_sha256"] = digest(output)
    return output


def _validate_bound_proof(
    root: Path,
    contract: Mapping[str, Any],
    structural_report: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    if structural_report.get("errors"):
        return None, list(structural_report.get("errors") or [])
    maturity = contract.get("maturity")
    if maturity not in PRODUCTION_MATURITIES:
        return None, reasons
    evidence = contract.get("evidence") if isinstance(contract.get("evidence"), dict) else {}
    attestation = contract.get("attestation") if isinstance(contract.get("attestation"), dict) else {}
    try:
        bundle_ref = _safe_rel_path(str(evidence.get("bundle_ref") or ""), prefix=DEFAULT_PROOF_DIR)
    except PentaSurvivalError as exc:
        return None, [str(exc)]
    bundle_path = root / bundle_ref
    if not bundle_path.exists():
        return None, [f"missing executed proof bundle: {bundle_ref}"]
    bundle = _load_json(bundle_path)
    bundle_sha = digest(bundle)
    if evidence.get("manifest_sha256") != bundle_sha:
        reasons.append("evidence.manifest_sha256 does not match executed proof bundle")
    if attestation.get("evidence_bundle_sha256") != bundle_sha:
        reasons.append("attestation.evidence_bundle_sha256 does not match executed proof bundle")
    plan_path = root / DEFAULT_TEST_PLAN
    if not plan_path.exists():
        reasons.append(f"missing canonical model-off test plan: {DEFAULT_TEST_PLAN}")
        return None, sorted(set(reasons))
    plan = _load_json(plan_path)
    proof_report = evaluate_proof_bundle(bundle, contract, plan)
    reasons.extend(proof_report["errors"])
    return proof_report, sorted(set(reasons))


def _repository_validation_report(
    root: Path,
    contract: Mapping[str, Any],
    structural_report: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    report = dict(structural_report)
    proof_report, reasons = _validate_bound_proof(root, contract, structural_report)
    production = contract.get("maturity") in PRODUCTION_MATURITIES
    proof_verified = bool(
        production
        and proof_report
        and proof_report.get("disposition") == "PASS"
        and not reasons
        and contract.get("attestation", {}).get("status") == "verified"
    )
    report["repository_proof_verified"] = proof_verified
    report["proof_validation_receipt_sha256"] = proof_report.get("receipt_sha256") if proof_report else None
    report["proof_bundle_sha256"] = proof_report.get("proof_bundle_sha256") if proof_report else None
    if report.get("errors"):
        report["disposition"] = "HOLD_FAIL_CLOSED"
    elif production and proof_verified:
        report["disposition"] = "VERIFIED"
    elif production:
        report["disposition"] = "HOLD_FAIL_CLOSED"
    elif contract.get("attestation", {}).get("status") == "declared":
        report["disposition"] = "DECLARED"
    else:
        report["disposition"] = "HOLD_FAIL_CLOSED"
    report["production_eligible"] = bool(production and proof_verified and not report.get("errors"))
    report.pop("receipt_sha256", None)
    report["receipt_sha256"] = digest(report)
    return report, reasons

def _read_source(root: Path, rel: str, ref: str | None = None) -> dict[str, Any]:
    safe = _safe_rel_path(rel)
    return _git_json(root, ref, safe) if ref else _load_json(root / safe)


def discover_family_members(root: Path, *, ref: str | None = None) -> dict[str, dict[str, Any]]:
    family_rel = "data/penta/family.registry.json"
    family = _read_source(root, family_rel, ref)
    catalogs = family.get("catalogs")
    if not isinstance(catalogs, list) or not catalogs:
        raise PentaSurvivalError("family registry must declare catalogs")
    members: dict[str, dict[str, Any]] = {}
    for catalog_ref in catalogs:
        if not isinstance(catalog_ref, dict):
            raise PentaSurvivalError("family catalog references must be objects")
        rel = _safe_rel_path(str(catalog_ref.get("path") or ""), prefix="data/penta")
        catalog = _read_source(root, rel, ref)
        systems = catalog.get("systems")
        if not isinstance(systems, list):
            raise PentaSurvivalError(f"catalog has no systems array: {rel}")
        for index, system in enumerate(systems):
            if not isinstance(system, dict):
                raise PentaSurvivalError(f"system {index} in {rel} must be an object")
            machine_key = system.get("machine_key")
            maturity = system.get("maturity")
            canonical_name = system.get("canonical_name")
            if not isinstance(machine_key, str) or not PENTA_ID_RE.fullmatch(machine_key):
                raise PentaSurvivalError(f"invalid machine_key in {rel}: {machine_key!r}")
            if machine_key in members:
                raise PentaSurvivalError(f"duplicate family machine_key: {machine_key}")
            if maturity not in ALLOWED_MATURITIES:
                raise PentaSurvivalError(f"invalid maturity for {machine_key}: {maturity!r}")
            if not isinstance(canonical_name, str) or not canonical_name.strip():
                raise PentaSurvivalError(f"missing canonical_name for {machine_key}")
            members[machine_key] = {
                "penta_id": machine_key,
                "canonical_name": canonical_name.strip(),
                "maturity": maturity,
                "source": rel,
                "source_record_sha256": digest(system),
            }
    return dict(sorted(members.items()))


def load_policy_and_registry(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = _load_json(root / DEFAULT_POLICY)
    validate_policy(policy)
    plan = _load_json(root / DEFAULT_TEST_PLAN)
    if policy.get("model_off_test_plan_sha256") != digest(plan):
        raise PentaSurvivalError("survival policy model_off_test_plan_sha256 does not match canonical plan")
    registry = _load_json(root / DEFAULT_REGISTRY)
    if registry.get("registry_id") != "ct.penta.survival-contracts.v1":
        raise PentaSurvivalError("unexpected survival contract registry_id")
    registry_version = registry.get("registry_version")
    if not isinstance(registry_version, str) or not SEMVER_RE.fullmatch(registry_version):
        raise PentaSurvivalError("survival registry_version must be semver")
    if registry.get("policy_ref") != DEFAULT_POLICY:
        raise PentaSurvivalError("survival registry policy_ref is incorrect")
    if registry.get("family_registry_ref") != "data/penta/family.registry.json":
        raise PentaSurvivalError("survival registry family_registry_ref is incorrect")
    if registry.get("contract_directory") != "data/penta/survival-contracts":
        raise PentaSurvivalError("survival registry contract_directory is incorrect")
    if registry.get("failure_disposition") != "HOLD_FAIL_CLOSED":
        raise PentaSurvivalError("survival registry must fail closed")
    contracts = registry.get("contracts")
    if not isinstance(contracts, list):
        raise PentaSurvivalError("survival registry contracts must be an array")
    seen: set[str] = set()
    seen_refs: set[str] = set()
    for item in contracts:
        if not isinstance(item, dict):
            raise PentaSurvivalError("survival registry entries must be objects")
        penta_id = item.get("penta_id")
        if not isinstance(penta_id, str) or not PENTA_ID_RE.fullmatch(penta_id):
            raise PentaSurvivalError(f"invalid registry penta_id: {penta_id!r}")
        if penta_id in seen:
            raise PentaSurvivalError(f"duplicate survival registry penta_id: {penta_id}")
        seen.add(penta_id)
        contract_ref = _safe_rel_path(
            str(item.get("contract_ref") or ""), prefix="data/penta/survival-contracts"
        )
        if contract_ref in seen_refs:
            raise PentaSurvivalError(f"duplicate survival registry contract_ref: {contract_ref}")
        seen_refs.add(contract_ref)
        contract_sha256 = item.get("contract_sha256")
        if not isinstance(contract_sha256, str) or not SHA256_RE.fullmatch(contract_sha256):
            raise PentaSurvivalError(f"invalid contract_sha256 for {penta_id}")
    return policy, registry


def _registry_index(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item["penta_id"]): item for item in registry.get("contracts", []) if isinstance(item, dict)}


def _check_member_contract(
    root: Path,
    member: Mapping[str, Any],
    entry: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    penta_id = str(member["penta_id"])
    if entry is None:
        reasons.append("missing survival registry entry")
        return None, reasons
    rel = _safe_rel_path(str(entry.get("contract_ref") or ""), prefix="data/penta/survival-contracts")
    path = root / rel
    if not path.exists():
        reasons.append(f"missing contract file: {rel}")
        return None, reasons
    contract = _load_json(path)
    structural_report = evaluate_contract(contract, policy=policy)
    report, proof_reasons = _repository_validation_report(root, contract, structural_report)
    if contract.get("penta_id") != penta_id:
        reasons.append("contract penta_id does not match family member")
    if contract.get("canonical_name") != member.get("canonical_name"):
        reasons.append("contract canonical_name does not match family member")
    if contract.get("maturity") != member.get("maturity"):
        reasons.append("contract maturity does not match family member")
    expected_hash = entry.get("contract_sha256")
    actual_hash = report["contract_sha256"]
    if expected_hash != actual_hash:
        reasons.append("registry contract_sha256 does not match contract")
    reasons.extend(report["errors"])
    reasons.extend(proof_reasons)
    return report, sorted(set(reasons))


def coverage_report(root: Path) -> dict[str, Any]:
    policy, registry = load_policy_and_registry(root)
    members = discover_family_members(root)
    entries = _registry_index(registry)
    results: list[dict[str, Any]] = []
    blockers: list[str] = []
    declaration_debt: list[str] = []
    verified = 0
    for penta_id, member in members.items():
        report, reasons = _check_member_contract(root, member, entries.get(penta_id), policy)
        maturity = str(member["maturity"])
        required_verified = maturity in PRODUCTION_MATURITIES
        declared = report is not None and not reasons
        is_verified = declared and report is not None and report["disposition"] == "VERIFIED"
        if is_verified:
            verified += 1
        if required_verified and not is_verified:
            blockers.append(penta_id)
        elif maturity in DECLARATION_MATURITIES and not declared:
            declaration_debt.append(penta_id)
        results.append(
            {
                "penta_id": penta_id,
                "canonical_name": member["canonical_name"],
                "maturity": maturity,
                "required_verified": required_verified,
                "contract_present": report is not None,
                "contract_declared": bool(declared),
                "contract_verified": bool(is_verified),
                "disposition": "VERIFIED" if is_verified else ("SURVIVAL_HOLD" if required_verified else "DECLARATION_DEBT"),
                "reasons": reasons,
                "contract_sha256": report.get("contract_sha256") if report else None,
                "validation_receipt_sha256": report.get("receipt_sha256") if report else None,
            }
        )
    unknown_entries = sorted(set(entries) - set(members))
    if unknown_entries:
        blockers.extend(f"unknown:{item}" for item in unknown_entries)
    output: dict[str, Any] = {
        "schema": COVERAGE_SCHEMA_ID,
        "policy_id": policy["policy_id"],
        "family_member_count": len(members),
        "verified_contract_count": verified,
        "production_blocker_count": len(blockers),
        "declaration_debt_count": len(declaration_debt),
        "unknown_registry_entries": unknown_entries,
        "production_blockers": sorted(blockers),
        "declaration_debt": sorted(declaration_debt),
        "disposition": "PASS" if not blockers else "HOLD_FAIL_CLOSED",
        "members": results,
    }
    output["receipt_sha256"] = digest(output)
    return output


def _changed_member_ids(root: Path, base_ref: str) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    head = discover_family_members(root)
    base = discover_family_members(root, ref=base_ref)
    changed = sorted(key for key in set(head) | set(base) if head.get(key) != base.get(key))
    return base, head, changed



def _registered_proof_refs(
    root: Path,
    entries: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    refs: dict[str, str] = {}
    for penta_id, entry in entries.items():
        contract_ref = _safe_rel_path(
            str(entry.get("contract_ref") or ""), prefix="data/penta/survival-contracts"
        )
        path = root / contract_ref
        if not path.exists():
            continue
        contract = _load_json(path)
        evidence = contract.get("evidence") if isinstance(contract.get("evidence"), dict) else {}
        proof_ref_raw = evidence.get("bundle_ref")
        if not isinstance(proof_ref_raw, str) or not proof_ref_raw.strip():
            continue
        try:
            proof_ref = _safe_rel_path(proof_ref_raw, prefix=DEFAULT_PROOF_DIR)
        except PentaSurvivalError:
            continue
        if proof_ref in refs and refs[proof_ref] != penta_id:
            raise PentaSurvivalError(f"proof bundle is referenced by multiple Pentas: {proof_ref}")
        refs[proof_ref] = penta_id
    return refs

def ratchet_report(root: Path, base_ref: str) -> dict[str, Any]:
    policy, registry = load_policy_and_registry(root)
    entries = _registry_index(registry)
    base, head, changed = _changed_member_ids(root, base_ref)
    changed_paths = _git_changed_files(root, base_ref)
    blockers: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []
    for penta_id in changed:
        member = head.get(penta_id)
        if member is None:
            checked.append({"penta_id": penta_id, "change": "removed", "disposition": "NOT_APPLICABLE"})
            continue
        base_member = base.get(penta_id)
        change = "added" if base_member is None else "modified"
        report, reasons = _check_member_contract(root, member, entries.get(penta_id), policy)
        maturity = str(member["maturity"])
        require_verified = maturity in PRODUCTION_MATURITIES
        require_declaration = base_member is None or maturity in DECLARATION_MATURITIES
        verified = report is not None and not reasons and report["disposition"] == "VERIFIED"
        declared = report is not None and not reasons
        failed = (require_verified and not verified) or (require_declaration and not declared)
        row = {
            "penta_id": penta_id,
            "change": change,
            "maturity": maturity,
            "requires_verified_contract": require_verified,
            "requires_declaration": require_declaration,
            "contract_verified": bool(verified),
            "contract_declared": bool(declared),
            "disposition": "HOLD_FAIL_CLOSED" if failed else "PASS",
            "reasons": reasons,
        }
        checked.append(row)
        if failed:
            blockers.append(row)

    registered_contract_refs = {
        _safe_rel_path(str(entry.get("contract_ref") or ""), prefix="data/penta/survival-contracts"):
        penta_id
        for penta_id, entry in entries.items()
    }
    member_contract_refs = {penta_id: rel for rel, penta_id in registered_contract_refs.items()}
    contract_dir_prefix = "data/penta/survival-contracts/"
    changed_contract_paths = sorted(
        path for path in changed_paths if path.startswith(contract_dir_prefix) and path.endswith(".json")
    )
    unregistered_contract_paths = sorted(set(changed_contract_paths) - set(registered_contract_refs))
    for path in unregistered_contract_paths:
        row = {
            "penta_id": None,
            "change": "unregistered_contract_file",
            "contract_ref": path,
            "disposition": "HOLD_FAIL_CLOSED",
            "reasons": ["changed survival contract file is not registered"],
        }
        checked.append(row)
        blockers.append(row)

    proof_refs = _registered_proof_refs(root, entries)
    proof_dir_prefix = DEFAULT_PROOF_DIR.rstrip("/") + "/"
    changed_proof_paths = sorted(
        path for path in changed_paths if path.startswith(proof_dir_prefix) and path.endswith(".json")
    )
    unreferenced_proof_paths = sorted(set(changed_proof_paths) - set(proof_refs))
    for path in unreferenced_proof_paths:
        row = {
            "penta_id": None,
            "change": "unreferenced_proof_bundle",
            "proof_ref": path,
            "disposition": "HOLD_FAIL_CLOSED",
            "reasons": ["changed executed proof bundle is not referenced by a registered survival contract"],
        }
        checked.append(row)
        blockers.append(row)

    registry_changed = DEFAULT_REGISTRY in changed_paths
    semantic_paths = {
        DEFAULT_POLICY,
        DEFAULT_TEST_PLAN,
        "schemas/penta/penta-survival-contract-v1.schema.json",
        "schemas/penta/penta-survival-proof-v1.schema.json",
        "runtime/penta_survival.py",
        "scripts/validate_penta_survival.py",
    }
    global_contract_semantics_changed = bool(set(changed_paths) & semantic_paths)
    refs_to_validate = set(changed_contract_paths)
    refs_to_validate.update(
        member_contract_refs[penta_id]
        for path, penta_id in proof_refs.items()
        if path in changed_proof_paths and penta_id in member_contract_refs
    )
    if registry_changed or global_contract_semantics_changed:
        refs_to_validate.update(registered_contract_refs)
    already_checked_members = {str(row.get("penta_id")) for row in checked if row.get("penta_id")}
    for rel in sorted(refs_to_validate):
        penta_id = registered_contract_refs.get(rel)
        if penta_id is None:
            continue
        member = head.get(penta_id)
        if member is None:
            row = {
                "penta_id": penta_id,
                "change": "orphaned_registry_entry",
                "contract_ref": rel,
                "disposition": "HOLD_FAIL_CLOSED",
                "reasons": ["survival registry entry does not resolve to a registered Penta member"],
            }
            checked.append(row)
            blockers.append(row)
            continue
        report, reasons = _check_member_contract(root, member, entries.get(penta_id), policy)
        maturity = str(member["maturity"])
        verified = report is not None and not reasons and report["disposition"] == "VERIFIED"
        declared = report is not None and not reasons
        failed = not declared or (maturity in PRODUCTION_MATURITIES and not verified)
        row = {
            "penta_id": penta_id,
            "change": "contract_or_registry_modified",
            "contract_ref": rel,
            "maturity": maturity,
            "requires_verified_contract": maturity in PRODUCTION_MATURITIES,
            "contract_verified": bool(verified),
            "contract_declared": bool(declared),
            "disposition": "HOLD_FAIL_CLOSED" if failed else "PASS",
            "reasons": reasons,
        }
        if penta_id not in already_checked_members:
            checked.append(row)
        elif failed:
            checked.append(row)
        if failed:
            blockers.append(row)

    deduplicated_blockers: list[dict[str, Any]] = []
    seen_blockers: set[str] = set()
    for row in blockers:
        key = _canonical(row)
        if key not in seen_blockers:
            seen_blockers.add(key)
            deduplicated_blockers.append(row)
    output: dict[str, Any] = {
        "schema": RATCHET_SCHEMA_ID,
        "base_ref": base_ref,
        "changed_member_count": len(changed),
        "changed_path_count": len(changed_paths),
        "changed_contract_paths": changed_contract_paths,
        "changed_proof_paths": changed_proof_paths,
        "registry_changed": registry_changed,
        "global_contract_semantics_changed": global_contract_semantics_changed,
        "checked_members": checked,
        "blocker_count": len(deduplicated_blockers),
        "blockers": deduplicated_blockers,
        "disposition": "PASS" if not deduplicated_blockers else "HOLD_FAIL_CLOSED",
    }
    output["receipt_sha256"] = digest(output)
    return output


def release_gate(
    root: Path,
    penta_id: str,
    *,
    source_commit: str,
    artifact_sha256: str,
    doctrine_version: str | None = None,
    compiled_behavior_hash: str | None = None,
) -> dict[str, Any]:
    policy, registry = load_policy_and_registry(root)
    members = discover_family_members(root)
    entries = _registry_index(registry)
    reasons: list[str] = []
    control_plane_commit: str | None = None
    try:
        control_plane_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()
        subprocess.run(
            ["git", "cat-file", "-e", f"{source_commit}^{{commit}}"],
            cwd=root, check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, control_plane_commit],
            cwd=root, check=True, capture_output=True, text=True
        )
        if control_plane_commit == source_commit:
            reasons.append("proof metadata commit must differ from immutable candidate source_commit")
    except (OSError, subprocess.CalledProcessError):
        reasons.append("candidate source_commit is not an ancestor of the control-plane proof commit")
    member = members.get(penta_id)
    report: dict[str, Any] | None = None
    contract: dict[str, Any] | None = None
    if member is None:
        reasons.append("penta_id is not a registered Penta Family member")
    else:
        report, contract_reasons = _check_member_contract(root, member, entries.get(penta_id), policy)
        reasons.extend(contract_reasons)
        if entries.get(penta_id):
            rel = _safe_rel_path(str(entries[penta_id]["contract_ref"]), prefix="data/penta/survival-contracts")
            if (root / rel).exists():
                contract = _load_json(root / rel)
    if member and member.get("maturity") not in PRODUCTION_MATURITIES:
        reasons.append("member maturity is not certified or production")
    if report and report.get("disposition") != "VERIFIED":
        reasons.append("survival contract is not VERIFIED")
    if contract:
        release = contract.get("release_binding") if isinstance(contract.get("release_binding"), dict) else {}
        if release.get("source_commit") != source_commit:
            reasons.append("requested source_commit does not match survival contract")
        if release.get("artifact_sha256") != artifact_sha256:
            reasons.append("requested artifact_sha256 does not match survival contract")
        if doctrine_version is not None and release.get("doctrine_version") != doctrine_version:
            reasons.append("requested doctrine_version does not match survival contract")
        if compiled_behavior_hash is not None and release.get("compiled_behavior_hash") != compiled_behavior_hash:
            reasons.append("requested compiled_behavior_hash does not match survival contract")
    unique = sorted(set(reasons))
    output: dict[str, Any] = {
        "schema": RELEASE_SCHEMA_ID,
        "penta_id": penta_id,
        "source_commit": source_commit,
        "artifact_sha256": artifact_sha256,
        "doctrine_version": doctrine_version,
        "compiled_behavior_hash": compiled_behavior_hash,
        "control_plane_commit": control_plane_commit,
        "metadata_split_preserved": bool(control_plane_commit and control_plane_commit != source_commit),
        "survival_validation_receipt_sha256": report.get("receipt_sha256") if report else None,
        "disposition": "PASS" if not unique else "HOLD_FAIL_CLOSED",
        "reasons": unique,
        "production_promoted": False,
        "provider_write_performed": False,
        "authority_manufactured": False,
    }
    output["receipt_sha256"] = digest(output)
    return output


def _write_output(value: Mapping[str, Any], output: str | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate deterministic Penta survival contracts")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output", help="optional JSON receipt path")
    sub = parser.add_subparsers(dest="command", required=True)
    common_after_command = argparse.ArgumentParser(add_help=False)
    common_after_command.add_argument("--root", default=argparse.SUPPRESS, help="repository root")
    common_after_command.add_argument("--output", default=argparse.SUPPRESS, help="optional JSON receipt path")
    sub.add_parser(
        "audit",
        parents=[common_after_command],
        help="report full coverage; gaps remain visible but command exits zero",
    )
    sub.add_parser(
        "check",
        parents=[common_after_command],
        help="fail when any certified/production Penta lacks verified survival proof",
    )
    validate = sub.add_parser(
        "validate-contract", parents=[common_after_command], help="validate one contract file"
    )
    validate.add_argument("path")
    ratchet = sub.add_parser(
        "ratchet",
        parents=[common_after_command],
        help="block new/modified member gaps relative to a base git ref",
    )
    ratchet.add_argument("--base-ref", required=True)
    release = sub.add_parser(
        "release", parents=[common_after_command], help="gate an exact production candidate"
    )
    release.add_argument("--penta-id", required=True)
    release.add_argument("--source-commit", required=True)
    release.add_argument("--artifact-sha256", required=True)
    release.add_argument("--doctrine-version")
    release.add_argument("--compiled-behavior-hash")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command in {"audit", "check"}:
            result = coverage_report(root)
            _write_output(result, args.output)
            return 0 if args.command == "audit" or result["disposition"] == "PASS" else 1
        if args.command == "validate-contract":
            policy = _load_json(root / DEFAULT_POLICY)
            contract = _load_json((root / args.path).resolve())
            structural = evaluate_contract(contract, policy=policy)
            result, proof_reasons = _repository_validation_report(root, contract, structural)
            if proof_reasons:
                result["repository_proof_errors"] = sorted(set(proof_reasons))
                result.pop("receipt_sha256", None)
                result["receipt_sha256"] = digest(result)
            _write_output(result, args.output)
            return 0 if not result["errors"] and not proof_reasons else 1
        if args.command == "ratchet":
            result = ratchet_report(root, args.base_ref)
            _write_output(result, args.output)
            return 0 if result["disposition"] == "PASS" else 1
        if args.command == "release":
            result = release_gate(
                root,
                args.penta_id,
                source_commit=args.source_commit,
                artifact_sha256=args.artifact_sha256,
                doctrine_version=args.doctrine_version,
                compiled_behavior_hash=args.compiled_behavior_hash,
            )
            _write_output(result, args.output)
            return 0 if result["disposition"] == "PASS" else 1
    except PentaSurvivalError as exc:
        result = {
            "schema": "ct.penta.survival-error.v1",
            "disposition": "HOLD_FAIL_CLOSED",
            "error": str(exc),
        }
        result["receipt_sha256"] = digest(result)
        _write_output(result, args.output)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
