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
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping
import urllib.error
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
EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{8,}"
)


class PentaMailError(ValueError):
    """Fail-closed PentaMail validation/transport error."""


def now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _safe_text(value: str, field: str, *, max_length: int = 10000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PentaMailError(f"{field} must be a non-empty string")
    if "\r" in value or "\x00" in value:
        raise PentaMailError(f"{field} contains unsafe control characters")
    if len(value) > max_length:
        raise PentaMailError(f"{field} exceeds maximum length")
    return value.strip()


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
            _safe_text(value, field, max_length=256)
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

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
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
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(1024 * 1024)
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
                return int(response.status), parsed
        except urllib.error.HTTPError as exc:
            raw = exc.read(65536)
            detail = raw.decode("utf-8", errors="replace")[:1000] if raw else str(exc.reason)
            raise PentaMailError(f"resend HTTP {exc.code}: {detail}") from exc

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
                    "X-CrownThrive-Correlation-ID": envelope.correlation_id,
                    "X-CrownThrive-Origin-Penta": envelope.origin_penta,
                    "X-CrownThrive-Idempotency-Key": envelope.idempotency_key,
                },
            },
        )
        message_id = payload.get("id")
        if status not in {200, 201} or not isinstance(message_id, str) or not message_id:
            raise PentaMailError("provider did not return a stable message id")
        return {
            "provider": self.provider_id,
            "provider_message_id": message_id,
            "http_status": status,
            "accepted": True,
            "accepted_at": now(),
        }

    def readback(self, message_id: str) -> dict[str, Any]:
        _safe_text(message_id, "provider_message_id", max_length=256)
        status, payload = self._request("GET", "/emails/" + message_id)
        same_id = payload.get("id") == message_id
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
        return {
            "schema": EVIDENCE_SCHEMA,
            "provider": self.provider_id,
            "operation": "email_send",
            "result": "PASS" if status == 200 and same_id else "FAIL",
            "readback": bool(status == 200 and same_id),
            "http_status": status,
            "provider_message_id": message_id,
            "provider_event": provider_event,
            "normalized_state": normalized,
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
        return {**prior, "idempotent_replay": True}

    adapter = adapter or ResendAdapter()
    domain_evidence = adapter.domain_read()
    if domain_evidence.get("result") != "PASS" or domain_evidence.get("readback") is not True:
        raise PentaMailError("provider read-only certification did not pass")
    ledger.append(envelope, "authorized", {"authority_ref": authorization.authority_ref})
    ledger.append(envelope, "queued", {"provider": adapter.provider_id})
    accepted = adapter.send(envelope, authorization)
    ledger.append(envelope, "accepted", {"provider": adapter.provider_id, "provider_message_id": accepted["provider_message_id"]})
    readback = adapter.readback(accepted["provider_message_id"])
    if readback.get("result") != "PASS" or readback.get("readback") is not True:
        raise PentaMailError("email_send exact readback failed")
    ledger.append(envelope, readback["normalized_state"], readback)
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
        },
        "live_evidence": [domain_evidence, readback],
        "idempotent_replay": False,
        "recorded_at": now(),
    }
    ledger.remember_receipt(envelope, receipt)
    return receipt


def owner_report(receipt: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "Penta Runtime Suite execution report",
            "",
            f"Correlation: {receipt.get('correlation_id')}",
            f"PentaMail provider: {receipt.get('provider')}",
            f"Provider message ID: {receipt.get('provider_message_id')}",
            f"Lifecycle state at readback: {receipt.get('lifecycle_state')}",
            "Exact provider readback: PASS",
            "",
            "This message is a transport validation. It does not manufacture production status for unrelated Penta systems.",
        ]
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="PentaMail governed institutional email runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    validate_cmd = sub.add_parser("validate")
    live = sub.add_parser("live-certify-send")
    for cmd in (validate_cmd, live):
        cmd.add_argument("--recipient", required=True)
        cmd.add_argument("--from-identity", required=True)
        cmd.add_argument("--subject", required=True)
        cmd.add_argument("--body", required=True)
        cmd.add_argument("--correlation-id", required=True)
        cmd.add_argument("--authority-ref", required=True)
        cmd.add_argument("--authorized-by", required=True)
        cmd.add_argument("--state", default=".penta/pentamail")
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
    if args.command == "validate":
        print(json.dumps(envelope.as_dict(), indent=2, sort_keys=True))
        return 0
    auth = AuthorizationContext(
        authorized=True,
        authorized_by=args.authorized_by,
        authority_ref=args.authority_ref,
        authority_class="D1",
    )
    receipt = certification_send(envelope=envelope, authorization=auth, state_dir=Path(args.state))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_cli())
    except PentaMailError as exc:
        print(json.dumps({"status": "HOLD_FAIL_CLOSED", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(78)
