"""Independent keyed verification for restricted cold repository snapshots."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any, Mapping

from .fabric import SHA256_RE, canonical_bytes


class ColdSnapshotVerifier:
    """Verify HMAC-sealed snapshots using a key held outside snapshot data."""

    def __init__(self, key: bytes):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("cold snapshot verification key must contain at least 32 bytes")
        self._key = key

    @classmethod
    def from_base64(cls, encoded: str) -> "ColdSnapshotVerifier":
        try:
            key = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            raise ValueError("cold snapshot verification key is not valid base64") from None
        return cls(key)

    @staticmethod
    def _signed_body(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        body = dict(snapshot)
        body.pop("snapshot_sha256", None)
        body.pop("signature", None)
        return body

    def signature(self, snapshot: Mapping[str, Any]) -> str:
        value = hmac.new(self._key, canonical_bytes(self._signed_body(snapshot)), hashlib.sha256).hexdigest()
        return "hmac-sha256:" + value

    def __call__(self, spec: Mapping[str, Any], snapshot: Mapping[str, Any]) -> bool:
        if snapshot.get("stable_id") != spec.get("stable_id"):
            return False
        claimed = snapshot.get("signature")
        if not isinstance(claimed, str) or not claimed.startswith("hmac-sha256:"):
            return False
        digest = claimed.removeprefix("hmac-sha256:")
        if not SHA256_RE.fullmatch(digest):
            return False
        return hmac.compare_digest(claimed, self.signature(snapshot))
