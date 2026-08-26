#!/usr/bin/env python3
"""Mailgun transport adapter for the governed PentaMail runtime.

The adapter is dependency-free and deliberately separates transport evidence:
- provider_accepted: Mailgun accepted/queued the message;
- recipient_server_accepted: Mailgun observed a delivered event;
- mailbox/inbox presence is outside this adapter and must be verified separately.

No credential value is persisted or emitted in evidence.
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request

from penta_mail import (
    AuthorizationContext,
    CommunicationEnvelope,
    EVIDENCE_SCHEMA,
    PentaMailError,
    _safe_text,
    now,
)


class MailgunAdapter:
    provider_id = "mailgun"

    SUCCESS_EVENTS = {"accepted", "delivered"}
    FAILURE_EVENTS = {"failed", "rejected", "complained", "unsubscribed"}

    def __init__(
        self,
        api_key: str | None = None,
        domain: str | None = None,
        *,
        base_url: str | None = None,
        timeout: int = 15,
        poll_attempts: int = 8,
        poll_interval: float = 1.5,
        opener=None,
        sleeper=None,
    ):
        self.api_key = (api_key or os.environ.get("MAILGUN_API_KEY") or "").strip()
        self.domain = (domain or os.environ.get("MAILGUN_DOMAIN") or "").strip().lower()
        self.base_url = (base_url or os.environ.get("MAILGUN_API_BASE_URL") or "https://api.mailgun.net").rstrip("/")
        self.timeout = int(timeout)
        self.poll_attempts = max(1, int(poll_attempts))
        self.poll_interval = max(0.0, float(poll_interval))
        self._opener = opener or urllib.request.urlopen
        self._sleeper = sleeper or time.sleep
        if not self.api_key:
            raise PentaMailError("MAILGUN_API_KEY is not bound")
        if not self.domain:
            raise PentaMailError("MAILGUN_DOMAIN is not bound")
        if any(ch in self.domain for ch in "/?#@ "):
            raise PentaMailError("MAILGUN_DOMAIN is invalid")
        if self.base_url not in {"https://api.mailgun.net", "https://api.eu.mailgun.net"}:
            raise PentaMailError("MAILGUN_API_BASE_URL must be an approved Mailgun API origin")

    def _auth_header(self) -> str:
        token = base64.b64encode(("api:" + self.api_key).encode("utf-8")).decode("ascii")
        return "Basic " + token

    @staticmethod
    def _multipart(fields: Mapping[str, str]) -> tuple[bytes, str]:
        boundary = "----CrownThrivePentaMailBoundary7MA4YWxkTrZu0gW"
        chunks: list[bytes] = []
        for name, value in fields.items():
            safe_name = str(name).replace('"', "")
            text = str(value)
            chunks.extend(
                [
                    ("--" + boundary + "\r\n").encode(),
                    (f'Content-Disposition: form-data; name="{safe_name}"\r\n\r\n').encode(),
                    text.encode("utf-8"),
                    b"\r\n",
                ]
            )
        chunks.append(("--" + boundary + "--\r\n").encode())
        return b"".join(chunks), "multipart/form-data; boundary=" + boundary

    def _request(
        self,
        method: str,
        path: str,
        *,
        form: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        url = self.base_url + path
        headers = {
            "Authorization": self._auth_header(),
            "User-Agent": "CrownThrive-PentaMail-Mailgun/1.0",
            "Accept": "application/json",
        }
        data = None
        if form is not None:
            data, content_type = self._multipart(form)
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read(1024 * 1024)
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(parsed, dict):
                    raise PentaMailError("mailgun response was not a JSON object")
                return int(response.status), parsed
        except urllib.error.HTTPError as exc:
            raw = exc.read(65536)
            detail = raw.decode("utf-8", errors="replace")[:1000] if raw else str(exc.reason)
            raise PentaMailError(f"mailgun HTTP {exc.code}: {detail}") from exc

    def domain_read(self) -> dict[str, Any]:
        domain_path = urllib.parse.quote(self.domain, safe=".-")
        status, payload = self._request("GET", "/v4/domains/" + domain_path)
        observed_name = str(payload.get("domain", {}).get("name") or payload.get("name") or "").lower()
        exact = observed_name == self.domain
        return {
            "schema": EVIDENCE_SCHEMA,
            "provider": self.provider_id,
            "operation": "domain_read",
            "result": "PASS" if status == 200 and exact else "FAIL",
            "readback": bool(status == 200 and exact),
            "http_status": status,
            "domain_match": exact,
            "observed_at": now(),
        }

    def send(self, envelope: CommunicationEnvelope, authorization: AuthorizationContext) -> dict[str, Any]:
        envelope.validate()
        authorization.validate_for(envelope)
        domain_path = urllib.parse.quote(self.domain, safe=".-")
        status, payload = self._request(
            "POST",
            f"/v3/{domain_path}/messages",
            form={
                "from": envelope.sender_identity,
                "to": envelope.recipient,
                "subject": envelope.subject,
                "text": envelope.body_text,
                "h:X-CrownThrive-Correlation-ID": envelope.correlation_id,
                "h:X-CrownThrive-Origin-Penta": envelope.origin_penta,
                "h:X-CrownThrive-Idempotency-Key": envelope.idempotency_key,
            },
        )
        message_id = payload.get("id")
        if status not in {200, 202} or not isinstance(message_id, str) or not message_id.strip():
            raise PentaMailError("mailgun did not return a stable message id")
        return {
            "provider": self.provider_id,
            "provider_message_id": message_id.strip(),
            "http_status": status,
            "accepted": True,
            "accepted_at": now(),
        }

    @staticmethod
    def _event_message_id(item: Mapping[str, Any]) -> str:
        message = item.get("message")
        if isinstance(message, Mapping):
            headers = message.get("headers")
            if isinstance(headers, Mapping):
                value = headers.get("message-id") or headers.get("message_id")
                if isinstance(value, str):
                    return value.strip()
            value = message.get("id")
            if isinstance(value, str):
                return value.strip()
        value = item.get("message-id") or item.get("message_id")
        return value.strip() if isinstance(value, str) else ""

    def readback(self, message_id: str) -> dict[str, Any]:
        wanted = _safe_text(message_id, "provider_message_id", max_length=512)
        query = urllib.parse.urlencode({"message-id": wanted, "limit": "25"})
        path = f"/v3/{urllib.parse.quote(self.domain, safe='.-')}/events?{query}"
        last_status = 0
        exact_item: Mapping[str, Any] | None = None
        provider_event = "not_observed"

        for attempt in range(self.poll_attempts):
            status, payload = self._request("GET", path)
            last_status = status
            items = payload.get("items") or []
            if not isinstance(items, list):
                items = []
            exact_candidates = [item for item in items if isinstance(item, Mapping) and self._event_message_id(item) == wanted]
            if exact_candidates:
                exact_item = exact_candidates[0]
                # Prefer a delivered event when the current page contains one.
                exact_item = next((item for item in exact_candidates if str(item.get("event") or "").lower() == "delivered"), exact_item)
                provider_event = str(exact_item.get("event") or "accepted").lower()
                if provider_event in self.SUCCESS_EVENTS | self.FAILURE_EVENTS:
                    break
            if attempt + 1 < self.poll_attempts and self.poll_interval:
                self._sleeper(self.poll_interval)

        exact = exact_item is not None
        success = exact and provider_event in self.SUCCESS_EVENTS
        normalized = {
            "accepted": "accepted",
            "delivered": "delivered",
            "failed": "failed",
            "rejected": "failed",
            "complained": "complained",
            "unsubscribed": "complained",
        }.get(provider_event, "deferred")
        return {
            "schema": EVIDENCE_SCHEMA,
            "provider": self.provider_id,
            "operation": "email_send",
            "result": "PASS" if last_status == 200 and success else "FAIL",
            "readback": bool(last_status == 200 and exact),
            "http_status": last_status,
            "provider_message_id": wanted,
            "provider_event": provider_event,
            "normalized_state": normalized,
            "provider_accepted": bool(success),
            "recipient_server_accepted": bool(exact and provider_event == "delivered"),
            "observed_at": now(),
        }
