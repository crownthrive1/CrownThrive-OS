from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Iterable

DAIL_SCHEMA_ID = "ct.contract.chlom.dail-event.v1"
DAIL_SCHEMA_VERSION = "1.0.0"
EVIDENCE_SCHEMA_ID = "ct.contract.chlom.evidence-reference.v1"
EVIDENCE_SCHEMA_VERSION = "1.0.0"
CLASSIFICATIONS = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED", "SEALED"}
DOCS_IMPACT = {"docs_updated", "docs_no_change", "docs_delta_opened"}
EVENT_TYPES = {
    "source_observed",
    "source_conflict_opened",
    "decision_recorded",
    "correction_recorded",
    "attestation_recorded",
    "export_recorded",
}
STATES = {"observed", "allow", "deny", "hold", "corrected", "attested", "exported"}
FORBIDDEN_KEYS = {
    "raw_body",
    "raw_evidence",
    "evidence_body",
    "secret",
    "secret_key",
    "password",
    "credential",
    "access_token",
    "refresh_token",
    "private_key",
    "authorization",
}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
EVENT_ID = re.compile(r"^ct\.dail\.event\.[A-Za-z0-9._-]+$")
EVIDENCE_ID = re.compile(r"^ct\.evidence\.ref\.[A-Za-z0-9._-]+$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(value: Any) -> str:
    text = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                return True
            if _contains_forbidden_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def validate_evidence_reference(ref: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_id",
        "schema_version",
        "evidence_ref_id",
        "kind",
        "classification",
        "source_ref",
        "locator_ref",
        "digest_sha256",
        "content_included",
        "public_projection_allowed",
        "retention_class",
    }
    missing = sorted(required - set(ref))
    if missing:
        errors.append(f"missing:{','.join(missing)}")
    if ref.get("schema_id") != EVIDENCE_SCHEMA_ID or ref.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append("schema_identity")
    if not EVIDENCE_ID.fullmatch(str(ref.get("evidence_ref_id", ""))):
        errors.append("evidence_ref_id")
    if ref.get("classification") not in CLASSIFICATIONS:
        errors.append("classification")
    if not HEX64.fullmatch(str(ref.get("digest_sha256", ""))):
        errors.append("digest_sha256")
    if ref.get("content_included") is not False:
        errors.append("content_must_not_be_embedded")
    if ref.get("classification") in {"RESTRICTED", "SEALED"} and ref.get("public_projection_allowed") is not False:
        errors.append("restricted_public_projection")
    if _contains_forbidden_key(ref):
        errors.append("forbidden_secret_or_raw_evidence_key")
    return errors


def _event_hash_material(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key != "event_hash"}


def validate_event(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_id",
        "schema_version",
        "event_id",
        "event_type",
        "sequence",
        "occurred_at",
        "subject_ref",
        "decision_ref",
        "correlation_id",
        "causation_id",
        "classification",
        "source_refs",
        "evidence_refs",
        "state",
        "reason_code",
        "supersedes_event_id",
        "previous_hash",
        "payload_hash",
        "event_hash",
        "docs_impact",
    }
    missing = sorted(required - set(event))
    if missing:
        errors.append(f"missing:{','.join(missing)}")
    if event.get("schema_id") != DAIL_SCHEMA_ID or event.get("schema_version") != DAIL_SCHEMA_VERSION:
        errors.append("schema_identity")
    if not EVENT_ID.fullmatch(str(event.get("event_id", ""))):
        errors.append("event_id")
    if event.get("event_type") not in EVENT_TYPES:
        errors.append("event_type")
    if not isinstance(event.get("sequence"), int) or int(event.get("sequence", 0)) < 1:
        errors.append("sequence")
    if event.get("classification") not in CLASSIFICATIONS:
        errors.append("classification")
    if event.get("state") not in STATES:
        errors.append("state")
    if event.get("docs_impact") not in DOCS_IMPACT:
        errors.append("docs_impact")
    if not isinstance(event.get("source_refs"), list) or len(event.get("source_refs", [])) != len(set(event.get("source_refs", []))):
        errors.append("source_refs")
    evidence_refs = event.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or len(evidence_refs) != len(set(evidence_refs)):
        errors.append("evidence_refs")
    elif any(not EVIDENCE_ID.fullmatch(str(item)) for item in evidence_refs):
        errors.append("evidence_ref_id")
    previous_hash = str(event.get("previous_hash", ""))
    if previous_hash != "GENESIS" and not HEX64.fullmatch(previous_hash):
        errors.append("previous_hash")
    if not HEX64.fullmatch(str(event.get("payload_hash", ""))):
        errors.append("payload_hash")
    if not HEX64.fullmatch(str(event.get("event_hash", ""))):
        errors.append("event_hash")
    if _contains_forbidden_key(event):
        errors.append("forbidden_secret_or_raw_evidence_key")
    expected = sha256_hex(_event_hash_material(event))
    if event.get("event_hash") != expected:
        errors.append("event_hash_mismatch")
    return errors


def build_event(event_input: dict[str, Any], *, sequence: int, previous_hash: str) -> dict[str, Any]:
    payload_material = {
        "event_type": event_input["event_type"],
        "subject_ref": event_input["subject_ref"],
        "decision_ref": event_input["decision_ref"],
        "correlation_id": event_input["correlation_id"],
        "causation_id": event_input.get("causation_id"),
        "classification": event_input["classification"],
        "source_refs": event_input.get("source_refs", []),
        "evidence_refs": event_input.get("evidence_refs", []),
        "state": event_input["state"],
        "reason_code": event_input["reason_code"],
        "supersedes_event_id": event_input.get("supersedes_event_id"),
        "docs_impact": event_input["docs_impact"],
    }
    event = {
        "schema_id": DAIL_SCHEMA_ID,
        "schema_version": DAIL_SCHEMA_VERSION,
        "event_id": event_input["event_id"],
        "event_type": event_input["event_type"],
        "sequence": sequence,
        "occurred_at": event_input["occurred_at"],
        "subject_ref": event_input["subject_ref"],
        "decision_ref": event_input["decision_ref"],
        "correlation_id": event_input["correlation_id"],
        "causation_id": event_input.get("causation_id"),
        "classification": event_input["classification"],
        "source_refs": list(event_input.get("source_refs", [])),
        "evidence_refs": list(event_input.get("evidence_refs", [])),
        "state": event_input["state"],
        "reason_code": event_input["reason_code"],
        "supersedes_event_id": event_input.get("supersedes_event_id"),
        "previous_hash": previous_hash,
        "payload_hash": sha256_hex(payload_material),
        "docs_impact": event_input["docs_impact"],
    }
    event["event_hash"] = sha256_hex(event)
    return event


def build_chain(event_inputs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    previous_hash = "GENESIS"
    for sequence, event_input in enumerate(event_inputs, start=1):
        event = build_event(event_input, sequence=sequence, previous_hash=previous_hash)
        errors = validate_event(event)
        if errors:
            raise ValueError(f"invalid_event:{event.get('event_id')}:{','.join(errors)}")
        events.append(event)
        previous_hash = event["event_hash"]
    return events


def verify_chain(events: Iterable[dict[str, Any]]) -> tuple[bool, list[str]]:
    rows = [deepcopy(event) for event in events]
    errors: list[str] = []
    seen_ids: set[str] = set()
    previous_hash = "GENESIS"
    correlation: str | None = None
    for expected_sequence, event in enumerate(rows, start=1):
        event_id = str(event.get("event_id", ""))
        if event_id in seen_ids:
            errors.append(f"duplicate_event_id:{event_id}")
        if event.get("sequence") != expected_sequence:
            errors.append(f"sequence:{event_id}")
        if event.get("previous_hash") != previous_hash:
            errors.append(f"previous_hash:{event_id}")
        if correlation is None:
            correlation = str(event.get("correlation_id", ""))
        elif event.get("correlation_id") != correlation:
            errors.append(f"correlation:{event_id}")
        causation_id = event.get("causation_id")
        if causation_id is not None and causation_id not in seen_ids:
            errors.append(f"causation_not_prior:{event_id}")
        supersedes = event.get("supersedes_event_id")
        if supersedes is not None and supersedes not in seen_ids:
            errors.append(f"supersedes_not_prior:{event_id}")
        for item in validate_event(event):
            errors.append(f"{item}:{event_id}")
        seen_ids.add(event_id)
        previous_hash = str(event.get("event_hash", ""))
    return not errors, errors


def reconstruct_decision_lineage(events: Iterable[dict[str, Any]], decision_ref: str) -> dict[str, Any]:
    selected = [deepcopy(event) for event in events if event.get("decision_ref") == decision_ref]
    ok, errors = verify_chain(events)
    superseded_by: dict[str, str] = {}
    for event in selected:
        supersedes = event.get("supersedes_event_id")
        if supersedes:
            superseded_by[str(supersedes)] = str(event["event_id"])
    current = [event for event in selected if event["event_id"] not in superseded_by]
    return {
        "decision_ref": decision_ref,
        "chain_verified": ok,
        "chain_errors": errors,
        "event_ids": [event["event_id"] for event in selected],
        "superseded_by": superseded_by,
        "current_event_ids": [event["event_id"] for event in current],
    }


def export_bundle(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = [deepcopy(event) for event in events]
    ok, errors = verify_chain(rows)
    if not ok:
        raise ValueError(f"cannot_export_invalid_chain:{','.join(errors)}")
    return {
        "schema_id": "ct.export.chlom.dail-bundle.v1",
        "schema_version": "1.0.0",
        "event_count": len(rows),
        "first_event_hash": rows[0]["event_hash"] if rows else None,
        "last_event_hash": rows[-1]["event_hash"] if rows else None,
        "events": rows,
        "bundle_hash": sha256_hex(rows),
    }
