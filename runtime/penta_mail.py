#!/usr/bin/env python3
"""PentaMail governed institutional email runtime.

The module is dependency-free. It validates communication envelopes, maintains
an idempotent evidence ledger, talks to registered mail providers, normalizes
provider receipts/readback, and exposes an explicit certification-send path.

Authority invariant: provider credentials and transport capability never create
permission to send. A consequential provider write requires an explicit
authorization context supplied by the calling governance layer.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
from http import HTTPStatus
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request

UTC = dt.timezone.utc
SCHEMA = "ct.pentamail.envelope.v1"
RECEIPT_SCHEMA = "ct.pentamail.receipt.v1"
EVIDENCE_SCHEMA = "ct.pentamail.provider-evidence.v1"
LIFECYCLE = {
    "requested", "authorized", "queued", "accepted", "delivered", "deferred",
    "bounced", "failed", "complained",
}
TERMINAL = {"delivered", "bounced", "failed", "complained"}
CLASSIFICATIONS = {"public", "internal", "confidential", "restricted"}
PRIORITIES = {"low", "normal", "high", "urgent"}
AUTHORITY_CLASSES = {"D0", "D1", "D2", "D3"}
CORRELATION_HEADER = "X-CrownThrive-Correlation-ID"
IDEMPOTENCY_HEADER = "X-CrownThrive-Idempotency-Key"
ORIGIN_PENTA_HEADER = "X-CrownThrive-Origin-Penta"
CORRELATION_TAG = "ct_correlation_sha256"
IDEMPOTENCY_TAG = "ct_idempotency_sha256"
BODY_TAG = "ct_body_sha256"
EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
PROVIDER_MESSAGE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{8,}"
)


class PentaMailError(ValueError):
    """Fail-closed PentaMail validation/transport error."""


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so provider credentials never cross an origin hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT_OPENER = urllib.request.build_opener(NoRedirectHandler())


def open_no_redirect(request: urllib.request.Request, *, timeout: int):
    return _NO_REDIRECT_OPENER.open(request, timeout=timeout)


def now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalized_provider_tags(value: Any) -> dict[str, str] | None:
    """Normalize provider-returned Resend tags without accepting ambiguity."""
    if not isinstance(value, list):
        return None
    normalized: dict[str, str] = {}
    for item in value:
        if not isinstance(item, Mapping):
            return None
        name = item.get("name")
        tag_value = item.get("value")
        if not isinstance(name, str) or not isinstance(tag_value, str):
            return None
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", name):
            return None
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", tag_value):
            return None
        if name in normalized:
            return None
        normalized[name] = tag_value
    return normalized


def _normalized_provider_headers(value: Any) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    normalized: dict[str, str] = {}
    for name, header_value in value.items():
        if not isinstance(name, str) or not isinstance(header_value, str):
            return None
        key = name.strip().lower()
        if not key or key in normalized:
            return None
        normalized[key] = header_value
    return normalized


def _safe_text(value: str, field: str, *, max_length: int = 10000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PentaMailError(f"{field} must be a non-empty string")
    if "\r" in value or "\x00" in value:
        raise PentaMailError(f"{field} contains unsafe control characters")
    if len(value) > max_length:
        raise PentaMailError(f"{field} exceeds maximum length")
    return value.strip()


def _provider_message_id(value: Any) -> str:
    if not isinstance(value, str) or not PROVIDER_MESSAGE_ID_RE.fullmatch(value):
        raise PentaMailError("provider did not return a valid stable message id")
    return value


def _extract_address(identity: str) -> str:
    value = _safe_text(identity, "email identity", max_length=320)
    if "\n" in value:
        raise PentaMailError("email identity contains unsafe newline")
    if "<" in value or ">" in value:
        match = re.fullmatch(r".*<([^<>]+)>", value)
        if not match:
            raise PentaMailError("invalid display-name email identity")
        value = match.group(1).strip()
    if not EMAIL_RE.fullmatch(value):
        raise PentaMailError(f"invalid email address: {value!r}")
    return value


@dataclasses.dataclass(frozen=True)
class CommunicationEnvelope:
    origin_penta: str
    purpose: str
    classification: str
    recipient: str
    sender_identity: str
    subject: str
    body_text: str
    correlation_id: str
    authority_ref: str
    authority_class: str
    priority: str
    retention_classification: str
    idempotency_key: str
    requested_at: str
    schema: str = SCHEMA

    def validate(self) -> None:
        if self.schema != SCHEMA:
            raise PentaMailError("unexpected envelope schema")
        if not self.origin_penta.startswith("penta."):
            raise PentaMailError("origin_penta must be a registered-style penta.* key")
        _safe_text(self.purpose, "purpose", max_length=512)
        if self.classification not in CLASSIFICATIONS:
            raise PentaMailError("invalid classification")
        _extract_address(self.recipient)
        _extract_address(self.sender_identity)
        subject = _safe_text(self.subject, "subject", max_length=998)
        if "\n" in subject:
            raise PentaMailError("subject contains unsafe newline")
        _safe_text(self.body_text, "body_text", max_length=200000)
        if SECRET_RE.search(self.body_text):
            raise PentaMailError("body_text appears to contain secret material")
        for field, value in (
            ("correlation_id", self.correlation_id),
            ("authority_ref", self.authority_ref),
            ("idempotency_key", self.idempotency_key),
            ("retention_classification", self.retention_classification),
        ):
            safe_value = _safe_text(value, field, max_length=256)
            if "\n" in safe_value:
                raise PentaMailError(f"{field} contains unsafe newline")
        if self.authority_class not in AUTHORITY_CLASSES:
            raise PentaMailError("invalid authority_class")
        if self.authority_class == "D0":
            raise PentaMailError("provider email_send requires at least D1 authority")
        if self.priority not in PRIORITIES:
            raise PentaMailError("invalid priority")
        try:
            parsed = dt.datetime.fromisoformat(self.requested_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PentaMailError("requested_at must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise PentaMailError("requested_at must include timezone")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class AuthorizationContext:
    authorized: bool
    authorized_by: str
    authority_ref: str
    authority_class: str = "D1"
    purpose_scope: str = "institutional_email"
    authorized_at: str = dataclasses.field(default_factory=now)

    def validate_for(self, envelope: CommunicationEnvelope) -> None:
        if self.authorized is not True:
            raise PentaMailError("send is not authorized")
        _safe_text(self.authorized_by, "authorized_by", max_length=256)
        _safe_text(self.authority_ref, "authorization authority_ref", max_length=256)
        if self.authority_ref != envelope.authority_ref:
            raise PentaMailError("authorization authority_ref does not match envelope")
        if self.authority_class not in AUTHORITY_CLASSES - {"D0"}:
            raise PentaMailError("email send requires D1-D3 authority context")
        if self.authority_class != envelope.authority_class:
            raise PentaMailError("authorization authority_class does not match envelope")
        if self.purpose_scope != "institutional_email":
            raise PentaMailError("authorization purpose_scope does not permit email")
        try:
            parsed = dt.datetime.fromisoformat(self.authorized_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PentaMailError("authorized_at must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise PentaMailError("authorized_at must include timezone")


def build_envelope(
    *,
    origin_penta: str,
    purpose: str,
    classification: str,
    recipient: str,
    sender_identity: str,
    subject: str,
    body_text: str,
    correlation_id: str,
    authority_ref: str,
    authority_class: str,
    priority: str = "normal",
    retention_classification: str = "institutional_status",
    idempotency_key: str | None = None,
    requested_at: str | None = None,
) -> CommunicationEnvelope:
    material = {
        "origin_penta": origin_penta,
        "purpose": purpose,
        "recipient": recipient,
        "subject": subject,
        "correlation_id": correlation_id,
        "authority_ref": authority_ref,
    }
    envelope = CommunicationEnvelope(
        origin_penta=origin_penta,
        purpose=purpose,
        classification=classification,
        recipient=recipient,
        sender_identity=sender_identity,
        subject=subject,
        body_text=body_text,
        correlation_id=correlation_id,
        authority_ref=authority_ref,
        authority_class=authority_class,
        priority=priority,
        retention_classification=retention_classification,
        idempotency_key=idempotency_key or ("pm-" + stable_hash(material)[:24]),
        requested_at=requested_at or now(),
    )
    envelope.validate()
    return envelope


def envelope_binding_hash(envelope: CommunicationEnvelope) -> str:
    """Bind idempotent replay to all delivery and authority material.

    `requested_at` is intentionally excluded so a legitimate retry can rebuild
    the same governed message while retaining the provider idempotency key.
    """
    envelope.validate()
    return stable_hash({
        "schema": envelope.schema,
        "origin_penta": envelope.origin_penta,
        "purpose": envelope.purpose,
        "classification": envelope.classification,
        "recipient": envelope.recipient,
        "sender_identity": envelope.sender_identity,
        "subject": envelope.subject,
        "body_text": envelope.body_text,
        "correlation_id": envelope.correlation_id,
        "authority_ref": envelope.authority_ref,
        "authority_class": envelope.authority_class,
        "priority": envelope.priority,
        "retention_classification": envelope.retention_classification,
        "idempotency_key": envelope.idempotency_key,
    })


class EvidenceLedger:
    """Append-only non-secret lifecycle/evidence ledger with idempotency guard."""

    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.events_path = self.state_dir / "events.jsonl"
        self.index_path = self.state_dir / "idempotency.json"

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {}
        value = json.loads(self.index_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise PentaMailError("invalid idempotency index")
        return value

    def _write_index(self, index: Mapping[str, Any]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(dict(index), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def append(self, envelope: CommunicationEnvelope, state: str, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if state not in LIFECYCLE:
            raise PentaMailError(f"invalid lifecycle state: {state}")
        event = {
            "schema": "ct.pentamail.lifecycle-event.v1",
            "message_key": envelope.idempotency_key,
            "correlation_id": envelope.correlation_id,
            "origin_penta": envelope.origin_penta,
            "recipient_hash": "sha256:" + hashlib.sha256(_extract_address(envelope.recipient).encode()).hexdigest()[:16],
            "subject_hash": "sha256:" + hashlib.sha256(envelope.subject.encode()).hexdigest()[:16],
            "state": state,
            "evidence": dict(evidence or {}),
            "observed_at": now(),
        }
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(canonical_json(event) + "\n")
        return event

    def prior_receipt(self, envelope: CommunicationEnvelope) -> dict[str, Any] | None:
        return self._load_index().get(envelope.idempotency_key)

    def remember_receipt(self, envelope: CommunicationEnvelope, receipt: Mapping[str, Any]) -> None:
        index = self._load_index()
        existing = index.get(envelope.idempotency_key)
        if existing and existing.get("provider_message_id") != receipt.get("provider_message_id"):
            raise PentaMailError("idempotency collision: key already bound to different provider message")
        index[envelope.idempotency_key] = dict(receipt)
        self._write_index(index)


class ResendAdapter:
    provider_id = "resend"

    def __init__(self, api_key: str | None = None, timeout: int = 15):
        self.api_key = (api_key or os.environ.get("RESEND_API_KEY") or "").strip()
        self.timeout = timeout
        if not self.api_key:
            raise PentaMailError("RESEND_API_KEY is not bound")

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        url = "https://api.resend.com" + path
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "User-Agent": "CrownThrive-PentaMail/1.0",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = canonical_json(dict(payload)).encode("utf-8")
        if idempotency_key is not None:
            safe_key = _safe_text(idempotency_key, "provider idempotency key", max_length=256)
            if "\n" in safe_key:
                raise PentaMailError("provider idempotency key contains unsafe newline")
            headers["Idempotency-Key"] = safe_key
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with open_no_redirect(request, timeout=self.timeout) as response:
                raw = response.read(1024 * 1024)
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
                return int(response.status), parsed
        except urllib.error.HTTPError as exc:
            try:
                reason = HTTPStatus(int(exc.code)).phrase
            except ValueError:
                reason = "provider request failed"
            # Provider error bodies can echo recipients, senders, or message
            # content. Never copy that body (or an untrusted reason) into logs.
            raise PentaMailError(f"resend HTTP {int(exc.code)}: {reason}") from None
        except urllib.error.URLError:
            raise PentaMailError("resend transport error") from None

    def domain_read(self) -> dict[str, Any]:
        status, payload = self._request("GET", "/domains")
        ok = status == 200
        return {
            "schema": EVIDENCE_SCHEMA,
            "provider": self.provider_id,
            "operation": "domain_read",
            "result": "PASS" if ok else "FAIL",
            "readback": ok,
            "http_status": status,
            "observed_at": now(),
            "domain_count": len(payload.get("data") or []),
        }

    def send(self, envelope: CommunicationEnvelope, authorization: AuthorizationContext) -> dict[str, Any]:
        envelope.validate()
        authorization.validate_for(envelope)
        status, payload = self._request(
            "POST",
            "/emails",
            {
                "from": envelope.sender_identity,
                "to": [envelope.recipient],
                "subject": envelope.subject,
                "text": envelope.body_text,
                "headers": {
                    CORRELATION_HEADER: envelope.correlation_id,
                    ORIGIN_PENTA_HEADER: envelope.origin_penta,
                    IDEMPOTENCY_HEADER: envelope.idempotency_key,
                },
                # Retrieve Sent Email returns tags but does not expose custom
                # request headers. These hashes provide the provider-owned
                # correlation/idempotency/body binding used by readback.
                "tags": [
                    {"name": CORRELATION_TAG, "value": stable_hash(envelope.correlation_id)},
                    {"name": IDEMPOTENCY_TAG, "value": stable_hash(envelope.idempotency_key)},
                    {"name": BODY_TAG, "value": stable_hash(envelope.body_text)},
                ],
            },
            idempotency_key=envelope.idempotency_key,
        )
        message_id = payload.get("id")
        if status not in {200, 201}:
            raise PentaMailError("provider did not return a stable message id")
        message_id = _provider_message_id(message_id)
        return {
            "provider": self.provider_id,
            "provider_message_id": message_id,
            "http_status": status,
            "accepted": True,
            "accepted_at": now(),
        }

    def readback(
        self,
        message_id: str,
        envelope: CommunicationEnvelope,
    ) -> dict[str, Any]:
        message_id = _provider_message_id(message_id)
        envelope.validate()
        encoded_id = urllib.parse.quote(message_id, safe="")
        status, payload = self._request("GET", "/emails/" + encoded_id)
        if not isinstance(payload, dict):
            payload = {}
        same_id = isinstance(payload, dict) and payload.get("id") == message_id
        provider_event = str(payload.get("last_event") or "accepted").lower()
        normalized = {
            "delivered": "delivered",
            "delivery_delayed": "deferred",
            "bounced": "bounced",
            "complained": "complained",
            "failed": "failed",
            "sent": "accepted",
            "queued": "accepted",
        }.get(provider_event, "accepted")
        recipient_matches = payload.get("to") == [envelope.recipient]
        sender_matches = payload.get("from") == envelope.sender_identity
        subject_matches = payload.get("subject") == envelope.subject
        body_matches = payload.get("text") == envelope.body_text
        provider_tags = _normalized_provider_tags(payload.get("tags"))
        tags_returned = provider_tags is not None
        correlation_binding_matches = bool(
            provider_tags
            and provider_tags.get(CORRELATION_TAG) == stable_hash(envelope.correlation_id)
        )
        idempotency_binding_matches = bool(
            provider_tags
            and provider_tags.get(IDEMPOTENCY_TAG) == stable_hash(envelope.idempotency_key)
        )
        body_hash_binding_matches = bool(
            provider_tags
            and provider_tags.get(BODY_TAG) == stable_hash(envelope.body_text)
        )
        raw_provider_headers = payload.get("headers")
        headers_exposed = raw_provider_headers is not None
        provider_headers = _normalized_provider_headers(raw_provider_headers)
        exposed_correlation_header_matches = bool(
            provider_headers
            and provider_headers.get(CORRELATION_HEADER.lower()) == envelope.correlation_id
        )
        exposed_idempotency_header_matches = bool(
            provider_headers
            and provider_headers.get(IDEMPOTENCY_HEADER.lower()) == envelope.idempotency_key
        )
        exposed_headers_consistent = bool(
            not headers_exposed
            or (exposed_correlation_header_matches and exposed_idempotency_header_matches)
        )
        content_verified = bool(
            recipient_matches
            and sender_matches
            and subject_matches
            and body_matches
            and correlation_binding_matches
            and idempotency_binding_matches
            and body_hash_binding_matches
            and exposed_headers_consistent
        )
        passed = bool(status == 200 and same_id and content_verified)
        failures: list[str] = []
        if not same_id:
            failures.append("provider_message_id_mismatch")
        if not recipient_matches:
            failures.append("recipient_binding_mismatch")
        if not sender_matches:
            failures.append("sender_binding_mismatch")
        if not subject_matches:
            failures.append("subject_binding_mismatch")
        if not body_matches:
            failures.append("body_binding_mismatch")
        if not tags_returned:
            failures.append("provider_binding_tags_not_returned")
        if not correlation_binding_matches:
            failures.append("correlation_tag_binding_unverified")
        if not idempotency_binding_matches:
            failures.append("idempotency_tag_binding_unverified")
        if not body_hash_binding_matches:
            failures.append("body_hash_tag_binding_unverified")
        if not exposed_headers_consistent:
            failures.append("provider_returned_header_binding_mismatch")
        return {
            "schema": EVIDENCE_SCHEMA,
            "provider": self.provider_id,
            "operation": "email_send",
            "result": "PASS" if passed else "FAIL",
            "readback": passed,
            "http_status": status,
            "provider_message_id": message_id,
            "provider_event": provider_event,
            "normalized_state": normalized,
            "recipient_binding_verified": recipient_matches,
            "sender_binding_verified": sender_matches,
            "subject_binding_verified": subject_matches,
            "body_binding_verified": body_matches,
            "provider_binding_channel": "resend_tags",
            "provider_binding_tags_returned": tags_returned,
            "correlation_binding_verified": correlation_binding_matches,
            "idempotency_binding_verified": idempotency_binding_matches,
            "body_hash_binding_verified": body_hash_binding_matches,
            "provider_returned_headers_exposed": headers_exposed,
            "provider_returned_headers_consistent": exposed_headers_consistent,
            "exact_content_binding_verified": content_verified,
            "custom_header_readback_state": (
                "NOT_EXPOSED_BY_RESEND_RETRIEVE_API"
                if not headers_exposed
                else "VERIFIED"
                if exposed_headers_consistent
                else "MISMATCH"
            ),
            **({"reason": ",".join(failures)} if failures else {}),
            "observed_at": now(),
        }


def certification_send(
    *,
    envelope: CommunicationEnvelope,
    authorization: AuthorizationContext,
    state_dir: Path,
    adapter: ResendAdapter | None = None,
) -> dict[str, Any]:
    """Perform one explicitly authorized D1 certification send and exact readback."""
    envelope.validate()
    authorization.validate_for(envelope)
    ledger = EvidenceLedger(state_dir)
    prior = ledger.prior_receipt(envelope)
    if prior:
        prior_binding = prior.get("verification_binding")
        prior_hash = (
            prior_binding.get("envelope_binding_sha256")
            if isinstance(prior_binding, Mapping)
            else None
        )
        if prior_hash != envelope_binding_hash(envelope):
            raise PentaMailError(
                "idempotency collision: prior receipt is bound to a different envelope"
            )
        return {**prior, "idempotent_replay": True}

    adapter = adapter or ResendAdapter()
    domain_evidence = adapter.domain_read()
    if domain_evidence.get("result") != "PASS" or domain_evidence.get("readback") is not True:
        raise PentaMailError("provider read-only certification did not pass")
    ledger.append(envelope, "authorized", {"authority_ref": authorization.authority_ref})
    ledger.append(envelope, "queued", {"provider": adapter.provider_id})
    accepted = adapter.send(envelope, authorization)
    ledger.append(envelope, "accepted", {"provider": adapter.provider_id, "provider_message_id": accepted["provider_message_id"]})
    readback = adapter.readback(accepted["provider_message_id"], envelope)
    if readback.get("result") != "PASS" or readback.get("readback") is not True:
        raise PentaMailError("email_send exact readback failed")
    required_exact_bindings = (
        "body_binding_verified",
        "correlation_binding_verified",
        "idempotency_binding_verified",
        "body_hash_binding_verified",
        "exact_content_binding_verified",
    )
    if any(readback.get(field) is not True for field in required_exact_bindings):
        raise PentaMailError("email_send provider content/tag binding failed")
    ledger.append(envelope, readback["normalized_state"], readback)
    recorded_at = now()
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "message_id": envelope.idempotency_key,
        "correlation_id": envelope.correlation_id,
        "provider": adapter.provider_id,
        "provider_message_id": accepted["provider_message_id"],
        "lifecycle_state": readback["normalized_state"],
        "provider_receipt": {
            "accepted_http_status": accepted["http_status"],
            "provider_event": readback["provider_event"],
            "readback_http_status": readback["http_status"],
            "body_binding_verified": readback["body_binding_verified"],
            "provider_binding_channel": readback["provider_binding_channel"],
            "correlation_binding_verified": readback["correlation_binding_verified"],
            "idempotency_binding_verified": readback["idempotency_binding_verified"],
            "body_hash_binding_verified": readback["body_hash_binding_verified"],
            "provider_returned_headers_exposed": readback.get(
                "provider_returned_headers_exposed", False
            ),
            "provider_returned_headers_consistent": readback.get(
                "provider_returned_headers_consistent", True
            ),
            "custom_header_readback_state": readback["custom_header_readback_state"],
        },
        "live_evidence": [domain_evidence, readback],
        "verification_binding": {
            "envelope_binding_sha256": envelope_binding_hash(envelope),
            "requested_at": envelope.requested_at,
            "recorded_at": recorded_at,
            "correlation_id": envelope.correlation_id,
            "idempotency_key": envelope.idempotency_key,
            "recipient_sha256": stable_hash(envelope.recipient),
            "sender_sha256": stable_hash(envelope.sender_identity),
            "subject_sha256": stable_hash(envelope.subject),
            "body_sha256": stable_hash(envelope.body_text),
            "correlation_header_name": CORRELATION_HEADER,
            "correlation_header_sha256": stable_hash(envelope.correlation_id),
            "idempotency_header_name": IDEMPOTENCY_HEADER,
            "idempotency_header_sha256": stable_hash(envelope.idempotency_key),
            "correlation_tag_name": CORRELATION_TAG,
            "correlation_tag_sha256": stable_hash(envelope.correlation_id),
            "idempotency_tag_name": IDEMPOTENCY_TAG,
            "idempotency_tag_sha256": stable_hash(envelope.idempotency_key),
            "body_tag_name": BODY_TAG,
            "body_tag_sha256": stable_hash(envelope.body_text),
            "provider_body_binding_verified": readback["body_binding_verified"],
            "provider_tag_binding_verified": bool(
                readback["correlation_binding_verified"]
                and readback["idempotency_binding_verified"]
                and readback["body_hash_binding_verified"]
            ),
            "custom_header_readback_state": readback["custom_header_readback_state"],
            "authority_ref": envelope.authority_ref,
        },
        "idempotent_replay": False,
        "recorded_at": recorded_at,
    }
    ledger.remember_receipt(envelope, receipt)
    return receipt


def owner_report(receipt: Mapping[str, Any]) -> str:
    provider_receipt = receipt.get("provider_receipt")
    provider_receipt = provider_receipt if isinstance(provider_receipt, Mapping) else {}
    body_binding = provider_receipt.get("body_binding_verified") is True
    correlation_binding = provider_receipt.get("correlation_binding_verified") is True
    idempotency_binding = provider_receipt.get("idempotency_binding_verified") is True
    body_hash_binding = provider_receipt.get("body_hash_binding_verified") is True
    header_state = provider_receipt.get(
        "custom_header_readback_state", "NOT_EXPOSED_BY_RESEND_RETRIEVE_API"
    )
    exact_binding = body_binding and body_hash_binding and correlation_binding and idempotency_binding
    return "\n".join(
        [
            "Penta Runtime Suite execution report",
            "",
            f"Correlation: {receipt.get('correlation_id')}",
            f"PentaMail provider: {receipt.get('provider')}",
            f"Provider message ID: {receipt.get('provider_message_id')}",
            f"Lifecycle state at readback: {receipt.get('lifecycle_state')}",
            f"Provider body binding: {'PASS' if body_binding else 'HOLD'}",
            f"Provider body-hash tag binding: {'PASS' if body_hash_binding else 'HOLD'}",
            f"Provider correlation-tag binding: {'PASS' if correlation_binding else 'HOLD'}",
            f"Provider idempotency-tag binding: {'PASS' if idempotency_binding else 'HOLD'}",
            f"Custom header readback: {header_state}",
            f"Exact provider readback: {'PASS' if exact_binding else 'HOLD'}",
            "",
            "This message is a transport validation. It does not manufacture production status for unrelated Penta systems.",
        ]
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="PentaMail validation-only institutional email runtime"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("--recipient", required=True)
    validate_cmd.add_argument("--from-identity", required=True)
    validate_cmd.add_argument("--subject", required=True)
    validate_cmd.add_argument("--body", required=True)
    validate_cmd.add_argument("--correlation-id", required=True)
    validate_cmd.add_argument("--authority-ref", required=True)
    args = parser.parse_args()
    envelope = build_envelope(
        origin_penta="penta.status",
        purpose="owner_execution_report",
        classification="internal",
        recipient=args.recipient,
        sender_identity=args.from_identity,
        subject=args.subject,
        body_text=args.body,
        correlation_id=args.correlation_id,
        authority_ref=args.authority_ref,
        authority_class="D1",
        priority="high",
        retention_classification="institutional_status",
    )
    print(json.dumps(envelope.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_cli())
    except PentaMailError as exc:
        print(json.dumps({"status": "HOLD_FAIL_CLOSED", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(78)
