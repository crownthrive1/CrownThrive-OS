#!/usr/bin/env python3
"""Deterministic CrownThrive collision intent, RTC, and repair primitives.

This module is deliberately provider-neutral and uses only the Python standard
library.  GitHub observation lives in ``governed_collision_agent_v2.py`` and
durable lease/event persistence lives behind the private CHLOM runtime.  Keeping
the classifier pure makes the same decision replayable in CI, tests, and RTC.

The executable never merges, force-pushes, deletes, spends money, changes
provider configuration, decides ownership/rights, or expands its own authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import sys
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "2.0.0"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
AGENT_ID = re.compile(r"^ct\.(?:agent|subagent)\.[a-z0-9][a-z0-9.-]*$")

DOMAIN_TYPES = {
    "path",
    "stable_id",
    "route",
    "runtime_resource",
    "schedule_slot",
    "authority_claim",
    "rights_claim",
    "provider_reference",
    "source_generation",
}
ACCESS_MODES = {"observe", "mutate", "create", "retire"}
MUTATING_ACCESS = {"mutate", "create", "retire"}

CONSTITUTIONAL_PATH_PREFIXES = (
    "constitution/",
    "governance/sovereign/",
    "authority/",
    "delegations/",
)
SHARED_PATH_SURFACES = {
    "docs.json": "mintlify_navigation",
    "index.mdx": "mintlify_homepage",
    ".github/workflows": "github_workflows",
    "developers/manifests": "agent_manifests",
    "supabase/migrations": "runtime_schema",
    "contracts": "contracts",
    "standards": "standards",
}


class ContractError(ValueError):
    """A fail-closed error in an intent, event, lease, or plan contract."""


class Disposition(str, Enum):
    CLEAR = "CLEAR"
    ALLOW_AWARE = "ALLOW_AWARE"
    HOLD = "HOLD"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    DENY = "DENY"


class RepairState(str, Enum):
    DETECTED = "DETECTED"
    HELD = "HELD"
    PLANNED = "PLANNED"
    LEASED = "LEASED"
    APPLYING = "APPLYING"
    VERIFYING = "VERIFYING"
    REPAIRED = "REPAIRED"
    ROLLED_BACK = "ROLLED_BACK"
    DEAD_LETTER = "DEAD_LETTER"


COLLISION_CLASSES = {
    0: "CT-COLL-0_CLEAR",
    1: "CT-COLL-1_AWARENESS_OR_SOFT_OVERLAP",
    2: "CT-COLL-2_DIRECT_FILE_OR_SEQUENCE",
    3: "CT-COLL-3_SEMANTIC_IDENTITY_RIGHTS_OR_GENERATION",
    4: "CT-COLL-4_RUNTIME_PROVIDER_OR_SCHEDULE_MUTATION",
    5: "CT-COLL-5_CONSTITUTIONAL_D3_OR_UNKNOWN_AUTHORITY",
}

SAFE_REPAIR_ACTIONS = {
    "awareness_receipt",
    "expired_lease_release",
    "retry_reschedule",
    "dead_letter_transition",
    "stack_dependency_draft",
    "split_scope_proposal",
    "review_rebind_required",
    "supersession_link_draft",
}
PROHIBITED_ACTIONS = {
    "merge",
    "force_push",
    "delete",
    "provider_write",
    "money_movement",
    "credential_rotation",
    "rights_determination",
    "authority_expansion",
    "self_approval",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ContractError("timestamp_timezone_required")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_uuid(value: str, field_name: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ContractError(f"{field_name}_must_be_uuid") from exc


def normalize_path(raw: str) -> str:
    """Return a repository-relative POSIX path or fail closed.

    A path never becomes a runtime/security collision merely because prose in
    its filename contains words such as "vault" or "credential".  Elevated
    semantics require an explicit structured claim.
    """

    if not isinstance(raw, str) or not raw.strip():
        raise ContractError("path_required")
    if "\x00" in raw or "\\" in raw:
        raise ContractError("path_contains_forbidden_character")
    candidate = raw.strip()
    if candidate.startswith("/"):
        raise ContractError("absolute_path_forbidden")
    normalized = posixpath.normpath(candidate)
    if normalized in {".", ".."} or normalized.startswith("../"):
        raise ContractError("path_traversal_forbidden")
    if len(normalized.encode("utf-8")) > 1024:
        raise ContractError("path_too_long")
    return normalized


def normalize_key(domain_type: str, raw: str) -> str:
    if domain_type not in DOMAIN_TYPES:
        raise ContractError("unknown_domain_type")
    if domain_type == "path":
        return normalize_path(raw)
    if not isinstance(raw, str) or not raw.strip():
        raise ContractError("claim_key_required")
    value = " ".join(raw.strip().split())
    if "\x00" in value or len(value.encode("utf-8")) > 512:
        raise ContractError("invalid_claim_key")
    return value.casefold()


def validate_sha(value: str, field_name: str, *, length: int) -> str:
    pattern = HEX40 if length == 40 else HEX64
    candidate = str(value).lower()
    if not pattern.fullmatch(candidate):
        raise ContractError(f"{field_name}_must_be_{length}_hex")
    return candidate


@dataclass(frozen=True, order=True)
class Claim:
    domain_type: str
    key: str
    access: str = "mutate"
    value_digest: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Claim":
        domain_type = str(raw.get("domain_type", ""))
        access = str(raw.get("access", ""))
        if access not in ACCESS_MODES:
            raise ContractError("unknown_access_mode")
        key = normalize_key(domain_type, raw.get("key", ""))
        digest = raw.get("value_digest")
        if digest is not None:
            digest = validate_sha(str(digest), "value_digest", length=64)
        return cls(domain_type=domain_type, key=key, access=access, value_digest=digest)

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "domain_type": self.domain_type,
            "key": self.key,
            "access": self.access,
        }
        if self.value_digest:
            value["value_digest"] = self.value_digest
        return value


@dataclass(frozen=True)
class Intent:
    repository: str
    target_kind: str
    target_id: str
    agent_id: str
    agent_instance_id: str
    base_sha: str
    head_sha: str
    executable_sha256: str
    config_sha256: str
    policy_sha256: str
    correlation_id: str
    claims: tuple[Claim, ...]
    authority_class: str = "D1"
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Intent":
        if raw.get("schema_version") != SCHEMA_VERSION:
            raise ContractError("unsupported_schema_version")
        repository = str(raw.get("repository", ""))
        if not REPOSITORY.fullmatch(repository):
            raise ContractError("repository_must_be_owner_name")
        target = raw.get("target")
        agent = raw.get("agent")
        versions = raw.get("versions")
        if not all(isinstance(item, Mapping) for item in (target, agent, versions)):
            raise ContractError("target_agent_and_versions_required")
        agent_id = str(agent.get("agent_id", ""))
        if not AGENT_ID.fullmatch(agent_id):
            raise ContractError("invalid_agent_id")
        target_kind = str(target.get("kind", ""))
        if target_kind not in {"pull_request", "branch", "runtime_packet", "record"}:
            raise ContractError("invalid_target_kind")
        target_id = str(target.get("id", "")).strip()
        if not target_id:
            raise ContractError("target_id_required")
        authority = str(raw.get("authority_class", "D1"))
        if authority not in {"D0", "D1", "D2", "D3"}:
            raise ContractError("invalid_authority_class")
        claims_raw = raw.get("claims")
        if not isinstance(claims_raw, list) or not claims_raw:
            raise ContractError("at_least_one_claim_required")
        claims = tuple(sorted({Claim.from_mapping(item) for item in claims_raw}))
        return cls(
            repository=repository,
            target_kind=target_kind,
            target_id=target_id,
            agent_id=agent_id,
            agent_instance_id=parse_uuid(agent.get("instance_id", ""), "agent_instance_id"),
            base_sha=validate_sha(versions.get("base_sha", ""), "base_sha", length=40),
            head_sha=validate_sha(versions.get("head_sha", ""), "head_sha", length=40),
            executable_sha256=validate_sha(
                versions.get("executable_sha256", ""), "executable_sha256", length=64
            ),
            config_sha256=validate_sha(versions.get("config_sha256", ""), "config_sha256", length=64),
            policy_sha256=validate_sha(versions.get("policy_sha256", ""), "policy_sha256", length=64),
            correlation_id=parse_uuid(raw.get("correlation_id", ""), "correlation_id"),
            claims=claims,
            authority_class=authority,
            intent_id=parse_uuid(raw.get("intent_id", str(uuid.uuid4())), "intent_id"),
        )

    @property
    def fingerprint(self) -> str:
        # Run-local UUIDs and correlation IDs are intentionally excluded.  The
        # same actor, target, versions and claims must replay to the same intent
        # fingerprint after a worker restart.
        return sha256_json(
            {
                "schema_version": SCHEMA_VERSION,
                "repository": self.repository,
                "target": {"kind": self.target_kind, "id": self.target_id},
                "agent_id": self.agent_id,
                "versions": {
                    "base_sha": self.base_sha,
                    "head_sha": self.head_sha,
                    "executable_sha256": self.executable_sha256,
                    "config_sha256": self.config_sha256,
                    "policy_sha256": self.policy_sha256,
                },
                "authority_class": self.authority_class,
                "claims": [claim.as_dict() for claim in self.claims],
            }
        )

    def as_dict(self, *, include_intent_id: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "repository": self.repository,
            "target": {"kind": self.target_kind, "id": self.target_id},
            "agent": {"agent_id": self.agent_id, "instance_id": self.agent_instance_id},
            "versions": {
                "base_sha": self.base_sha,
                "head_sha": self.head_sha,
                "executable_sha256": self.executable_sha256,
                "config_sha256": self.config_sha256,
                "policy_sha256": self.policy_sha256,
            },
            "authority_class": self.authority_class,
            "correlation_id": self.correlation_id,
            "claims": [claim.as_dict() for claim in self.claims],
        }
        if include_intent_id:
            value["intent_id"] = self.intent_id
        return value


def path_surface(path: str) -> str | None:
    for prefix, surface in SHARED_PATH_SURFACES.items():
        if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
            return surface
    first = path.split("/", 1)[0]
    return f"directory:{first}" if "/" in path else None


def is_mutating(left: Claim, right: Claim) -> bool:
    return left.access in MUTATING_ACCESS or right.access in MUTATING_ACCESS


@dataclass(frozen=True)
class Collision:
    severity: int
    collision_class: str
    domains: tuple[str, ...]
    reasons: tuple[str, ...]
    left_intent_id: str
    right_intent_id: str
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "class": self.collision_class,
            "domains": list(self.domains),
            "reasons": list(self.reasons),
            "left_intent_id": self.left_intent_id,
            "right_intent_id": self.right_intent_id,
            "collision_fingerprint": self.fingerprint,
        }


def classify_collision(left: Intent, right: Intent) -> Collision:
    if left.repository.casefold() != right.repository.casefold():
        return _collision_result(0, (), ("different_repository",), left, right)
    if left.intent_id == right.intent_id:
        return _collision_result(0, (), ("same_intent",), left, right)

    severity = 0
    reasons: set[str] = set()
    domains: set[str] = set()
    right_by_domain = {(c.domain_type, c.key): c for c in right.claims}

    for lclaim in left.claims:
        rclaim = right_by_domain.get((lclaim.domain_type, lclaim.key))
        if rclaim is None or not is_mutating(lclaim, rclaim):
            continue
        domain = f"{lclaim.domain_type}:{lclaim.key}"
        domains.add(domain)
        if lclaim.domain_type == "path":
            inherited_identical = (
                lclaim.value_digest is not None
                and lclaim.value_digest == rclaim.value_digest
                and (left.base_sha == right.head_sha or right.base_sha == left.head_sha)
            )
            if inherited_identical:
                severity = max(severity, 1)
                reasons.add("byte_identical_inherited_path_overlap")
            elif any(lclaim.key.startswith(prefix) for prefix in CONSTITUTIONAL_PATH_PREFIXES):
                severity = max(severity, 5)
                reasons.add("constitutional_path_parallel_mutation")
            else:
                severity = max(severity, 2)
                reasons.add("exact_path_parallel_mutation")
        elif lclaim.domain_type in {"runtime_resource", "schedule_slot", "provider_reference"}:
            severity = max(severity, 4)
            reasons.add(f"{lclaim.domain_type}_parallel_mutation")
        elif lclaim.domain_type in {
            "stable_id",
            "route",
            "rights_claim",
            "authority_claim",
            "source_generation",
        }:
            severity = max(severity, 3)
            suffix = "_conflicting_value" if lclaim.value_digest != rclaim.value_digest else "_parallel_claim"
            reasons.add(lclaim.domain_type + suffix)

    left_paths = [c for c in left.claims if c.domain_type == "path" and c.access in MUTATING_ACCESS]
    right_paths = [c for c in right.claims if c.domain_type == "path" and c.access in MUTATING_ACCESS]
    left_surfaces = {path_surface(c.key) for c in left_paths} - {None}
    right_surfaces = {path_surface(c.key) for c in right_paths} - {None}
    for surface in sorted(left_surfaces & right_surfaces):
        domains.add(f"surface:{surface}")
        if severity < 2:
            severity = max(severity, 1)
            reasons.add("shared_surface_awareness")

    if left.authority_class == "D3" or right.authority_class == "D3":
        if domains:
            severity = 5
            reasons.add("d3_authority_requires_human_quorum")

    if not reasons:
        reasons.add("no_material_overlap")
    return _collision_result(severity, tuple(sorted(domains)), tuple(sorted(reasons)), left, right)


def _collision_result(
    severity: int,
    domains: Sequence[str],
    reasons: Sequence[str],
    left: Intent,
    right: Intent,
) -> Collision:
    endpoint_fingerprints = sorted((left.fingerprint, right.fingerprint))
    core = {
        "schema_version": SCHEMA_VERSION,
        "endpoint_intent_fingerprints": endpoint_fingerprints,
        "severity": severity,
        "domains": sorted(domains),
        "reasons": sorted(reasons),
    }
    return Collision(
        severity=severity,
        collision_class=COLLISION_CLASSES[severity],
        domains=tuple(sorted(domains)),
        reasons=tuple(sorted(reasons)),
        left_intent_id=left.intent_id,
        right_intent_id=right.intent_id,
        fingerprint=sha256_json(core),
    )


def disposition_for(collisions: Iterable[Collision]) -> dict[str, Any]:
    items = list(collisions)
    maximum = max((item.severity for item in items), default=0)
    if maximum >= 5:
        disposition = Disposition.HUMAN_REVIEW_REQUIRED
    elif maximum >= 2:
        disposition = Disposition.HOLD
    elif maximum == 1:
        disposition = Disposition.ALLOW_AWARE
    else:
        disposition = Disposition.CLEAR
    return {
        "disposition": disposition.value,
        "max_severity": maximum,
        "reason_codes": sorted({reason for item in items for reason in item.reasons}),
        "collision_fingerprints": sorted({item.fingerprint for item in items if item.severity}),
        "merge_authority": False,
        "self_approval": False,
        "D3_auto": False,
    }


def build_rtc_event(
    event_type: str,
    intent: Intent,
    *,
    sequence: int,
    collision: Collision | None = None,
    causation_id: str | None = None,
    previous_event_hash: str | None = None,
    observed_at: datetime | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if sequence < 1:
        raise ContractError("event_sequence_must_be_positive")
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{2,127}", event_type):
        raise ContractError("invalid_event_type")
    if causation_id is not None:
        causation_id = parse_uuid(causation_id, "causation_id")
    if previous_event_hash is not None:
        previous_event_hash = validate_sha(previous_event_hash, "previous_event_hash", length=64)
    event_id = str(uuid.uuid4())
    timestamp = iso_z(observed_at or utc_now())
    event_payload = dict(payload or {})
    payload_sha = sha256_json(event_payload)
    identity = {
        "schema_version": SCHEMA_VERSION,
        "event_type": event_type,
        "intent_fingerprint": intent.fingerprint,
        "collision_fingerprint": collision.fingerprint if collision else None,
        "sequence": sequence,
        "correlation_id": intent.correlation_id,
        "causation_id": causation_id,
        "payload_sha256": payload_sha,
    }
    idempotency_key = sha256_json(identity)
    event = {
        **identity,
        "event_id": event_id,
        "observed_at": timestamp,
        "repository": intent.repository,
        "target": {"kind": intent.target_kind, "id": intent.target_id},
        "agent": {
            "agent_id": intent.agent_id,
            "instance_id": intent.agent_instance_id,
        },
        "versions": {
            "base_sha": intent.base_sha,
            "head_sha": intent.head_sha,
            "executable_sha256": intent.executable_sha256,
            "config_sha256": intent.config_sha256,
            "policy_sha256": intent.policy_sha256,
        },
        "intent_id": intent.intent_id,
        "idempotency_key": idempotency_key,
        "previous_event_hash": previous_event_hash,
        "visibility": "restricted",
        "payload": event_payload,
    }
    event["event_hash"] = hashlib.sha256(
        ((previous_event_hash or "GENESIS") + "|" + canonical_json(event)).encode("utf-8")
    ).hexdigest()
    return event


@dataclass(frozen=True)
class Lease:
    lease_id: str
    domain_key: str
    owner_agent_id: str
    owner_instance_id: str
    intent_id: str
    fence_token: int
    expected_main_sha: str
    expected_head_sha: str
    acquired_at: datetime
    renewed_at: datetime
    expires_at: datetime
    state: str = "active"


class LeaseBook:
    """Deterministic in-memory lease model used by tests and dry runs.

    Production serialization is provided by a transaction-scoped advisory lock,
    a partial unique index, and a monotonic database sequence.
    """

    def __init__(self) -> None:
        self._leases: dict[str, Lease] = {}
        self._fence = 0

    def acquire(
        self,
        *,
        domain_key: str,
        intent: Intent,
        expected_main_sha: str,
        owner_agent_id: str,
        owner_instance_id: str,
        ttl_seconds: int = 900,
        now: datetime | None = None,
    ) -> Lease:
        if not 60 <= ttl_seconds <= 3600:
            raise ContractError("lease_ttl_out_of_range")
        now = now or utc_now()
        expected_main_sha = validate_sha(expected_main_sha, "expected_main_sha", length=40)
        owner_instance_id = parse_uuid(owner_instance_id, "owner_instance_id")
        existing = self._leases.get(domain_key)
        if existing and existing.state == "active" and existing.expires_at > now:
            raise ContractError("collision_domain_already_leased")
        self._fence += 1
        lease = Lease(
            lease_id=str(uuid.uuid4()),
            domain_key=domain_key,
            owner_agent_id=owner_agent_id,
            owner_instance_id=owner_instance_id,
            intent_id=intent.intent_id,
            fence_token=self._fence,
            expected_main_sha=expected_main_sha,
            expected_head_sha=intent.head_sha,
            acquired_at=now,
            renewed_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self._leases[domain_key] = lease
        return lease

    def renew(self, lease: Lease, *, ttl_seconds: int = 900, now: datetime | None = None) -> Lease:
        now = now or utc_now()
        current = self._leases.get(lease.domain_key)
        if current != lease or lease.state != "active":
            raise ContractError("stale_or_unknown_lease")
        if lease.expires_at <= now:
            self._leases[lease.domain_key] = replace(lease, state="expired")
            raise ContractError("lease_expired")
        renewed = replace(lease, renewed_at=now, expires_at=now + timedelta(seconds=ttl_seconds))
        self._leases[lease.domain_key] = renewed
        return renewed

    def release(self, lease: Lease, *, now: datetime | None = None) -> Lease:
        current = self._leases.get(lease.domain_key)
        if current != lease or lease.state != "active":
            raise ContractError("stale_or_unknown_lease")
        released = replace(lease, state="released", renewed_at=now or utc_now())
        self._leases[lease.domain_key] = released
        return released


TRANSITIONS = {
    RepairState.DETECTED: {RepairState.HELD},
    RepairState.HELD: {RepairState.PLANNED, RepairState.DEAD_LETTER},
    RepairState.PLANNED: {RepairState.LEASED, RepairState.DEAD_LETTER},
    RepairState.LEASED: {RepairState.APPLYING, RepairState.ROLLED_BACK},
    RepairState.APPLYING: {RepairState.VERIFYING, RepairState.ROLLED_BACK},
    RepairState.VERIFYING: {RepairState.REPAIRED, RepairState.ROLLED_BACK},
    RepairState.ROLLED_BACK: {RepairState.PLANNED, RepairState.DEAD_LETTER},
    RepairState.REPAIRED: set(),
    RepairState.DEAD_LETTER: set(),
}


@dataclass(frozen=True)
class RepairPlan:
    plan_id: str
    collision_fingerprint: str
    action_kind: str
    authority_required: str
    reversible: bool
    expected_main_sha: str
    expected_head_sha: str
    idempotency_key: str
    state: RepairState = RepairState.DETECTED
    lease_id: str | None = None
    fence_token: int | None = None
    retry_count: int = 0

    @classmethod
    def compile(
        cls,
        collision: Collision,
        intent: Intent,
        *,
        current_main_sha: str,
        action_kind: str | None = None,
    ) -> "RepairPlan":
        current_main_sha = validate_sha(current_main_sha, "current_main_sha", length=40)
        if action_kind is None:
            action_kind = {
                0: "awareness_receipt",
                1: "awareness_receipt",
                2: "stack_dependency_draft",
                3: "supersession_link_draft",
                4: "review_rebind_required",
                5: "review_rebind_required",
            }[collision.severity]
        if action_kind in PROHIBITED_ACTIONS or action_kind not in SAFE_REPAIR_ACTIONS:
            raise ContractError("repair_action_outside_safe_boundary")
        authority = "D0" if action_kind == "awareness_receipt" else "D1"
        identity = {
            "collision_fingerprint": collision.fingerprint,
            "intent_fingerprint": intent.fingerprint,
            "action_kind": action_kind,
            "expected_main_sha": current_main_sha,
            "expected_head_sha": intent.head_sha,
        }
        return cls(
            plan_id=str(uuid.uuid4()),
            collision_fingerprint=collision.fingerprint,
            action_kind=action_kind,
            authority_required=authority,
            reversible=True,
            expected_main_sha=current_main_sha,
            expected_head_sha=intent.head_sha,
            idempotency_key=sha256_json(identity),
        )

    def transition(
        self,
        next_state: RepairState,
        *,
        current_main_sha: str,
        current_head_sha: str,
        lease: Lease | None = None,
    ) -> "RepairPlan":
        current_main_sha = validate_sha(current_main_sha, "current_main_sha", length=40)
        current_head_sha = validate_sha(current_head_sha, "current_head_sha", length=40)
        if current_main_sha != self.expected_main_sha or current_head_sha != self.expected_head_sha:
            raise ContractError("repair_plan_stale_version_binding")
        if next_state not in TRANSITIONS[self.state]:
            raise ContractError("invalid_repair_state_transition")
        if next_state in {RepairState.LEASED, RepairState.APPLYING, RepairState.VERIFYING}:
            effective = lease
            if effective is None:
                raise ContractError("active_fenced_lease_required")
            if effective.state != "active" or effective.expires_at <= utc_now():
                raise ContractError("active_fenced_lease_required")
            if effective.expected_main_sha != current_main_sha or effective.expected_head_sha != current_head_sha:
                raise ContractError("lease_version_binding_mismatch")
            if self.fence_token is not None and self.fence_token != effective.fence_token:
                raise ContractError("fence_token_mismatch")
            return replace(
                self,
                state=next_state,
                lease_id=effective.lease_id,
                fence_token=effective.fence_token,
            )
        return replace(self, state=next_state)

    def retry_or_dead_letter(self, *, maximum_retries: int = 3) -> "RepairPlan":
        count = self.retry_count + 1
        if count >= maximum_retries:
            return replace(self, retry_count=count, state=RepairState.DEAD_LETTER)
        return replace(self, retry_count=count, state=RepairState.PLANNED)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": self.plan_id,
            "collision_fingerprint": self.collision_fingerprint,
            "action_kind": self.action_kind,
            "authority_required": self.authority_required,
            "reversible": self.reversible,
            "expected_main_sha": self.expected_main_sha,
            "expected_head_sha": self.expected_head_sha,
            "idempotency_key": self.idempotency_key,
            "state": self.state.value,
            "lease_id": self.lease_id,
            "fence_token": self.fence_token,
            "retry_count": self.retry_count,
            "auto_merge_authorized": False,
            "D3_auto": False,
        }


def load_intent(path: str) -> Intent:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, Mapping):
        raise ContractError("intent_root_must_be_object")
    return Intent.from_mapping(raw)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="compare one intent with one or more intents")
    analyze.add_argument("--intent", required=True)
    analyze.add_argument("--against", action="append", default=[])
    analyze.add_argument("--fail-on-severity", type=int, default=2)
    event = subparsers.add_parser("event", help="emit a deterministic RTC envelope")
    event.add_argument("--intent", required=True)
    event.add_argument("--event-type", required=True)
    event.add_argument("--sequence", type=int, required=True)
    event.add_argument("--previous-event-hash")
    args = parser.parse_args(argv)
    try:
        intent = load_intent(args.intent)
        if args.command == "event":
            result = build_rtc_event(
                args.event_type,
                intent,
                sequence=args.sequence,
                previous_event_hash=args.previous_event_hash,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        collisions = [classify_collision(intent, load_intent(path)) for path in args.against]
        result = {
            "schema_version": SCHEMA_VERSION,
            "intent_fingerprint": intent.fingerprint,
            "decision": disposition_for(collisions),
            "collisions": [item.as_dict() for item in collisions],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2 if result["decision"]["max_severity"] >= args.fail_on_severity else 0
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"disposition": Disposition.DENY.value, "reason_code": str(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
