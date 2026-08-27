"""Dependency-free DAIL v2 evidence-spine reference implementation.

The module builds deterministic, append-oriented event envelopes for the
CrownThrive OS.  It does not grant authority, promote lifecycle state, or turn
a hash chain into an independently immutable ledger.  Privileged history
rewrite is detectable only when a trusted external witness head is retained.

Stripe verification here proves that an exact raw byte sequence matched a
configured endpoint secret inside the allowed replay window.  Because Stripe
webhook verification uses a shared secret, it is E4 external symmetric
evidence, not public-key non-repudiation or E5 asymmetric attestation.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from threading import RLock
from typing import Any, Iterable, Mapping, Optional, Sequence
from uuid import UUID, uuid4


EVENT_SCHEMA = "ct.dail.event.v2"
EVENT_SCHEMA_VERSION = "2.0.0"
CANONICAL_CHAIN_ID = "ct.dail.global.v1"
CANONICALIZATION_VERSION = "ct-json-sort-v1"
VERIFICATION_SCHEMA = "ct.dail.external-verification.v2"
VERIFIER_ADMISSION_SCHEMA = "ct.dail.verifier-admission.v1"
FACTORY_CONTINUATION_SCHEMA = "ct.dail.factory-continuation.v2"
UNSEALED_TELEMETRY_SCHEMA = "ct.dail.unsealed-telemetry-queue.v1"
WITNESS_HEAD_SCHEMA = "ct.dail.witness-head.v1"
GENESIS_HASH = "0" * 64
STRIPE_TOLERANCE_SECONDS = 300

EVIDENCE_CLASSES = {
    "E0_INTERNAL_ASSERTION",
    "E1_INTERNAL_HASHED",
    "E2_SEPARATE_WORKLOAD_VERIFIED",
    "E3_EXTERNAL_UNVERIFIED",
    "E4_EXTERNAL_SYMMETRIC_VERIFIED",
    "E5_EXTERNAL_ASYMMETRIC_ATTESTED",
    "E6_INDEPENDENTLY_ANCHORED",
}
VISIBILITIES = {"public", "internal", "restricted", "confidential", "sealed"}
CHAIN_ANCHOR_STATES = {
    "unanchored",
    "queued",
    "anchored_testnet",
    "anchored_production",
    "failed",
    "not_applicable",
}
DECISION_CLASSES = {"D0", "D1", "D2", "D3"}
EVENT_CLASSES = {
    "material_transition",
    "external_evidence",
    "factory_continuation",
    "correction",
    "supersession",
    "low_risk_telemetry",
}
CHANGE_CLASSES = {
    "editorial",
    "factual_correction",
    "source_reconciliation",
    "founder_adjudication",
    "policy_amendment",
    "security_hotfix",
    "schema_migration",
    "economic_amendment",
    "rights_amendment",
    "retraction",
    "supersession",
    "rollback",
    "recovery_patch",
    "runtime_transition",
    "provider_transition",
    "factory_transition",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STRIPE_V1_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class DailError(ValueError):
    """Base exception for a structurally invalid DAIL operation."""


class DailIntegrityError(DailError):
    """Raised when an event, chain, receipt, or witness fails verification."""


class DailConflictError(DailError):
    """Raised when a source identity or idempotency key is reused differently."""


class DailUnavailableError(DailError):
    """Raised when a governed write cannot be sealed and must fail closed."""


@dataclass(frozen=True)
class AppendResult:
    """Result of an in-memory reference-ledger append."""

    event: dict[str, Any]
    idempotent_replay: bool
    replay_basis: Optional[str] = None


def canonical_json(value: Any) -> str:
    """Return the portable JSON representation used by every DAIL v2 digest.

    The cross-runtime dialect intentionally permits only string object keys and
    integer JSON numbers. Python float rendering and PostgreSQL JSONB numeric
    rendering are not byte-equivalent for every finite value.
    """

    def validate_portable(item: Any, path: str) -> None:
        if isinstance(item, float):
            raise DailError(f"{path} uses a non-portable floating-point number")
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise DailError(f"{path} contains a non-string object key")
                validate_portable(child, f"{path}.{key}")
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                validate_portable(child, f"{path}[{index}]")

    validate_portable(value, "$")

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise DailError(f"value is not canonical JSON: {exc}") from exc


def sha256_bytes(value: bytes) -> str:
    if not isinstance(value, bytes):
        raise DailError("sha256_bytes requires exact bytes")
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def _utc_iso(value: Optional[datetime | str] = None) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DailError("timestamp must be RFC3339") from exc
    else:
        raise DailError("timestamp must be a datetime, RFC3339 string, or null")
    if parsed.tzinfo is None:
        raise DailError("timestamp must include a timezone")
    return (
        parsed.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DailError(f"{field} must be a non-empty string")
    return value


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise DailError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_uuid(value: Any, field: str) -> str:
    text = _require_string(value, field)
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError) as exc:
        raise DailError(f"{field} must be a UUID") from exc
    canonical = str(parsed)
    if text != canonical:
        raise DailError(f"{field} must use canonical lowercase UUID form")
    return canonical


def _require_secret_ref(value: Any, field: str) -> str:
    reference = _require_string(value, field)
    if len(reference) > 200 or "whsec_" in reference.casefold():
        raise DailError(f"{field} must be a bounded reference, never secret material")
    return reference


def _copy_json(value: Any) -> Any:
    return json.loads(canonical_json(value))


def _validate_ref_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise DailError(f"{field} must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise DailError(f"{field} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise DailError(f"{field} must not contain duplicates")
    return value


def classify_event(event_class: str) -> dict[str, Any]:
    """Return the non-overridable write policy for an event class."""

    if event_class not in EVENT_CLASSES:
        raise DailError(f"unsupported event_class: {event_class}")
    low_risk = event_class == "low_risk_telemetry"
    consequential = event_class in {
        "material_transition",
        "correction",
        "supersession",
    }
    return {
        "event_class": event_class,
        "material": not low_risk,
        "consequential": consequential,
        "dail_seal_required": not low_risk,
        "unsealed_queue_allowed": low_risk,
    }


def _validate_authority_basis(value: Any, *, consequential: bool) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DailError("authority_basis must be an object")
    authority = _copy_json(value)
    required = {"authority_ref", "actor_ref", "decision_class", "approval_ref", "human_authority"}
    missing = required - set(authority)
    if missing:
        raise DailError(f"authority_basis missing fields: {sorted(missing)}")
    _require_string(authority["authority_ref"], "authority_basis.authority_ref")
    _require_string(authority["actor_ref"], "authority_basis.actor_ref")
    if authority["decision_class"] not in DECISION_CLASSES:
        raise DailError("authority_basis.decision_class must be D0-D3")
    if authority["approval_ref"] is not None:
        _require_string(authority["approval_ref"], "authority_basis.approval_ref")
    if not isinstance(authority["human_authority"], bool):
        raise DailError("authority_basis.human_authority must be boolean")
    if consequential and authority["approval_ref"] is None:
        raise DailError("consequential events require an approval_ref")
    if authority["decision_class"] == "D3" and (
        not authority["human_authority"] or authority["approval_ref"] is None
    ):
        raise DailError("D3 remains human-reserved and requires explicit approval evidence")
    return authority


def _validate_transition(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DailError("material_transition events require a transition object")
    transition = _copy_json(value)
    required = {
        "subject_type",
        "subject_id",
        "previous_state",
        "new_state",
        "change_class",
        "risk_class",
        "reason",
        "affected_record_ids",
        "rollback_ref",
    }
    missing = required - set(transition)
    if missing:
        raise DailError(f"transition missing fields: {sorted(missing)}")
    for field in ("subject_type", "subject_id", "previous_state", "new_state", "reason", "rollback_ref"):
        _require_string(transition[field], f"transition.{field}")
    if transition["previous_state"] == transition["new_state"]:
        raise DailError("transition must change state")
    if transition["change_class"] not in CHANGE_CLASSES:
        raise DailError("transition.change_class is not governed")
    if transition["risk_class"] not in DECISION_CLASSES:
        raise DailError("transition.risk_class must be D0-D3")
    affected = _validate_ref_list(transition["affected_record_ids"], "transition.affected_record_ids")
    if not affected:
        raise DailError("transition.affected_record_ids must not be empty")
    return transition


def _validate_receipt_digest(receipt: Mapping[str, Any], *, digest_field: str = "receipt_sha256") -> None:
    body = _copy_json(receipt)
    supplied = body.pop(digest_field, None)
    _require_sha256(supplied, digest_field)
    if supplied != sha256_json(body):
        raise DailIntegrityError(f"{digest_field} mismatch")


def _verification_refs(
    receipts: Iterable[Mapping[str, Any]],
    verifier_admission_keys: Optional[Mapping[str, bytes | str]],
) -> list[dict[str, str]]:
    receipt_list = list(receipts)
    if receipt_list and not verifier_admission_keys:
        raise DailError("verified evidence requires authenticated verifier admission keys")
    refs: list[dict[str, str]] = []
    for receipt in receipt_list:
        if not isinstance(receipt, Mapping):
            raise DailError("verification receipts must be objects")
        _validate_receipt_digest(receipt)
        if receipt.get("schema") != VERIFICATION_SCHEMA:
            raise DailError("unsupported verification receipt schema")
        if (
            receipt.get("outcome") != "verified"
            or receipt.get("evidence_class") != "E4_EXTERNAL_SYMMETRIC_VERIFIED"
        ):
            raise DailError("external evidence requires a verified E4 receipt")
        independence = receipt.get("independence") or {}
        if independence.get("trust_domain_labels_distinct") is not True:
            raise DailError("verification receipt lacks distinct producer/verifier domains")
        admission = receipt.get("admission")
        if not isinstance(admission, Mapping):
            raise DailError("verification receipt lacks authenticated admission evidence")
        if admission.get("schema") != VERIFIER_ADMISSION_SCHEMA:
            raise DailError("unsupported verifier admission schema")
        version_ref = _require_secret_ref(
            admission.get("key_version_ref"), "admission.key_version_ref"
        )
        content_sha256 = _require_sha256(
            admission.get("content_sha256"), "admission.content_sha256"
        )
        admission_mac = _require_sha256(admission.get("mac_sha256"), "admission.mac_sha256")
        content = _copy_json(receipt)
        content.pop("receipt_sha256", None)
        content.pop("admission", None)
        if sha256_json(content) != content_sha256:
            raise DailIntegrityError("verifier admission content digest mismatch")
        configured_key = verifier_admission_keys.get(version_ref) if verifier_admission_keys else None
        if isinstance(configured_key, str):
            configured_key = configured_key.encode("utf-8")
        if not isinstance(configured_key, bytes) or not configured_key:
            raise DailError("verifier admission key version is not configured")
        expected_mac = hmac.new(
            configured_key,
            f"dail-verifier-admission-v1|{content_sha256}".encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_mac, admission_mac):
            raise DailIntegrityError("verifier admission MAC mismatch")
        refs.append(
            {
                "receipt_id": _require_string(receipt.get("receipt_id"), "receipt_id"),
                "receipt_sha256": _require_sha256(receipt.get("receipt_sha256"), "receipt_sha256"),
            }
        )
    if len({ref["receipt_id"] for ref in refs}) != len(refs):
        raise DailError("verification receipt IDs must be unique")
    return refs


def dail_event_v2_preimage(event: Mapping[str, Any]) -> dict[str, Any]:
    """Project a row into the exact SQL ``dail_event_v2_preimage`` object."""

    return {
        "preimage_format": "dail.event.v2.canonical-jsonb",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "chain_id": event.get("chain_id"),
        "sequence_id": event.get("sequence_id"),
        "previous_event_hash": event.get("previous_event_hash"),
        "event_id": event.get("event_id"),
        "schema_version": event.get("schema_version"),
        "event_type": event.get("event_type"),
        "actor_ref": event.get("actor_ref"),
        "actor_did": event.get("actor_did"),
        "agent_id": event.get("agent_id"),
        "source_system": event.get("source_system"),
        "source_event_id": event.get("source_event_id"),
        "trust_domain": event.get("trust_domain"),
        "evidence_class": event.get("evidence_class"),
        "idempotency_key": event.get("idempotency_key"),
        "verification_receipt_id": event.get("verification_receipt_id"),
        "entity_type": event.get("entity_type"),
        "entity_id": event.get("entity_id"),
        "entity_version": event.get("entity_version"),
        "correlation_id": event.get("correlation_id"),
        "causation_id": event.get("causation_id"),
        "authority_basis": event.get("authority_basis"),
        "approval_id": event.get("approval_id"),
        "visibility_class": event.get("visibility_class"),
        "payload_sha256": event.get("payload_sha256"),
        "payload_ref": event.get("payload_ref"),
        "correction_of_event_id": event.get("correction_of_event_id"),
        "supersedes_event_id": event.get("supersedes_event_id"),
        "chain_anchor_state": event.get("chain_anchor_state"),
        "signature_ref": event.get("signature_ref"),
        "created_at": event.get("created_at"),
    }


def _contract_payload(
    *,
    event_class: str,
    classification: Mapping[str, Any],
    transition: Optional[Mapping[str, Any]],
    verification_receipt_sha256: Optional[str],
    content: Any,
    referenced_content_sha256: Optional[str],
) -> dict[str, Any]:
    """Put adapter-only controls inside the SQL-hashed payload projection."""

    return {
        "_dail_contract": {
            "event_class": event_class,
            "classification": _copy_json(classification),
            "transition": _copy_json(transition) if transition is not None else None,
            "verification_receipt_sha256": verification_receipt_sha256,
        },
        "content": _copy_json(content) if content is not None else None,
        "referenced_content_sha256": referenced_content_sha256,
    }


def build_event(
    *,
    chain_id: str,
    sequence_id: int,
    event_type: str,
    event_class: str,
    source_system: str,
    source_event_id: str,
    trust_domain: str,
    evidence_class: str,
    idempotency_key: str,
    correlation_id: str,
    causation_id: Optional[str],
    authority_basis: Mapping[str, Any],
    visibility_class: str,
    payload_ref: str,
    previous_event_hash: Optional[str],
    payload: Any = None,
    payload_sha256: Optional[str] = None,
    verification_receipts: Sequence[Mapping[str, Any]] = (),
    verifier_admission_keys: Optional[Mapping[str, bytes | str]] = None,
    correction_of_event_id: Optional[str] = None,
    supersedes_event_id: Optional[str] = None,
    transition: Optional[Mapping[str, Any]] = None,
    actor_ref: Optional[str] = None,
    actor_did: Optional[str] = None,
    agent_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    entity_version: Optional[str] = None,
    approval_id: Optional[str] = None,
    chain_anchor_state: str = "unanchored",
    signature_ref: Optional[str] = None,
    event_id: Optional[str] = None,
    created_at: Optional[datetime | str] = None,
) -> dict[str, Any]:
    """Build one row whose event hash is byte-equivalent to the SQL contract."""

    classification = classify_event(event_class)
    if chain_id != CANONICAL_CHAIN_ID:
        raise DailError(f"chain_id must be {CANONICAL_CHAIN_ID}")
    if not isinstance(sequence_id, int) or isinstance(sequence_id, bool) or sequence_id < 1:
        raise DailError("sequence_id must be a positive integer")
    if sequence_id == 1:
        if previous_event_hash is not None:
            raise DailError("true genesis must use a null previous_event_hash")
    else:
        _require_sha256(previous_event_hash, "previous_event_hash")
    if evidence_class not in EVIDENCE_CLASSES:
        raise DailError("unsupported evidence_class")
    if visibility_class not in VISIBILITIES:
        raise DailError("unsupported visibility_class")
    if chain_anchor_state not in CHAIN_ANCHOR_STATES:
        raise DailError("unsupported chain_anchor_state")
    if chain_anchor_state != "unanchored":
        raise DailError(
            "generic event admission cannot assert an anchor state; "
            "independent write and readback evidence are required"
        )
    if evidence_class in {
        "E2_SEPARATE_WORKLOAD_VERIFIED",
        "E5_EXTERNAL_ASYMMETRIC_ATTESTED",
        "E6_INDEPENDENTLY_ANCHORED",
    }:
        raise DailError(
            f"{evidence_class} requires a dedicated authenticated admission path"
        )
    for field, value in (
        ("event_type", event_type),
        ("source_system", source_system),
        ("source_event_id", source_event_id),
        ("trust_domain", trust_domain),
        ("idempotency_key", idempotency_key),
        ("correlation_id", correlation_id),
        ("payload_ref", payload_ref),
    ):
        _require_string(value, field)
    if "whsec_" in payload_ref.casefold():
        raise DailError("payload_ref must never contain secret material")
    if causation_id is not None:
        _require_string(causation_id, "causation_id")
    if signature_ref is not None:
        _require_secret_ref(signature_ref, "signature_ref")

    authority = _validate_authority_basis(
        authority_basis, consequential=classification["consequential"]
    )
    normalized_transition = None
    if event_class == "material_transition":
        normalized_transition = _validate_transition(transition)
        if normalized_transition["risk_class"] != authority["decision_class"]:
            raise DailError("transition risk_class must match authority decision_class")
    elif transition is not None:
        raise DailError("transition is allowed only for material_transition events")

    normalized_actor_ref = actor_ref or authority["actor_ref"]
    if normalized_actor_ref != authority["actor_ref"]:
        raise DailError("actor_ref must match authority_basis.actor_ref")
    _require_string(normalized_actor_ref, "actor_ref")
    for field, value in (("actor_did", actor_did), ("agent_id", agent_id)):
        if value is not None:
            _require_string(value, field)
    normalized_approval_id = approval_id if approval_id is not None else authority["approval_ref"]
    if normalized_approval_id != authority["approval_ref"]:
        raise DailError("approval_id must match authority_basis.approval_ref")

    if normalized_transition is not None:
        normalized_entity_type = entity_type or normalized_transition["subject_type"]
        normalized_entity_id = entity_id or normalized_transition["subject_id"]
        if normalized_entity_type != normalized_transition["subject_type"]:
            raise DailError("entity_type must match transition.subject_type")
        if normalized_entity_id != normalized_transition["subject_id"]:
            raise DailError("entity_id must match transition.subject_id")
    else:
        normalized_entity_type, normalized_entity_id = entity_type, entity_id
    _require_string(normalized_entity_type, "entity_type")
    _require_string(normalized_entity_id, "entity_id")
    if entity_version is not None:
        _require_string(entity_version, "entity_version")
    if correction_of_event_id is not None:
        correction_of_event_id = _require_uuid(
            correction_of_event_id, "correction_of_event_id"
        )
    if supersedes_event_id is not None:
        supersedes_event_id = _require_uuid(supersedes_event_id, "supersedes_event_id")
    if event_class == "correction" and correction_of_event_id is None:
        raise DailError("correction events require correction_of_event_id")
    if event_class == "supersession" and supersedes_event_id is None:
        raise DailError("supersession events require supersedes_event_id")

    verification_refs = _verification_refs(verification_receipts, verifier_admission_keys)
    if len(verification_refs) > 1:
        raise DailError("DAIL v2 supports one verification receipt per event")
    if event_class == "external_evidence" and not verification_refs:
        raise DailError("external_evidence events require an independent verification receipt")
    if event_class == "external_evidence" and evidence_class != "E4_EXTERNAL_SYMMETRIC_VERIFIED":
        raise DailError("the implemented external admission path supports only verified E4 evidence")
    if verification_refs and evidence_class != "E4_EXTERNAL_SYMMETRIC_VERIFIED":
        raise DailError("an E4 verification receipt cannot promote another evidence class")
    if evidence_class == "E4_EXTERNAL_SYMMETRIC_VERIFIED":
        if event_class != "external_evidence" or not verification_refs:
            raise DailError("E4 admission requires the verified external-evidence path")
        receipt = verification_receipts[0]
        if (
            receipt.get("provider") != source_system
            or receipt.get("source_event_id") != source_event_id
            or receipt.get("producer_trust_domain") != trust_domain
        ):
            raise DailIntegrityError(
                "verification receipt provenance differs from the admitted source event"
            )

    if payload is None:
        referenced_content_sha256 = _require_sha256(payload_sha256, "payload_sha256")
    else:
        referenced_content_sha256 = sha256_json(_copy_json(payload))
        if payload_sha256 is not None and payload_sha256 != referenced_content_sha256:
            raise DailIntegrityError("supplied payload_sha256 does not match the payload")
    verification_sha = verification_refs[0]["receipt_sha256"] if verification_refs else None
    normalized_payload = _contract_payload(
        event_class=event_class,
        classification=classification,
        transition=normalized_transition,
        verification_receipt_sha256=verification_sha,
        content=payload,
        referenced_content_sha256=referenced_content_sha256,
    )
    body: dict[str, Any] = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "chain_id": chain_id,
        "sequence_id": sequence_id,
        "previous_event_hash": previous_event_hash,
        "event_id": _require_uuid(event_id or str(uuid4()), "event_id"),
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_type": event_type,
        "actor_ref": normalized_actor_ref,
        "actor_did": actor_did,
        "agent_id": agent_id,
        "source_system": source_system,
        "source_event_id": source_event_id,
        "trust_domain": trust_domain,
        "evidence_class": evidence_class,
        "idempotency_key": idempotency_key,
        "verification_receipt_id": (
            _require_uuid(verification_refs[0]["receipt_id"], "verification_receipt_id")
            if verification_refs
            else None
        ),
        "entity_type": normalized_entity_type,
        "entity_id": normalized_entity_id,
        "entity_version": entity_version,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "authority_basis": canonical_json(authority),
        "approval_id": normalized_approval_id,
        "visibility_class": visibility_class,
        "payload": normalized_payload,
        "payload_sha256": sha256_json(normalized_payload),
        "payload_ref": payload_ref,
        "correction_of_event_id": correction_of_event_id,
        "supersedes_event_id": supersedes_event_id,
        "chain_anchor_state": chain_anchor_state,
        "signature_ref": signature_ref,
        "created_at": _utc_iso(created_at),
    }
    body["event_hash"] = sha256_json(dail_event_v2_preimage(body))
    validate_event(body)
    return body


def validate_event(event: Mapping[str, Any]) -> None:
    """Validate the row and recompute the exact SQL-equivalent preimage hash."""

    if not isinstance(event, Mapping):
        raise DailError("event must be an object")
    body = _copy_json(event)
    supplied_hash = body.pop("event_hash", None)
    _require_sha256(supplied_hash, "event_hash")
    required = {
        "canonicalization_version", "chain_id", "sequence_id", "previous_event_hash",
        "event_id", "schema_version", "event_type", "actor_ref", "actor_did", "agent_id",
        "source_system", "source_event_id", "trust_domain", "evidence_class", "idempotency_key",
        "verification_receipt_id", "entity_type", "entity_id", "entity_version",
        "correlation_id", "causation_id", "authority_basis", "approval_id", "visibility_class",
        "payload", "payload_sha256", "payload_ref", "correction_of_event_id",
        "supersedes_event_id", "chain_anchor_state", "signature_ref", "created_at",
    }
    if set(body) != required:
        missing = sorted(required - set(body))
        extra = sorted(set(body) - required)
        raise DailError(f"event fields do not match v2 row contract; missing={missing}, extra={extra}")
    if body["canonicalization_version"] != CANONICALIZATION_VERSION:
        raise DailError("unsupported DAIL canonicalization version")
    if body["schema_version"] != EVENT_SCHEMA_VERSION or body["chain_id"] != CANONICAL_CHAIN_ID:
        raise DailError("unsupported DAIL v2 chain or schema")
    if not isinstance(body["sequence_id"], int) or isinstance(body["sequence_id"], bool) or body["sequence_id"] < 1:
        raise DailError("sequence_id must be a positive integer")
    if body["sequence_id"] == 1:
        if body["previous_event_hash"] is not None:
            raise DailIntegrityError("true genesis previous_event_hash must be null")
    else:
        _require_sha256(body["previous_event_hash"], "previous_event_hash")
    _require_uuid(body["event_id"], "event_id")
    for field in (
        "event_type", "actor_ref", "source_system", "source_event_id",
        "trust_domain", "idempotency_key", "entity_type", "entity_id", "correlation_id",
        "authority_basis", "payload_ref",
    ):
        _require_string(body[field], field)
    for field in (
        "actor_did", "agent_id", "entity_version", "causation_id", "approval_id", "signature_ref",
    ):
        if body[field] is not None:
            _require_string(body[field], field)
    for field in (
        "verification_receipt_id", "correction_of_event_id", "supersedes_event_id",
    ):
        if body[field] is not None:
            _require_uuid(body[field], field)
    if body["evidence_class"] not in EVIDENCE_CLASSES:
        raise DailError("unsupported evidence_class")
    if body["visibility_class"] not in VISIBILITIES:
        raise DailError("unsupported visibility_class")
    if body["chain_anchor_state"] not in CHAIN_ANCHOR_STATES:
        raise DailError("unsupported chain_anchor_state")
    if _utc_iso(body["created_at"]) != body["created_at"]:
        raise DailError("created_at must use the canonical six-microsecond UTC form")
    _require_sha256(body["payload_sha256"], "payload_sha256")
    if sha256_json(body["payload"]) != body["payload_sha256"]:
        raise DailIntegrityError("payload_sha256 mismatch")

    contract = body["payload"].get("_dail_contract") if isinstance(body["payload"], dict) else None
    if not isinstance(contract, dict):
        raise DailError("payload must contain the governed _dail_contract projection")
    classification = classify_event(contract.get("event_class"))
    if contract.get("classification") != classification:
        raise DailIntegrityError("event classification does not match its governed class")
    try:
        authority_raw = json.loads(body["authority_basis"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise DailError("authority_basis must be canonical JSON text") from exc
    authority = _validate_authority_basis(
        authority_raw, consequential=classification["consequential"]
    )
    if canonical_json(authority) != body["authority_basis"]:
        raise DailError("authority_basis text is not canonical")
    if body["actor_ref"] != authority["actor_ref"] or body["approval_id"] != authority["approval_ref"]:
        raise DailIntegrityError("authority projection differs from actor or approval fields")
    transition = contract.get("transition")
    if contract["event_class"] == "material_transition":
        normalized_transition = _validate_transition(transition)
        if normalized_transition["risk_class"] != authority["decision_class"]:
            raise DailIntegrityError("transition and authority risk classes differ")
        if normalized_transition["subject_type"] != body["entity_type"] or normalized_transition["subject_id"] != body["entity_id"]:
            raise DailIntegrityError("transition and entity identity differ")
    elif transition is not None:
        raise DailError("non-transition event contains transition state")
    if contract["event_class"] == "correction" and not body["correction_of_event_id"]:
        raise DailError("correction event is missing its predecessor")
    if contract["event_class"] == "supersession" and not body["supersedes_event_id"]:
        raise DailError("supersession event is missing its predecessor")
    verification_sha = contract.get("verification_receipt_sha256")
    if body["verification_receipt_id"] is None:
        if verification_sha is not None:
            raise DailError("verification digest requires its receipt ID")
    else:
        _require_sha256(verification_sha, "verification_receipt_sha256")
    if contract["event_class"] == "external_evidence" and body["verification_receipt_id"] is None:
        raise DailError("external evidence is missing verification")
    if supplied_hash != sha256_json(dail_event_v2_preimage(body)):
        raise DailIntegrityError("event_hash mismatch")


def build_witness_head(
    events: Sequence[Mapping[str, Any]],
    *,
    witness_id: str,
    witness_trust_domain: str,
    expected_predecessor: Optional[Mapping[str, Any]] = None,
    observed_at: Optional[datetime | str] = None,
) -> dict[str, Any]:
    """Create a portable head checkpoint; external persistence gives it weight."""

    verification = verify_chain(events, expected_predecessor=expected_predecessor)
    body = {
        "schema": WITNESS_HEAD_SCHEMA,
        "witness_id": _require_string(witness_id, "witness_id"),
        "witness_trust_domain": _require_string(witness_trust_domain, "witness_trust_domain"),
        "chain_id": verification["chain_id"],
        "sequence_id": verification["head_sequence_id"],
        "event_hash": verification["head_hash"],
        "observed_at": _utc_iso(observed_at),
    }
    body["witness_sha256"] = sha256_json(body)
    return body


def _validate_witness_head(witness: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(witness, Mapping):
        raise DailError("witness_head must be an object")
    body = _copy_json(witness)
    supplied = body.pop("witness_sha256", None)
    _require_sha256(supplied, "witness_sha256")
    if supplied != sha256_json(body):
        raise DailIntegrityError("witness digest mismatch")
    if body.get("schema") != WITNESS_HEAD_SCHEMA:
        raise DailError("unsupported witness schema")
    for field in ("witness_id", "witness_trust_domain", "chain_id"):
        _require_string(body.get(field), field)
    if not isinstance(body.get("sequence_id"), int) or body["sequence_id"] < 1:
        raise DailError("witness sequence_id must be positive")
    _require_sha256(body.get("event_hash"), "witness event_hash")
    _utc_iso(body.get("observed_at"))
    return body


def verify_chain(
    events: Sequence[Mapping[str, Any]],
    *,
    expected_predecessor: Optional[Mapping[str, Any]] = None,
    witness_head: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Verify a linked v2 segment and an optional independently held head.

    Sequence IDs must increase, but need not be gap-free because PostgreSQL
    identity values can be consumed by rolled-back transactions.
    """

    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)) or not events:
        raise DailIntegrityError("a DAIL chain must contain at least one event")
    if expected_predecessor is None:
        predecessor_sequence = 0
        expected_previous: Optional[str] = None
        predecessor_chain_id = CANONICAL_CHAIN_ID
    else:
        if not isinstance(expected_predecessor, Mapping):
            raise DailError("expected_predecessor must be an object")
        predecessor_sequence = expected_predecessor.get("sequence_id")
        if not isinstance(predecessor_sequence, int) or predecessor_sequence < 1:
            raise DailError("expected_predecessor.sequence_id must be positive")
        expected_previous = _require_sha256(
            expected_predecessor.get("event_hash"), "expected_predecessor.event_hash"
        )
        predecessor_chain_id = _require_string(
            expected_predecessor.get("chain_id"), "expected_predecessor.chain_id"
        )
        if predecessor_chain_id != CANONICAL_CHAIN_ID:
            raise DailError("expected predecessor uses the wrong DAIL chain")
    chain_id: Optional[str] = None
    indexed: dict[int, str] = {}
    previous_sequence = predecessor_sequence
    for event in events:
        validate_event(event)
        if event["sequence_id"] <= previous_sequence:
            raise DailIntegrityError("event sequence is duplicated or reordered")
        if event["previous_event_hash"] != expected_previous:
            raise DailIntegrityError("event previous hash does not match its predecessor")
        if chain_id is None:
            chain_id = event["chain_id"]
        elif event["chain_id"] != chain_id:
            raise DailIntegrityError("event chain_id changed inside the chain")
        expected_previous = event["event_hash"]
        previous_sequence = event["sequence_id"]
        indexed[previous_sequence] = expected_previous

    if chain_id != predecessor_chain_id:
        raise DailIntegrityError("segment chain_id differs from its expected predecessor")

    witness_state = "not_supplied"
    if witness_head is not None:
        witness = _validate_witness_head(witness_head)
        if witness["chain_id"] != chain_id:
            raise DailIntegrityError("witness chain_id does not match")
        witnessed_hash = indexed.get(witness["sequence_id"])
        if witnessed_hash is None:
            raise DailIntegrityError("local chain is truncated before the witnessed head")
        if witnessed_hash != witness["event_hash"]:
            raise DailIntegrityError("local chain conflicts with the witnessed head")
        witness_state = "matched"
    return {
        "ok": True,
        "chain_id": chain_id,
        "checked_events": len(events),
        "head_sequence_id": previous_sequence,
        "head_hash": expected_previous,
        "witness_state": witness_state,
    }


