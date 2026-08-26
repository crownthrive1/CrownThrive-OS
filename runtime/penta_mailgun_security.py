#!/usr/bin/env python3
"""Mailgun webhook authenticity verification for CrownThrive PentaMailer.

The webhook signing key is never embedded in this module. Runtime resolution is
through MAILGUN_WEBHOOK_SIGNING_KEY, with the corresponding PentaCredentials
Vault alias recorded as metadata only.
"""
from __future__ import annotations

import dataclasses
import hashlib
import hmac
import os
import time
from typing import Any, Mapping, MutableMapping

ENV_ALIAS = "MAILGUN_WEBHOOK_SIGNING_KEY"
VAULT_ALIAS = "ct.pentamailer.mailgun.webhook_signing_key"
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60
DEFAULT_FUTURE_SKEW_SECONDS = 5 * 60


class MailgunWebhookError(ValueError):
    """Fail-closed Mailgun webhook verification error."""


@dataclasses.dataclass(frozen=True)
class WebhookVerification:
    provider: str
    operation: str
    result: str
    verified: bool
    signature_source: str
    timestamp: int
    token_fingerprint: str
    replay_checked: bool
    freshness_checked: bool

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class TokenReplayCache:
    """Minimal replay cache contract.

    Production receivers may replace the supplied mutable mapping with a durable
    TTL store. Raw Mailgun tokens are hashed before they are used as cache keys.
    """

    def __init__(self, storage: MutableMapping[str, int] | None = None, ttl_seconds: int = DEFAULT_MAX_AGE_SECONDS):
        self.storage = storage if storage is not None else {}
        self.ttl_seconds = int(ttl_seconds)
        if self.ttl_seconds <= 0:
            raise MailgunWebhookError("replay cache ttl must be positive")

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def check_and_record(self, token: str, now_epoch: int) -> None:
        expired = [key for key, expires_at in self.storage.items() if int(expires_at) < now_epoch]
        for key in expired:
            self.storage.pop(key, None)

        cache_key = self._key(token)
        expires_at = self.storage.get(cache_key)
        if expires_at is not None and int(expires_at) >= now_epoch:
            raise MailgunWebhookError("replayed Mailgun webhook token")
        self.storage[cache_key] = now_epoch + self.ttl_seconds


def resolve_signing_key(explicit: str | None = None) -> str:
    value = (explicit or os.environ.get(ENV_ALIAS) or "").strip()
    if not value:
        raise MailgunWebhookError(f"{ENV_ALIAS} is not bound")
    if len(value) < 16:
        raise MailgunWebhookError("Mailgun webhook signing key is unexpectedly short")
    return value


def _required_text(payload: Mapping[str, Any], field: str, *, max_length: int) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise MailgunWebhookError(f"invalid Mailgun webhook {field}")
    return value


def _parse_timestamp(payload: Mapping[str, Any]) -> int:
    raw = payload.get("timestamp")
    if isinstance(raw, bool):
        raise MailgunWebhookError("invalid Mailgun webhook timestamp")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise MailgunWebhookError("invalid Mailgun webhook timestamp") from exc
    if value <= 0:
        raise MailgunWebhookError("invalid Mailgun webhook timestamp")
    return value


class MailgunWebhookVerifier:
    """Verify Mailgun webhook signatures using the provider's HMAC-SHA256 contract."""

    def __init__(
        self,
        signing_key: str | None = None,
        *,
        max_age_seconds: int | None = DEFAULT_MAX_AGE_SECONDS,
        future_skew_seconds: int = DEFAULT_FUTURE_SKEW_SECONDS,
        accept_parent_signature: bool = True,
    ):
        self._signing_key = resolve_signing_key(signing_key)
        self.max_age_seconds = None if max_age_seconds is None else int(max_age_seconds)
        self.future_skew_seconds = int(future_skew_seconds)
        self.accept_parent_signature = bool(accept_parent_signature)
        if self.max_age_seconds is not None and self.max_age_seconds <= 0:
            raise MailgunWebhookError("max_age_seconds must be positive or None")
        if self.future_skew_seconds < 0:
            raise MailgunWebhookError("future_skew_seconds must be non-negative")

    def _signature(self, payload: Mapping[str, Any]) -> tuple[str, str]:
        if self.accept_parent_signature:
            parent = payload.get("parent-signature")
            if isinstance(parent, str) and parent:
                return parent, "parent-signature"
        return _required_text(payload, "signature", max_length=256), "signature"

    def verify(
        self,
        payload: Mapping[str, Any],
        *,
        received_at: int | None = None,
        replay_cache: TokenReplayCache | None = None,
    ) -> WebhookVerification:
        if not isinstance(payload, Mapping):
            raise MailgunWebhookError("Mailgun webhook signature payload must be a mapping")

        token = _required_text(payload, "token", max_length=512)
        timestamp = _parse_timestamp(payload)
        supplied_signature, signature_source = self._signature(payload)
        if len(supplied_signature) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in supplied_signature):
            raise MailgunWebhookError("invalid Mailgun webhook signature encoding")

        now_epoch = int(time.time() if received_at is None else received_at)
        freshness_checked = self.max_age_seconds is not None
        if timestamp > now_epoch + self.future_skew_seconds:
            raise MailgunWebhookError("Mailgun webhook timestamp is too far in the future")
        if self.max_age_seconds is not None and now_epoch - timestamp > self.max_age_seconds:
            raise MailgunWebhookError("stale Mailgun webhook timestamp")

        signed_material = f"{timestamp}{token}".encode("utf-8")
        expected = hmac.new(self._signing_key.encode("utf-8"), signed_material, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied_signature.lower()):
            raise MailgunWebhookError("Mailgun webhook signature mismatch")

        replay_checked = replay_cache is not None
        if replay_cache is not None:
            replay_cache.check_and_record(token, now_epoch)

        return WebhookVerification(
            provider="mailgun",
            operation="webhook_verify",
            result="PASS",
            verified=True,
            signature_source=signature_source,
            timestamp=timestamp,
            token_fingerprint="sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:16],
            replay_checked=replay_checked,
            freshness_checked=freshness_checked,
        )


def verify_mailgun_webhook(
    signature_payload: Mapping[str, Any],
    *,
    signing_key: str | None = None,
    received_at: int | None = None,
    replay_cache: TokenReplayCache | None = None,
    max_age_seconds: int | None = DEFAULT_MAX_AGE_SECONDS,
    future_skew_seconds: int = DEFAULT_FUTURE_SKEW_SECONDS,
    accept_parent_signature: bool = True,
) -> dict[str, Any]:
    verifier = MailgunWebhookVerifier(
        signing_key,
        max_age_seconds=max_age_seconds,
        future_skew_seconds=future_skew_seconds,
        accept_parent_signature=accept_parent_signature,
    )
    return verifier.verify(
        signature_payload,
        received_at=received_at,
        replay_cache=replay_cache,
    ).as_dict()
