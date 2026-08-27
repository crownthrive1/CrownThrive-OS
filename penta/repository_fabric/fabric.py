#!/usr/bin/env python3
"""Deterministic repository convergence, cold fallback and emergency routing.

The fabric consumes provider observations.  It never discovers private provider
coordinates from public source and it never merges, changes visibility, or
dispatches a provider write.  Those effects remain in separately certified
adapters.  Its job is to validate identity/attestation evidence, select a
fail-closed route, emit bounded build candidates, and project sanitized state to
PentaBrain/PentaSpine/PentaNerves and the Command Center.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from penta.organic.body import OrganicControlPlane


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
STABLE_ID_RE = re.compile(r"^ct\.repo\.[a-z0-9][a-z0-9.-]*$")
PUBLIC_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REASON_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,127}$")
CONTROL_PLANE_KEYS = {
    "schema",
    "version",
    "control_plane_id",
    "canonical_hub_id",
    "owner",
    "institutional_phase",
    "state",
    "inventory",
    "information_flow",
    "failover",
    "release_governance",
    "build_dispatch",
    "invariants",
    "implementation",
}
PUBLIC_NODE_KEYS = {
    "stable_id",
    "repository",
    "default_branch",
    "expected_provider_visibility",
    "node_manifest_path",
    "roles",
    "visibility_class",
}
RESTRICTED_NODE_KEYS = {
    "stable_id",
    "locator",
    "default_branch",
    "expected_provider_visibility",
    "node_manifest_path",
    "roles",
    "visibility_class",
}


class ConvergenceError(ValueError):
    """Fail-closed repository-fabric contract violation."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _parse_time(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ConvergenceError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConvergenceError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ConvergenceError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _now(value: str | None) -> datetime:
    return _parse_time(value, "evaluated_at") if value else datetime.now(timezone.utc)


def _sealed(value: Mapping[str, Any], field: str) -> bool:
    claimed = value.get(field)
    if not isinstance(claimed, str) or not SHA256_RE.fullmatch(claimed):
        return False
    body = dict(value)
    body.pop(field, None)
    return canonical_sha256(body) == claimed


def _string_list(value: object) -> list[str] | None:
    """Return a clean, duplicate-free string list or fail shape validation."""
    if (
        not isinstance(value, list)
        or len(value) != len(set(item for item in value if isinstance(item, str)))
        or not all(
            isinstance(item, str) and item and item.strip() == item for item in value
        )
    ):
        return None
    return value


def _safe_public_node(node: Mapping[str, Any]) -> None:
    unexpected = sorted(set(node) - PUBLIC_NODE_KEYS)
    if unexpected:
        raise ConvergenceError("public node contains unsupported fields: " + ", ".join(unexpected))
    repository = node.get("repository")
    if not isinstance(repository, str) or not PUBLIC_REPOSITORY_RE.fullmatch(repository):
        raise ConvergenceError("public nodes require an owner/repository locator")
    if node.get("expected_provider_visibility") != "public":
        raise ConvergenceError("private provider coordinates must use restricted runtime bindings")


def _safe_restricted_node(node: Mapping[str, Any]) -> None:
    unexpected = sorted(set(node) - RESTRICTED_NODE_KEYS)
    if unexpected:
        raise ConvergenceError("restricted node contains unsupported fields: " + ", ".join(unexpected))
    forbidden = {
        "repository",
        "repository_id",
        "repository_url",
        "owner",
        "head_sha",
        "api_url",
        "clone_url",
        "emergency_route",
    }
    leaked = sorted(forbidden.intersection(node))
    if leaked:
        raise ConvergenceError(
            "restricted node exposes provider coordinates in public policy: " + ", ".join(leaked)
        )
    if node.get("locator") != "restricted_ref_only":
        raise ConvergenceError("restricted nodes must use restricted_ref_only")
    if node.get("expected_provider_visibility") != "private":
        raise ConvergenceError("restricted nodes must expect private provider visibility")