class DailLedger:
    """Thread-safe in-memory adapter used to exercise the DAIL append contract.

    Durable implementations must enforce the same uniqueness and locking rules
    transactionally in their database.  This class deliberately has no update,
    delete, or truncate API.
    """

    def __init__(
        self,
        chain_id: str,
        *,
        head_sequence_id: int = 0,
        head_hash: Optional[str] = None,
    ):
        self.chain_id = _require_string(chain_id, "chain_id")
        if self.chain_id != CANONICAL_CHAIN_ID:
            raise DailError(f"chain_id must be {CANONICAL_CHAIN_ID}")
        if not isinstance(head_sequence_id, int) or isinstance(head_sequence_id, bool) or head_sequence_id < 0:
            raise DailError("head_sequence_id must be a non-negative integer")
        if head_sequence_id == 0:
            if head_hash is not None:
                raise DailError("a genesis ledger cannot have a predecessor hash")
        else:
            _require_sha256(head_hash, "head_hash")
        self._base_head_sequence_id = head_sequence_id
        self._base_head_hash = head_hash
        self._events: list[dict[str, Any]] = []
        self._idempotency: dict[str, tuple[str, dict[str, Any]]] = {}
        self._source_events: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    @property
    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._events)

    def append(self, *, idempotency_key: str, **event_request: Any) -> AppendResult:
        _require_string(idempotency_key, "idempotency_key")
        source_system = _require_string(event_request.get("source_system"), "source_system")
        source_event_id = _require_string(event_request.get("source_event_id"), "source_event_id")
        logical = _copy_json({**event_request, "idempotency_key": idempotency_key})
        full_fingerprint = sha256_json(logical)
        idempotency_scope = f"{source_system}\x1f{idempotency_key}"
        source_scope = f"{source_system}\x1f{source_event_id}"

        with self._lock:
            existing = self._idempotency.get(idempotency_scope)
            if existing is not None:
                if existing[0] != full_fingerprint:
                    raise DailConflictError("idempotency key was reused for a different event")
                return AppendResult(deepcopy(existing[1]), True, "idempotency_key")
            source_existing = self._source_events.get(source_scope)
            if source_existing is not None:
                raise DailConflictError(
                    "source event identity was reused without its original idempotency key"
                )

            sequence_id = (
                self._events[-1]["sequence_id"] + 1
                if self._events
                else self._base_head_sequence_id + 1
            )
            previous = self._events[-1]["event_hash"] if self._events else self._base_head_hash
            event = build_event(
                chain_id=self.chain_id,
                sequence_id=sequence_id,
                previous_event_hash=previous,
                idempotency_key=idempotency_key,
                **event_request,
            )
            self._events.append(event)
            self._idempotency[idempotency_scope] = (full_fingerprint, event)
            self._source_events[source_scope] = event
            return AppendResult(deepcopy(event), False)

    def verify(self, *, witness_head: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        with self._lock:
            predecessor = None
            if self._base_head_sequence_id:
                predecessor = {
                    "chain_id": self.chain_id,
                    "sequence_id": self._base_head_sequence_id,
                    "event_hash": self._base_head_hash,
                }
            return verify_chain(
                deepcopy(self._events),
                expected_predecessor=predecessor,
                witness_head=witness_head,
            )


def _parse_stripe_header(header: str) -> tuple[Optional[int], list[str], Optional[str]]:
    if not isinstance(header, str) or not header.strip():
        return None, [], "missing_signature_header"
    timestamps: list[str] = []
    signatures: list[str] = []
    for part in header.split(","):
        key, separator, value = part.strip().partition("=")
        if not separator:
            continue
        if key == "t":
            timestamps.append(value)
        elif key == "v1" and _STRIPE_V1_RE.fullmatch(value):
            signatures.append(value.lower())
    if len(timestamps) != 1:
        return None, signatures, "invalid_timestamp_count"
    try:
        timestamp = int(timestamps[0])
    except ValueError:
        return None, signatures, "invalid_timestamp"
    if timestamp < 0:
        return None, signatures, "invalid_timestamp"
    if not signatures:
        return timestamp, [], "missing_v1_signature"
    return timestamp, signatures, None


def verify_stripe_signature(
    raw_body: bytes,
    signature_header: str,
    secret_versions: Mapping[str, bytes | str],
    *,
    now: Optional[datetime | int] = None,
    tolerance_seconds: int = STRIPE_TOLERANCE_SECONDS,
) -> dict[str, Any]:
    """Verify Stripe's ``t.raw_body`` HMAC without parsing or re-encoding body."""

    if not isinstance(raw_body, bytes):
        raise DailError("Stripe verification requires the exact raw request bytes")
    if not isinstance(secret_versions, Mapping) or not secret_versions:
        raise DailError("at least one versioned Stripe endpoint secret is required")
    if not isinstance(tolerance_seconds, int) or isinstance(tolerance_seconds, bool):
        raise DailError("tolerance_seconds must be an integer")
    if tolerance_seconds != STRIPE_TOLERANCE_SECONDS:
        raise DailError("Stripe replay tolerance must be exactly 300 seconds")

    normalized_secrets: list[tuple[str, bytes]] = []
    for version_ref, secret in secret_versions.items():
        _require_secret_ref(version_ref, "secret version reference")
        if isinstance(secret, str):
            secret_bytes = secret.encode("utf-8")
        elif isinstance(secret, bytes):
            secret_bytes = secret
        else:
            raise DailError("Stripe endpoint secrets must be bytes or strings")
        if not secret_bytes:
            raise DailError("Stripe endpoint secrets must not be empty")
        normalized_secrets.append((version_ref, secret_bytes))

    timestamp, signatures, parse_error = _parse_stripe_header(signature_header)
    if isinstance(now, datetime):
        if now.tzinfo is None:
            raise DailError("now must include a timezone")
        now_seconds = int(now.timestamp())
    elif isinstance(now, int) and not isinstance(now, bool):
        now_seconds = now
    elif now is None:
        now_seconds = int(datetime.now(timezone.utc).timestamp())
    else:
        raise DailError("now must be a timezone-aware datetime, integer epoch, or null")

    matched_versions: list[str] = []
    age_seconds: Optional[int] = None
    if timestamp is not None:
        age_seconds = now_seconds - timestamp
        signed_payload = str(timestamp).encode("ascii") + b"." + raw_body
        for version_ref, secret in normalized_secrets:
            expected = hmac.new(secret, signed_payload, hashlib.sha256).hexdigest()
            matched = False
            for candidate in signatures:
                matched = hmac.compare_digest(expected, candidate) or matched
            if matched:
                matched_versions.append(version_ref)

    within_tolerance = age_seconds is not None and abs(age_seconds) <= tolerance_seconds
    verified = parse_error is None and bool(matched_versions) and within_tolerance
    if parse_error is not None:
        outcome = "malformed"
        reason = parse_error
    elif not within_tolerance:
        outcome = "rejected"
        reason = "timestamp_outside_tolerance"
    elif not matched_versions:
        outcome = "rejected"
        reason = "signature_mismatch"
    else:
        outcome = "verified"
        reason = None

    body: dict[str, Any] = {
        "provider": "stripe",
        "algorithm": "hmac-sha256",
        "verified": verified,
        "outcome": outcome,
        "reason": reason,
        "signature_timestamp": timestamp,
        "age_seconds": age_seconds,
        "tolerance_seconds": tolerance_seconds,
        "matched_secret_version_refs": sorted(matched_versions),
        "candidate_signature_count": len(signatures),
        "configured_secret_version_count": len(normalized_secrets),
        "raw_body_sha256": sha256_bytes(raw_body),
        "signature_header_sha256": sha256_bytes(signature_header.encode("utf-8")),
    }
    body["verification_sha256"] = sha256_json(body)
    return body


def build_external_verification_receipt(
    verification: Mapping[str, Any],
    *,
    source_event_id: str,
    producer_trust_domain: str,
    verifier_id: str,
    verifier_trust_domain: str,
    admission_key_version_ref: str,
    admission_key: bytes | str,
    receipt_id: Optional[str] = None,
    verified_at: Optional[datetime | str] = None,
) -> dict[str, Any]:
    """Bind a Stripe decision to separately labelled producer/verifier domains.

    Workload authentication is an ingress deployment control; this pure builder
    does not turn caller-supplied identity labels into independent attestation.
    """

    if not isinstance(verification, Mapping):
        raise DailError("verification must be an object")
    verification_body = _copy_json(verification)
    supplied = verification_body.pop("verification_sha256", None)
    _require_sha256(supplied, "verification_sha256")
    if supplied != sha256_json(verification_body):
        raise DailIntegrityError("verification result digest mismatch")
    if verification_body.get("provider") != "stripe":
        raise DailError("unsupported external verification provider")
    producer_domain = _require_string(producer_trust_domain, "producer_trust_domain")
    verifier_domain = _require_string(verifier_trust_domain, "verifier_trust_domain")
    if producer_domain == verifier_domain:
        raise DailError("producer and verifier trust domains must be distinct")

    key_version_ref = _require_secret_ref(
        admission_key_version_ref, "admission_key_version_ref"
    )
    if isinstance(admission_key, str):
        admission_key_bytes = admission_key.encode("utf-8")
    elif isinstance(admission_key, bytes):
        admission_key_bytes = admission_key
    else:
        raise DailError("admission_key must be bytes or a string")
    if not admission_key_bytes:
        raise DailError("admission_key must not be empty")

    body: dict[str, Any] = {
        "schema": VERIFICATION_SCHEMA,
        "receipt_id": _require_uuid(receipt_id or str(uuid4()), "receipt_id"),
        "provider": "stripe",
        "source_event_id": _require_string(source_event_id, "source_event_id"),
        "producer_trust_domain": producer_domain,
        "verifier_id": _require_string(verifier_id, "verifier_id"),
        "verifier_trust_domain": verifier_domain,
        "algorithm": verification_body["algorithm"],
        "outcome": verification_body["outcome"],
        "reason": verification_body["reason"],
        "evidence_class": (
            "E4_EXTERNAL_SYMMETRIC_VERIFIED"
            if verification_body["verified"]
            else "E3_EXTERNAL_UNVERIFIED"
        ),
        "verification": {
            "signature_timestamp": verification_body["signature_timestamp"],
            "age_seconds": verification_body["age_seconds"],
            "tolerance_seconds": verification_body["tolerance_seconds"],
            "matched_secret_version_refs": verification_body["matched_secret_version_refs"],
            "candidate_signature_count": verification_body["candidate_signature_count"],
            "configured_secret_version_count": verification_body["configured_secret_version_count"],
            "raw_body_sha256": verification_body["raw_body_sha256"],
            "signature_header_sha256": verification_body["signature_header_sha256"],
            "verification_sha256": supplied,
        },
        "independence": {
            "trust_domain_labels_distinct": True,
            "authenticated_workload_identity_verified_by_this_builder": False,
            "independent_attestation_claimed": False,
            "shared_secret_verification": True,
            "public_key_non_repudiation": False,
            "external_witness_still_required_for_admin_resistant_immutability": True,
        },
        "verified_at": _utc_iso(verified_at),
    }
    content_sha256 = sha256_json(body)
    body["admission"] = {
        "schema": VERIFIER_ADMISSION_SCHEMA,
        "key_version_ref": key_version_ref,
        "content_sha256": content_sha256,
        "mac_sha256": hmac.new(
            admission_key_bytes,
            f"dail-verifier-admission-v1|{content_sha256}".encode("ascii"),
            hashlib.sha256,
        ).hexdigest(),
    }
    body["receipt_sha256"] = sha256_json(body)
    return body


def _validate_digest_map(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise DailError(f"{field} must be a non-empty object")
    normalized: dict[str, str] = {}
    for ref, digest in value.items():
        key = _require_string(ref, f"{field} reference")
        normalized[key] = _require_sha256(digest, f"{field}.{key}")
    return dict(sorted(normalized.items()))


def _validate_assurance_state(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DailError(f"{field} must be an object")
    state = _copy_json(value)
    required = {"status", "receipt_ref", "receipt_sha256", "verifier_id"}
    missing = required - set(state)
    if missing:
        raise DailError(f"{field} missing fields: {sorted(missing)}")
    if state["status"] not in {"PASS", "FAIL", "HOLD", "NOT_RUN"}:
        raise DailError(f"{field}.status is invalid")
    _require_string(state["receipt_ref"], f"{field}.receipt_ref")
    _require_sha256(state["receipt_sha256"], f"{field}.receipt_sha256")
    _require_string(state["verifier_id"], f"{field}.verifier_id")
    return state


def _validate_checkpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DailError("predecessor_checkpoint must be an object")
    checkpoint = _copy_json(value)
    required = {"checkpoint_id", "chain_id", "sequence", "event_hash"}
    missing = required - set(checkpoint)
    if missing:
        raise DailError(f"predecessor_checkpoint missing fields: {sorted(missing)}")
    _require_string(checkpoint["checkpoint_id"], "predecessor_checkpoint.checkpoint_id")
    _require_string(checkpoint["chain_id"], "predecessor_checkpoint.chain_id")
    if not isinstance(checkpoint["sequence"], int) or checkpoint["sequence"] < 1:
        raise DailError("predecessor_checkpoint.sequence must be positive")
    _require_sha256(checkpoint["event_hash"], "predecessor_checkpoint.event_hash")
    return checkpoint


def _validate_next_action(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DailError("next_action must be an object")
    action = _copy_json(value)
    required = {"action", "owner_ref", "authority_class", "requires_human_approval"}
    missing = required - set(action)
    if missing:
        raise DailError(f"next_action missing fields: {sorted(missing)}")
    _require_string(action["action"], "next_action.action")
    _require_string(action["owner_ref"], "next_action.owner_ref")
    if action["authority_class"] not in DECISION_CLASSES:
        raise DailError("next_action.authority_class must be D0-D3")
    if not isinstance(action["requires_human_approval"], bool):
        raise DailError("next_action.requires_human_approval must be boolean")
    if action["authority_class"] == "D3" and not action["requires_human_approval"]:
        raise DailError("D3 next actions must remain human-reserved")
    return action


def build_factory_continuation_receipt(
    *,
    factory_id: str,
    run_id: str,
    stage: str,
    source_digests: Mapping[str, str],
    artifact_digests: Mapping[str, str],
    test_state: Mapping[str, Any],
    security_state: Mapping[str, Any],
    predecessor_checkpoint: Mapping[str, Any],
    next_action: Mapping[str, Any],
    producer_id: str,
    receipt_id: Optional[str] = None,
    created_at: Optional[datetime | str] = None,
) -> dict[str, Any]:
    """Build an exact, non-authorizing checkpoint for a factory continuation."""

    tests = _validate_assurance_state(test_state, "test_state")
    security = _validate_assurance_state(security_state, "security_state")
    producer = _require_string(producer_id, "producer_id")
    if producer in {tests["verifier_id"], security["verifier_id"]}:
        raise DailError("factory producer cannot independently verify its own continuation")
    ready = tests["status"] == "PASS" and security["status"] == "PASS"
    deterministic_content: dict[str, Any] = {
        "factory_id": _require_string(factory_id, "factory_id"),
        "run_id": _require_string(run_id, "run_id"),
        "stage": _require_string(stage, "stage"),
        "source_digests": _validate_digest_map(source_digests, "source_digests"),
        "artifact_digests": _validate_digest_map(artifact_digests, "artifact_digests"),
        "test_state": tests,
        "security_state": security,
        "predecessor_checkpoint": _validate_checkpoint(predecessor_checkpoint),
        "next_action": _validate_next_action(next_action),
        "continuation_state": "READY_FOR_GOVERNED_CONTINUATION" if ready else "HOLD",
        "producer_id": producer,
        "self_certification": False,
        "production_authority_granted": False,
        "provider_write_authority_granted": False,
        "requires_dail_append": True,
    }
    body: dict[str, Any] = {
        "schema": FACTORY_CONTINUATION_SCHEMA,
        "receipt_id": receipt_id or f"dfc-{uuid4().hex}",
        **deterministic_content,
        # Occurrence identity/time do not affect the reproducible checkpoint.
        "content_sha256": sha256_json(deterministic_content),
        "created_at": _utc_iso(created_at),
    }
    _require_string(body["receipt_id"], "receipt_id")
    body["receipt_sha256"] = sha256_json(body)
    return body


def prepare_unavailable_write(
    *,
    event_class: str,
    allow_unsealed_telemetry: bool = False,
    source_system: Optional[str] = None,
    source_event_id: Optional[str] = None,
    trust_domain: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    correlation_id: Optional[str] = None,
    causation_id: Optional[str] = None,
    payload_ref: Optional[str] = None,
    payload: Any = None,
    payload_sha256: Optional[str] = None,
    created_at: Optional[datetime | str] = None,
) -> dict[str, Any]:
    """Fail closed unless the caller explicitly queues low-risk telemetry.

    The returned packet is not a DAIL event.  It has no sequence or event hash
    and cannot be used as authority or evidence until a later sealed append.
    """

    classification = classify_event(event_class)
    if classification["material"] or classification["consequential"]:
        raise DailUnavailableError("material or consequential writes require a successful DAIL append")
    if not allow_unsealed_telemetry:
        raise DailUnavailableError("unsealed telemetry queueing was not explicitly authorized")
    if event_class != "low_risk_telemetry":
        raise DailUnavailableError("only low-risk telemetry may be queued unsealed")
    for field, value in (
        ("source_system", source_system),
        ("source_event_id", source_event_id),
        ("trust_domain", trust_domain),
        ("idempotency_key", idempotency_key),
        ("correlation_id", correlation_id),
        ("payload_ref", payload_ref),
    ):
        _require_string(value, field)
    if causation_id is not None:
        _require_string(causation_id, "causation_id")
    if payload is None:
        normalized_payload = None
        normalized_payload_sha = _require_sha256(payload_sha256, "payload_sha256")
    else:
        normalized_payload = _copy_json(payload)
        normalized_payload_sha = sha256_json(normalized_payload)
        if payload_sha256 is not None and payload_sha256 != normalized_payload_sha:
            raise DailIntegrityError("supplied payload_sha256 does not match telemetry payload")
    body: dict[str, Any] = {
        "schema": UNSEALED_TELEMETRY_SCHEMA,
        "event_class": event_class,
        "classification": classification,
        "source_system": source_system,
        "source_event_id": source_event_id,
        "trust_domain": trust_domain,
        "idempotency_key": idempotency_key,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "payload": normalized_payload,
        "payload_sha256": normalized_payload_sha,
        "payload_ref": payload_ref,
        "seal_state": "queued_unsealed",
        "dail_sequence": None,
        "dail_event_hash": None,
        "grants_authority": False,
        "counts_as_dail_evidence": False,
        "requires_dail_append": True,
        "created_at": _utc_iso(created_at),
    }
    body["queue_sha256"] = sha256_json(body)
    return body
