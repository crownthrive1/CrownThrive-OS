"""PentaContext v1.1 internal runtime client.

Context is evidence/operational memory, never authority. This client never logs
credentials and only talks to the service-role-protected PentaContext Edge rail.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any, Iterable
from urllib import error, request

SYSTEM_KEY = "penta.context"
VERSION = "1.1.0"
VALID_CLASSIFICATIONS = {"public", "internal", "confidential", "restricted"}
VALID_SOURCE_TYPES = {"github", "drive", "database", "api", "web", "document", "message", "email", "calendar", "event", "system", "manual", "other"}
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]{12,}")
_NAMED_SECRET = re.compile(r"(?i)(api[_ -]?key|secret|token|password|private[_ -]?key)\s*[:=]\s*[A-Za-z0-9._~+/-]{12,}")
_PROVIDER_SECRET = re.compile(r"(?i)(sk-[A-Za-z0-9_-]{10,}|sb_secret_[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")

class PentaContextError(RuntimeError):
    pass

def redact_local(value: str) -> str:
    value = _EMAIL.sub("[redacted-email]", value)
    value = _SSN.sub("[redacted-ssn]", value)
    value = _BEARER.sub(r"\1[redacted-secret]", value)
    value = _PROVIDER_SECRET.sub("[redacted-secret]", value)
    return _NAMED_SECRET.sub("[redacted-secret]", value)

def normalize_scope(scope_key: str) -> str:
    value = scope_key.strip().lower()
    if not 2 <= len(value) <= 128:
        raise ValueError("scope_key must be 2..128 characters")
    return value

def normalize_tags(tags: Iterable[str] | None) -> list[str]:
    return sorted({str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()})

@dataclass(frozen=True)
class PentaContextConfig:
    supabase_url: str
    service_role_key: str
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "PentaContextConfig":
        url = os.getenv("SUPABASE_URL", "").rstrip("/")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise PentaContextError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return cls(url, key)

    @property
    def edge_url(self) -> str:
        return f"{self.supabase_url}/functions/v1/penta-context"

class PentaContextClient:
    def __init__(self, config: PentaContextConfig | None = None) -> None:
        self.config = config or PentaContextConfig.from_env()

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(self.config.edge_url, data=json.dumps(payload, separators=(",", ":")).encode(), method="POST", headers={"content-type": "application/json", "authorization": f"Bearer {self.config.service_role_key}", "user-agent": "penta-context-python/1.1.0"})
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1000]
            raise PentaContextError(f"PentaContext HTTP {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise PentaContextError("PentaContext transport unavailable") from exc
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise PentaContextError("PentaContext returned a non-object payload")
        return parsed

    def health(self) -> dict[str, Any]:
        return self._post({"action": "health"})

    def queue_status(self, scope_key: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"action": "queue_status"}
        if scope_key is not None:
            payload["scope_key"] = normalize_scope(scope_key)
        return self._post(payload)

    def query(self, scope_key: str, query: str = "", *, limit: int = 8, max_chars: int = 12000, tags: Iterable[str] | None = None, classification_ceiling: str = "internal", actor_ref: str = "penta.context.python") -> dict[str, Any]:
        ceiling = classification_ceiling.strip().lower()
        if ceiling not in VALID_CLASSIFICATIONS:
            raise ValueError("invalid classification ceiling")
        if not 1 <= int(limit) <= 50 or not 512 <= int(max_chars) <= 100000:
            raise ValueError("invalid query bounds")
        return self._post({"action":"query","scope_key":normalize_scope(scope_key),"query":query,"limit":int(limit),"max_chars":int(max_chars),"tags":normalize_tags(tags),"classification_ceiling":ceiling,"actor_ref":actor_ref})

    def _ingest_payload(self, scope_key: str, source_type: str, source_ref: str, content: str, *, title: str | None, summary: str | None, tags: Iterable[str] | None, metadata: dict[str, Any] | None, classification: str, importance: float, confidence: float, observed_at: str | None, expires_at: str | None, actor_ref: str) -> dict[str, Any]:
        source_type = source_type.strip().lower(); classification = classification.strip().lower()
        if source_type not in VALID_SOURCE_TYPES: raise ValueError("invalid source_type")
        if classification not in VALID_CLASSIFICATIONS: raise ValueError("invalid classification")
        if not content.strip() or len(content) > 500000: raise ValueError("content must be 1..500000 characters")
        if not 0 <= importance <= 1 or not 0 <= confidence <= 1: raise ValueError("importance/confidence must be between 0 and 1")
        payload: dict[str, Any] = {"scope_key":normalize_scope(scope_key),"source_type":source_type,"source_ref":source_ref.strip(),"content":redact_local(content),"title":redact_local(title) if title else None,"summary":redact_local(summary) if summary else None,"tags":normalize_tags(tags),"metadata":metadata or {},"classification":classification,"importance":importance,"confidence":confidence,"actor_ref":actor_ref}
        if observed_at is not None: payload["observed_at"] = observed_at
        if expires_at is not None: payload["expires_at"] = expires_at
        return payload

    def ingest(self, scope_key: str, source_type: str, source_ref: str, content: str, *, title: str | None = None, summary: str | None = None, tags: Iterable[str] | None = None, metadata: dict[str, Any] | None = None, classification: str = "internal", importance: float = 0.5, confidence: float = 0.7, observed_at: str | None = None, expires_at: str | None = None, actor_ref: str = "penta.context.python") -> dict[str, Any]:
        payload = self._ingest_payload(scope_key,source_type,source_ref,content,title=title,summary=summary,tags=tags,metadata=metadata,classification=classification,importance=importance,confidence=confidence,observed_at=observed_at,expires_at=expires_at,actor_ref=actor_ref)
        return self._post({"action":"ingest",**payload})

    def enqueue(self, scope_key: str, source_type: str, source_ref: str, content: str, *, title: str | None = None, summary: str | None = None, tags: Iterable[str] | None = None, metadata: dict[str, Any] | None = None, classification: str = "internal", importance: float = 0.5, confidence: float = 0.7, observed_at: str | None = None, expires_at: str | None = None, actor_ref: str = "penta.context.python", priority: int = 50, idempotency_key: str | None = None) -> dict[str, Any]:
        if not 0 <= int(priority) <= 100: raise ValueError("priority must be 0..100")
        payload = self._ingest_payload(scope_key,source_type,source_ref,content,title=title,summary=summary,tags=tags,metadata=metadata,classification=classification,importance=importance,confidence=confidence,observed_at=observed_at,expires_at=expires_at,actor_ref=actor_ref)
        payload.update({"action":"enqueue","priority":int(priority)})
        if idempotency_key: payload["idempotency_key"] = idempotency_key
        return self._post(payload)