def _node_rows(policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    inventory = policy.get("inventory")
    if not isinstance(inventory, Mapping):
        raise ConvergenceError("inventory must be an object")
    public = inventory.get("public_nodes")
    restricted = inventory.get("restricted_nodes")
    if not isinstance(public, list) or not isinstance(restricted, list):
        raise ConvergenceError("public_nodes and restricted_nodes must be arrays")
    rows: list[dict[str, Any]] = []
    for raw in public:
        if not isinstance(raw, Mapping):
            raise ConvergenceError("public node must be an object")
        row = dict(raw)
        row["visibility_class"] = "public"
        _safe_public_node(row)
        rows.append(row)
    for raw in restricted:
        if not isinstance(raw, Mapping):
            raise ConvergenceError("restricted node must be an object")
        row = dict(raw)
        row["visibility_class"] = "restricted"
        _safe_restricted_node(row)
        rows.append(row)
    return rows


def validate_control_plane(policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Validate public-safe topology without resolving restricted locators."""
    if set(policy) != CONTROL_PLANE_KEYS:
        raise ConvergenceError("repository control-plane fields drifted")
    if policy.get("schema") != "ct.penta.repository-federation-control-plane.v1":
        raise ConvergenceError("unsupported repository control-plane schema")
    if policy.get("version") != "1.0.0":
        raise ConvergenceError("unsupported repository control-plane version")
    if policy.get("control_plane_id") != "ct.penta.repository-convergence":
        raise ConvergenceError("repository control-plane identity drifted")
    if policy.get("canonical_hub_id") != "ct.repo.crownthrive-support":
        raise ConvergenceError("canonical hub stable ID drifted")
    if (
        policy.get("owner") != "CrownThrive LLC"
        or policy.get("institutional_phase") != "phase_3_execute"
        or policy.get("state")
        != "controlled_test_pending_provider_binding_and_child_readback"
    ):
        raise ConvergenceError("repository control-plane authority state drifted")
    rules = policy.get("invariants")
    if not isinstance(rules, Mapping):
        raise ConvergenceError("invariants must be an object")
    required_true = {
        "private_coordinates_prohibited_in_public_source",
        "awareness_never_grants_authority",
        "direct_main_write_prohibited",
        "child_self_activation_prohibited",
        "unknown_or_stale_fails_closed",
        "build_dispatch_requires_exact_authority",
        "emergency_route_is_authority_reducing",
    }
    if set(rules) != required_true:
        raise ConvergenceError("repository control-plane invariants drifted")
    missing = sorted(name for name in required_true if rules.get(name) is not True)
    if missing:
        raise ConvergenceError("missing fail-closed invariants: " + ", ".join(missing))
    failover = policy.get("failover")
    if not isinstance(failover, Mapping):
        raise ConvergenceError("failover policy must be an object")
    if set(failover) != {"hot_primary", "cold_recovery", "silent_emergency"}:
        raise ConvergenceError("failover must define hot, cold and silent emergency routes")
    if not all(isinstance(failover[name], Mapping) for name in failover):
        raise ConvergenceError("every failover route must be an object")
    route_fields = {
        "hot_primary": {"mode", "ttl_seconds", "required"},
        "cold_recovery": {"mode", "max_age_seconds", "required", "provider_writes"},
        "silent_emergency": {
            "mode",
            "public_address",
            "external_broadcast",
            "authority_effect",
        },
    }
    if any(set(failover[name]) != fields for name, fields in route_fields.items()):
        raise ConvergenceError("repository failover route fields drifted")
    hot_ttl = failover["hot_primary"].get("ttl_seconds")
    cold_ttl = failover["cold_recovery"].get("max_age_seconds")
    if (
        not isinstance(hot_ttl, int)
        or isinstance(hot_ttl, bool)
        or hot_ttl not in range(60, 86_401)
    ):
        raise ConvergenceError("hot route TTL must be between 60 and 86400 seconds")
    if (
        not isinstance(cold_ttl, int)
        or isinstance(cold_ttl, bool)
        or cold_ttl not in range(hot_ttl, 604_801)
    ):
        raise ConvergenceError("cold route max age must be bounded and no shorter than hot TTL")
    if failover["silent_emergency"].get("public_address") != "restricted_ref_only":
        raise ConvergenceError("silent emergency address must remain restricted")
    if failover["cold_recovery"].get("mode") != "read_only_authority_reducing":
        raise ConvergenceError("cold recovery must be read-only and authority-reducing")
    if failover["cold_recovery"].get("provider_writes") is not False:
        raise ConvergenceError("cold recovery provider writes must remain disabled")
    if failover["silent_emergency"].get("external_broadcast") is not False:
        raise ConvergenceError("silent emergency broadcast must remain disabled")
    if failover["silent_emergency"].get("authority_effect") != "reduce_only":
        raise ConvergenceError("silent emergency authority must reduce only")
    if failover["hot_primary"].get("mode") != "live_provider_readback":
        raise ConvergenceError("hot route must use live provider readback")
    if failover["silent_emergency"].get("mode") != "local_hash_chained_restricted_handoff":
        raise ConvergenceError("silent emergency mode drifted")
    required_hot = _string_list(failover["hot_primary"].get("required"))
    required_cold = _string_list(failover["cold_recovery"].get("required"))
    if required_hot is None or set(required_hot) != {
        "repository_identity",
        "exact_head",
        "node_attestation",
        "build_readback",
    }:
        raise ConvergenceError("hot route evidence requirements drifted")
    if required_cold is None or set(required_cold) != {
        "content_digest",
        "external_signature_verification",
        "exact_head",
    }:
        raise ConvergenceError("cold route evidence requirements drifted")
    inventory = policy.get("inventory")
    if not isinstance(inventory, Mapping) or set(inventory) != {
        "expected_physical_repository_count",
        "public_nodes",
        "restricted_nodes",
    }:
        raise ConvergenceError("repository inventory fields drifted")
    rows = _node_rows(policy)
    expected_count = policy["inventory"].get("expected_physical_repository_count")
    if (
        not isinstance(expected_count, int)
        or isinstance(expected_count, bool)
        or expected_count <= 0
        or expected_count != len(rows)
    ):
        raise ConvergenceError("repository census does not match expected count")
    ids: set[str] = set()
    repositories: set[str] = set()
    for row in rows:
        stable_id = row.get("stable_id")
        if not isinstance(stable_id, str) or not STABLE_ID_RE.fullmatch(stable_id):
            raise ConvergenceError(f"invalid repository stable ID: {stable_id!r}")
        if stable_id in ids:
            raise ConvergenceError(f"duplicate repository stable ID: {stable_id}")
        ids.add(stable_id)
        repository = row.get("repository")
        if isinstance(repository, str):
            if repository.lower() in repositories:
                raise ConvergenceError(f"duplicate public repository locator: {repository}")
            repositories.add(repository.lower())
        if row.get("default_branch") != "main":
            raise ConvergenceError(f"unsupported default branch for {stable_id}")
        roles = row.get("roles")
        if (
            not isinstance(roles, list)
            or not roles
            or len(roles) != len(set(roles))
            or not all(isinstance(role, str) and role.strip() == role and role for role in roles)
        ):
            raise ConvergenceError(f"roles are required for {stable_id}")
        if row.get("node_manifest_path") != ".crownthrive/penta-node.v1.json":
            raise ConvergenceError(f"node manifest path drifted for {stable_id}")
    if policy["canonical_hub_id"] not in ids:
        raise ConvergenceError("canonical hub is missing from inventory")
    release = policy.get("release_governance")
    if not isinstance(release, Mapping):
        raise ConvergenceError("release governance policy must be an object")
    if set(release) != {
        "stable_id",
        "active_default_branch_ruleset_required",
        "required_check_contexts",
        "max_bypass_actor_count",
        "exact_head_success_required",
    }:
        raise ConvergenceError("release governance policy fields drifted")
    required_contexts = release.get("required_check_contexts")
    if (
        release.get("stable_id") != policy["canonical_hub_id"]
        or release.get("active_default_branch_ruleset_required") is not True
        or release.get("exact_head_success_required") is not True
        or release.get("max_bypass_actor_count") != 0
        or not isinstance(required_contexts, list)
        or not required_contexts
        or len(required_contexts) != len(set(required_contexts))
        or not all(isinstance(context, str) and context.strip() == context and context for context in required_contexts)
    ):
        raise ConvergenceError("release governance must require exact-head checks and zero bypass actors")
    dispatch = policy.get("build_dispatch")
    if not isinstance(dispatch, Mapping):
        raise ConvergenceError("build dispatch policy must be an object")
    if set(dispatch) != {
        "event_type",
        "default",
        "requires_exact_authority_lease",
        "allowed_effects",
        "prohibited_effects",
    }:
        raise ConvergenceError("build dispatch policy fields drifted")
    if dispatch.get("default") != "candidate_only" or dispatch.get("requires_exact_authority_lease") is not True:
        raise ConvergenceError("build dispatch must remain candidate-only and authority-bound")
    allowed = _string_list(dispatch.get("allowed_effects"))
    prohibited_values = _string_list(dispatch.get("prohibited_effects"))
    prohibited = set(prohibited_values or [])
    if allowed is None or set(allowed) != {
        "validate",
        "test",
        "compile",
        "package",
        "preserve-evidence",
    }:
        raise ConvergenceError("build dispatch allowed effects drifted")
    if prohibited_values is None or prohibited != {
        "merge",
        "visibility-change",
        "delete",
        "release-publish",
        "provider-secret-return",
    }:
        raise ConvergenceError("build dispatch prohibited effects are incomplete")
    information_flow = policy.get("information_flow")
    if not isinstance(information_flow, Mapping) or set(information_flow) != {
        "afferent",
        "efferent",
        "lateral",
    } or not all(
        isinstance(information_flow[name], str) and information_flow[name]
        for name in ("afferent", "efferent", "lateral")
    ):
        raise ConvergenceError("repository information-flow contract drifted")
    expected_flow = {
        "afferent": "repository telemetry -> PentaNerves -> PentaSpine -> PentaBrain",
        "efferent": "PentaBrain disposition -> exact authority -> PentaFactory/PentaPR",
        "lateral": "repository attestation -> PentaFederation -> peer receipt -> PentaSpine",
    }
    if dict(information_flow) != expected_flow:
        raise ConvergenceError("repository information-flow paths drifted")
    implementation = policy.get("implementation")
    if not isinstance(implementation, Mapping) or set(implementation) != {
        "runtime",
        "validator",
        "workflow",
        "tests",
        "node_schema",
    }:
        raise ConvergenceError("repository implementation bindings drifted")
    if dict(implementation) != {
        "runtime": "penta/repository_fabric",
        "validator": "scripts/validate_repository_federation.py",
        "workflow": ".github/workflows/penta-repository-convergence.yml",
        "tests": "tests/test_penta_repository_fabric.py",
        "node_schema": "schemas/penta/repository-node-attestation.schema.json",
    }:
        raise ConvergenceError("repository implementation paths drifted")
    return rows


@dataclass(frozen=True)
class RouteDecision:
    stable_id: str
    visibility_class: str
    route: str
    state: str
    reason_codes: tuple[str, ...]
    observed: bool
    head_sha: str | None
    build_state: str
    attestation_sha256: str | None


class EmergencyJournal:
    """Append-only local queue for authority-reducing emergency handoff evidence."""

    EVENT_KEYS = {
        "schema",
        "stable_id",
        "sequence",
        "previous_sha256",
        "reason_codes",
        "observed_at",
        "delivery_state",
        "external_broadcast",
        "authority_effect",
        "event_sha256",
    }

    def __init__(self, path: Path | None = None):
        self.path = path
        self.events: list[dict[str, Any]] = []
        if path and path.is_symlink():
            raise ConvergenceError("emergency journal may not be a symlink")
        if path and path.exists():
            if not path.is_file():
                raise ConvergenceError("emergency journal must be a regular file")
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ConvergenceError(f"invalid emergency journal line {line_number}") from exc
                if not isinstance(item, dict):
                    raise ConvergenceError("emergency journal entries must be objects")
                self.events.append(item)
            if not self.verify():
                raise ConvergenceError("emergency journal integrity failure")

    def append(self, stable_id: str, reason_codes: Iterable[str], observed_at: str) -> dict[str, Any]:
        if not STABLE_ID_RE.fullmatch(stable_id):
            raise ConvergenceError("emergency journal stable ID is invalid")
        _parse_time(observed_at, "emergency.observed_at")
        normalized_reasons = sorted(set(reason_codes))
        if not normalized_reasons or not all(
            isinstance(reason, str) and REASON_CODE_RE.fullmatch(reason)
            for reason in normalized_reasons
        ):
            raise ConvergenceError("emergency reason codes are invalid")
        body: dict[str, Any] = {
            "schema": "ct.penta.repository-emergency-handoff.v1",
            "stable_id": stable_id,
            "sequence": len(self.events) + 1,
            "previous_sha256": self.events[-1]["event_sha256"] if self.events else "GENESIS",
            "reason_codes": normalized_reasons,
            "observed_at": observed_at,
            "delivery_state": "local_sealed_pending_authorized_restricted_route",
            "external_broadcast": False,
            "authority_effect": "reduce_only",
        }
        body["event_sha256"] = canonical_sha256(body)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.is_symlink():
                raise ConvergenceError("emergency journal may not be a symlink")
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            flags |= getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(self.path, flags, 0o600)
            except OSError as exc:
                raise ConvergenceError("emergency journal could not be opened safely") from exc
            with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        self.events.append(body)
        return body

    def verify(self) -> bool:
        previous = "GENESIS"
        for sequence, event in enumerate(self.events, start=1):
            if set(event) != self.EVENT_KEYS:
                return False
            if (
                event.get("schema") != "ct.penta.repository-emergency-handoff.v1"
                or not isinstance(event.get("stable_id"), str)
                or not STABLE_ID_RE.fullmatch(event["stable_id"])
                or event.get("delivery_state")
                != "local_sealed_pending_authorized_restricted_route"
                or event.get("external_broadcast") is not False
                or event.get("authority_effect") != "reduce_only"
                or not isinstance(event.get("reason_codes"), list)
                or event["reason_codes"] != sorted(set(event["reason_codes"]))
                or not event["reason_codes"]
                or not all(
                    isinstance(reason, str) and REASON_CODE_RE.fullmatch(reason)
                    for reason in event["reason_codes"]
                )
            ):
                return False
            try:
                _parse_time(event.get("observed_at"), "emergency.observed_at")
            except ConvergenceError:
                return False
            body = dict(event)
            claimed = body.pop("event_sha256", None)
            if not isinstance(claimed, str) or not SHA256_RE.fullmatch(claimed):
                return False
            if body.get("sequence") != sequence or body.get("previous_sha256") != previous:
                return False
            if canonical_sha256(body) != claimed:
                return False
            previous = str(claimed)
        return True


class RepositoryFabric:
    """Select hot/cold/emergency paths and produce public-safe convergence state."""

    def __init__(
        self,
        policy: Mapping[str, Any],
        *,
        emergency_journal: Path | None = None,
        observation_verifier: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None,
        cold_snapshot_verifier: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None,
    ):
        self.policy = dict(policy)
        rows = validate_control_plane(self.policy)
        self.nodes = {row["stable_id"]: row for row in rows}
        self.emergency = EmergencyJournal(emergency_journal)
        self.observation_verifier = observation_verifier
        self.cold_snapshot_verifier = cold_snapshot_verifier

    def _validate_observation(
        self,
        spec: Mapping[str, Any],
        observation: Mapping[str, Any],
        evaluated_at: datetime,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if observation.get("schema") != "ct.penta.repository-observation.v1":
            reasons.append("observation_schema_invalid")
            return False, reasons
        if not _sealed(observation, "observation_sha256"):
            reasons.append("observation_digest_invalid")
        if observation.get("source_adapter") != "ct.adapter.github-repository-read.v1":
            reasons.append("provider_adapter_invalid")
        try:
            independently_verified = (
                self.observation_verifier is not None
                and self.observation_verifier(spec, observation) is True
            )
        except Exception:  # external verifier failures must reduce authority
            independently_verified = False
        if not independently_verified:
            reasons.append("provider_observation_unverified")
        if observation.get("stable_id") != spec["stable_id"]:
            reasons.append("stable_id_mismatch")
        observed_at = _parse_time(observation.get("observed_at"), "observation.observed_at")
        ttl = int(self.policy["failover"]["hot_primary"]["ttl_seconds"])
        age = (evaluated_at - observed_at).total_seconds()
        if age < -300:
            reasons.append("observation_from_future")
        elif age > ttl:
            reasons.append("observation_stale")
        head = observation.get("head_sha")
        if not isinstance(head, str) or not GIT_SHA_RE.fullmatch(head):
            reasons.append("head_sha_invalid")
        if observation.get("default_branch") != spec["default_branch"]:
            reasons.append("default_branch_mismatch")
        expected_visibility = spec.get("expected_provider_visibility")
        if observation.get("provider_visibility") != expected_visibility:
            reasons.append("provider_visibility_mismatch")
        attestation = observation.get("node_attestation")
        if not isinstance(attestation, Mapping):
            reasons.append("node_attestation_missing")
        else:
            if attestation.get("schema") != "ct.penta.repository-node-attestation.v1":
                reasons.append("node_attestation_schema_invalid")
            if attestation.get("stable_id") != spec["stable_id"]:
                reasons.append("node_attestation_identity_mismatch")
            if attestation.get("parent_id") != "ct.repo.crownthrive-support":
                reasons.append("node_attestation_parent_mismatch")
            if attestation.get("mesh_contract_version") != self.policy.get("version"):
                reasons.append("mesh_contract_version_mismatch")
            if attestation.get("default_branch") != spec["default_branch"]:
                reasons.append("node_attestation_branch_mismatch")
            expected_attestation_visibility = (
                "restricted" if spec.get("expected_provider_visibility") == "private" else "public"
            )
            if attestation.get("visibility_class") != expected_attestation_visibility:
                reasons.append("node_attestation_visibility_mismatch")
            attested_roles = _string_list(attestation.get("roles"))
            if attested_roles is None or sorted(attested_roles) != sorted(spec["roles"]):
                reasons.append("node_attestation_roles_mismatch")
            if not isinstance(attestation.get("build_profile"), str) or not attestation["build_profile"]:
                reasons.append("node_attestation_build_profile_missing")
            authority = attestation.get("authority")
            required_authority = {
                "direct_main_write": False,
                "self_activation": False,
                "d3_human_reserved": True,
                "provider_writes_require_exact_certification": True,
            }
            if not isinstance(authority, Mapping) or any(
                authority.get(field) is not expected for field, expected in required_authority.items()
            ):
                reasons.append("node_attestation_authority_invalid")
            information_flow = _string_list(attestation.get("information_flow"))
            if information_flow is None or sorted(information_flow) != [
                "afferent",
                "efferent",
                "lateral",
            ]:
                reasons.append("node_attestation_information_flow_invalid")
            claimed = observation.get("node_attestation_sha256")
            if claimed != canonical_sha256(attestation):
                reasons.append("node_attestation_digest_mismatch")
        release_policy = self.policy["release_governance"]
        if spec["stable_id"] == release_policy["stable_id"]:
            governance = observation.get("release_governance")
            required_contexts = sorted(release_policy["required_check_contexts"])
            if not isinstance(governance, Mapping):
                reasons.append("release_governance_readback_missing")
            else:
                if governance.get("head_sha") != observation.get("head_sha"):
                    reasons.append("release_governance_head_mismatch")
                if governance.get("active_default_branch_ruleset") is not True:
                    reasons.append("release_ruleset_inactive_or_missing")
                bypass_count = governance.get("bypass_actor_count")
                if (
                    not isinstance(bypass_count, int)
                    or isinstance(bypass_count, bool)
                    or bypass_count > release_policy["max_bypass_actor_count"]
                    or bypass_count < 0
                ):
                    reasons.append("release_ruleset_bypass_present")
                observed_required = _string_list(governance.get("required_contexts"))
                if observed_required is None or sorted(observed_required) != required_contexts:
                    reasons.append("release_required_context_drift")
                observed_successful = _string_list(governance.get("successful_contexts"))
                if observed_successful is None or sorted(observed_successful) != required_contexts:
                    reasons.append("release_exact_head_gate_unsuccessful")
                applicable_count = governance.get("applicable_ruleset_count")
                if (
                    not isinstance(applicable_count, int)
                    or isinstance(applicable_count, bool)
                    or applicable_count <= 0
                ):
                    reasons.append("release_ruleset_inactive_or_missing")
                if governance.get("all_ruleset_contexts_successful") is not True:
                    reasons.append("release_ruleset_context_unsuccessful")
                if governance.get("state") != "passed":
                    reasons.append("release_governance_not_passed")
        return not reasons, reasons

    def _validate_cold(
        self,
        spec: Mapping[str, Any],
        cold: Mapping[str, Any] | None,
        evaluated_at: datetime,
    ) -> tuple[bool, list[str]]:
        if not isinstance(cold, Mapping):
            return False, ["cold_snapshot_missing"]
        reasons: list[str] = []
        if cold.get("schema") != "ct.penta.repository-cold-snapshot.v1":
            reasons.append("cold_snapshot_schema_invalid")
        if cold.get("stable_id") != spec["stable_id"]:
            reasons.append("cold_snapshot_identity_mismatch")
        if not _sealed(cold, "snapshot_sha256"):
            reasons.append("cold_snapshot_digest_invalid")
        if self.cold_snapshot_verifier is None:
            reasons.append("cold_snapshot_verifier_unbound")
        else:
            try:
                verified = self.cold_snapshot_verifier(spec, cold)
            except Exception:  # an external verifier must never break fail-closed routing
                verified = False
            if verified is not True:
                reasons.append("cold_snapshot_signature_unverified")
        if cold.get("signature_verified") is not True:
            reasons.append("cold_snapshot_signature_unverified")
        if cold.get("restore_mode") != "read_only":
            reasons.append("cold_snapshot_not_read_only")
        created = _parse_time(cold.get("created_at"), "cold_snapshot.created_at")
        ttl = int(self.policy["failover"]["cold_recovery"]["max_age_seconds"])
        age = (evaluated_at - created).total_seconds()
        if age < -300 or age > ttl:
            reasons.append("cold_snapshot_expired")
        head = cold.get("head_sha")
        if not isinstance(head, str) or not GIT_SHA_RE.fullmatch(head):
            reasons.append("cold_snapshot_head_invalid")
        return not reasons, reasons

    def reconcile(
        self,
        observations: Mapping[str, Mapping[str, Any]],
        *,
        cold_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
        evaluated_at: str | None = None,
    ) -> dict[str, Any]:
        now = _now(evaluated_at)
        now_text = now.isoformat()
        cold_snapshots = cold_snapshots or {}
        unknown = sorted(set(observations) - set(self.nodes))
        if unknown:
            raise ConvergenceError("observations contain unknown nodes: " + ", ".join(unknown))
        unknown_cold = sorted(set(cold_snapshots) - set(self.nodes))
        if unknown_cold:
            raise ConvergenceError(
                "cold snapshots contain unknown nodes: " + ", ".join(unknown_cold)
            )

        decisions: list[RouteDecision] = []
        build_candidates: list[dict[str, Any]] = []
        for stable_id in sorted(self.nodes):
            spec = self.nodes[stable_id]
            observation = observations.get(stable_id)
            live_ok = False
            live_reasons = ["live_observation_missing"]
            if isinstance(observation, Mapping):
                live_ok, live_reasons = self._validate_observation(spec, observation, now)
            if live_ok and observation is not None:
                head = str(observation["head_sha"])
                build = observation.get("build") if isinstance(observation.get("build"), Mapping) else {}
                build_state = str(build.get("state", "unknown"))
                built_head = build.get("head_sha")
                if build_state != "passed" or built_head != head:
                    build_candidates.append(
                        {
                            "stable_id": stable_id,
                            "candidate_id": "build-" + canonical_sha256({"stable_id": stable_id, "head_sha": head})[:20],
                            "head_sha": head if spec["visibility_class"] == "public" else "restricted",
                            "state": "candidate_pending_exact_authority",
                            "dispatch_allowed": False,
                            "reason": "head has no matching successful build readback",
                        }
                    )
                decisions.append(
                    RouteDecision(
                        stable_id,
                        spec["visibility_class"],
                        "hot_primary",
                        "live_readback_verified",
                        tuple(),
                        True,
                        head,
                        build_state,
                        str(observation.get("node_attestation_sha256")),
                    )
                )
                continue

            cold = cold_snapshots.get(stable_id)
            cold_ok, cold_reasons = self._validate_cold(spec, cold, now)
            if cold_ok and cold is not None:
                decisions.append(
                    RouteDecision(
                        stable_id,
                        spec["visibility_class"],
                        "cold_recovery",
                        "degraded_read_only",
                        tuple(live_reasons),
                        False,
                        str(cold["head_sha"]),
                        "not_executable_from_cold_awareness",
                        None,
                    )
                )
                continue

            reasons = tuple(sorted(set(live_reasons + cold_reasons)))
            self.emergency.append(stable_id, reasons, now_text)
            decisions.append(
                RouteDecision(
                    stable_id,
                    spec["visibility_class"],
                    "silent_emergency",
                    "hold_fail_closed",
                    reasons,
                    False,
                    None,
                    "blocked",
                    None,
                )
            )

        counts = {
            route: sum(1 for decision in decisions if decision.route == route)
            for route in ("hot_primary", "cold_recovery", "silent_emergency")
        }
        system_state = (
            "hold_emergency"
            if counts["silent_emergency"]
            else "degraded_read_only"
            if counts["cold_recovery"]
            else "hot_operational"
        )
        public_nodes: list[dict[str, Any]] = []
        restricted_nodes: list[dict[str, Any]] = []
        for decision in decisions:
            item: dict[str, Any] = {
                "stable_id": decision.stable_id,
                "route": decision.route,
                "state": decision.state,
                "reason_codes": list(decision.reason_codes),
                "build_state": decision.build_state,
            }
            if decision.visibility_class == "public":
                item["head_sha"] = decision.head_sha
                item["node_attestation_sha256"] = decision.attestation_sha256
                item["repository"] = self.nodes[decision.stable_id]["repository"]
                public_nodes.append(item)
            else:
                item["provider_coordinates"] = "restricted"
                item["head_state"] = "observed_restricted" if decision.head_sha else "unavailable"
                restricted_nodes.append(item)

        result: dict[str, Any] = {
            "schema": "ct.penta.repository-convergence-result.v1",
            "version": self.policy["version"],
            "evaluated_at": now_text,
            "canonical_hub_id": self.policy["canonical_hub_id"],
            "system_state": system_state,
            "expected_repository_count": len(self.nodes),
            "route_counts": counts,
            "public_nodes": public_nodes,
            "restricted_nodes": restricted_nodes,
            "restricted_node_count": len(restricted_nodes),
            "build_candidates": build_candidates,
            "information_flow": {
                "afferent": {
                    "path": "repository -> PentaNerves -> PentaSpine -> PentaBrain",
                    "state": "active" if counts["hot_primary"] else "hold",
                    "authority_effect": "none",
                },
                "efferent": {
                    "path": "PentaBrain -> authority gate -> PentaFactory/PentaPR",
                    "state": "candidate_only",
                    "provider_write": False,
                },
                "lateral": {
                    "path": "repository -> PentaFederation -> peer receipt",
                    "state": "verification_only",
                    "direct_peer_authority": False,
                },
            },
            "emergency": {
                "queued_count": len(self.emergency.events),
                "journal_integrity": self.emergency.verify(),
                "route_address": "restricted_ref_only",
                "external_broadcast": False,
                "authority_effect": "reduce_only",
            },
            "release_gate": {
                "stable_id": self.policy["release_governance"]["stable_id"],
                "required_contexts": list(
                    self.policy["release_governance"]["required_check_contexts"]
                ),
                "max_bypass_actor_count": 0,
                "state": (
                    "evidence_eligible_pending_separate_release_authority"
                    if any(
                        decision.stable_id == self.policy["release_governance"]["stable_id"]
                        and decision.route == "hot_primary"
                        for decision in decisions
                    )
                    else "hold_exact_head_gate_or_ruleset_boundary"
                ),
                "release_authority_created": False,
            },
            "authority_invariant": "Awareness, reachability, CI and build candidates never manufacture merge, provider, D3, rights, economic or release authority.",
        }
        result["result_sha256"] = canonical_sha256(result)
        return result

    def project_to_organic(
        self,
        result: Mapping[str, Any],
        organic: OrganicControlPlane,
        *,
        identity: Mapping[str, Any],
        observed_at: str,
    ) -> dict[str, Any]:
        """Project sanitized repository health through Nerves/Spine/Brain."""
        claimed = result.get("result_sha256")
        result_body = dict(result)
        result_body.pop("result_sha256", None)
        if not isinstance(claimed, str) or canonical_sha256(result_body) != claimed:
            raise ConvergenceError("repository convergence result integrity failure")
        nodes = list(result.get("public_nodes", [])) + list(result.get("restricted_nodes", []))
        route_health = {"hot_primary": 1.0, "cold_recovery": 0.55, "silent_emergency": 0.1}
        route_redundancy = {"hot_primary": 2, "cold_recovery": 1, "silent_emergency": 0}
        for index, node in enumerate(nodes):
            route = str(node["route"])
            signal = {
                "schema": "ct.penta.nerve-signal.v1",
                "signal_id": f"ct.signal.repository.{index}.{str(result['result_sha256'])[:16]}",
                "signal_type": "repository_signal",
                "information_direction": "afferent",
                "identity": dict(identity),
                "organ": {
                    "organ_id": node["stable_id"],
                    "health": route_health[route],
                    "load": 0.5,
                    "cost": 0.0,
                    "capacity": 1.0,
                    "redundancy": route_redundancy[route],
                },
            }
            organic.ingest(signal, observed_at=observed_at, received_at=observed_at)
        snapshot = organic.command_center_snapshot()
        return {
            "schema": "ct.command-center.repository-fabric.v1",
            "repository_fabric_result_sha256": result["result_sha256"],
            "system_state": result["system_state"],
            "expected_repository_count": result["expected_repository_count"],
            "route_counts": result["route_counts"],
            "organic_snapshot": snapshot,
            "private_coordinates_included": False,
        }
