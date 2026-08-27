"""Deterministic Mailgun probation containment policy reference.

This module is deliberately provider-I/O free.  It classifies an authenticated
Mailgun disablement notice, computes durable policy windows, reconciles
idempotent incidents, and decides the size of a controlled release batch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from threading import RLock
from typing import Iterable, Literal


QUEUE_HOLD = timedelta(hours=3)
TRIGGER_PROBATION = timedelta(hours=72)
ROLLING_WINDOW = timedelta(hours=1)
ROLLING_HOURLY_LIMIT = 10
CONTROLLED_BATCH_LIMIT = 2


class SignalRejected(ValueError):
    """The input is not an authenticated, exact Mailgun probation signal."""


class DuplicateIncidentConflict(ValueError):
    """A provider event id was reused for a different canonical incident."""


_PROBATION = re.compile(r"\byour\s+account\s+is\s+on\s+probation\b", re.IGNORECASE)
_HOURLY_LIMIT = re.compile(
    r"\bdomains?\s+are\s+limited\s+to\s+(?P<limit>\d+)\s+messages?\s*/\s*hour\b",
    re.IGNORECASE,
)
_TEMPORARILY_DISABLED = re.compile(
    r"\baccount\s+has\s+been\s+temporarily\s+disabled\b", re.IGNORECASE
)
_ENABLED_IN = re.compile(
    r"\baccount\s+will\s+be\s+enabled\s+in\s+(?P<seconds>\d+)\s+seconds?\b",
    re.IGNORECASE,
)


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _nonempty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class NoticeClassification:
    kind: Literal["mailgun_account_probation_temporarily_disabled"]
    hourly_limit: int
    provider_enable_seconds: int


def classify_notice(
    message: str,
    *,
    authenticated: bool,
    source: str,
) -> NoticeClassification:
    """Classify only the complete authenticated Mailgun probation notice.

    Authentication is an input from the provider adapter (for example, a
    verified webhook signature or an authenticated provider response).  Text
    that merely looks like Mailgun is never treated as authenticated.
    """

    if authenticated is not True or source.strip().lower() != "mailgun":
        raise SignalRejected("mailgun source authentication is required")
    if not isinstance(message, str):
        raise SignalRejected("notice must be text")

    hourly = _HOURLY_LIMIT.search(message)
    enabled = _ENABLED_IN.search(message)
    if not (_PROBATION.search(message) and hourly and _TEMPORARILY_DISABLED.search(message) and enabled):
        raise SignalRejected("notice is not the complete Mailgun probation disablement signal")

    hourly_limit = int(hourly.group("limit"))
    provider_enable_seconds = int(enabled.group("seconds"))
    if hourly_limit != 100:
        raise SignalRejected("notice is not the accepted 100-message hourly probation signal")
    if provider_enable_seconds <= 0 or provider_enable_seconds > 86400:
        raise SignalRejected("provider enable estimate must be between 1 and 86400 seconds")
    return NoticeClassification(
        kind="mailgun_account_probation_temporarily_disabled",
        hourly_limit=hourly_limit,
        provider_enable_seconds=provider_enable_seconds,
    )


@dataclass(frozen=True)
class ProbationIncident:
    provider_event_id: str
    account_ref: str
    domain_ref: str
    trigger_ref: str
    received_at: datetime
    hourly_limit: int
    provider_enable_seconds: int
    provider_enable_estimate: datetime
    hold_until: datetime
    probation_until: datetime
    canonical_sha256: str

    @property
    def scope(self) -> tuple[str, str, str]:
        return (self.account_ref, self.domain_ref, self.trigger_ref)


def build_incident(
    classification: NoticeClassification,
    *,
    provider_event_id: str,
    account_ref: str,
    domain_ref: str,
    trigger_ref: str,
    received_at: datetime,
) -> ProbationIncident:
    received_at = _utc(received_at, "received_at")
    provider_event_id = _nonempty(provider_event_id, "provider_event_id")
    account_ref = _nonempty(account_ref, "account_ref")
    domain_ref = _nonempty(domain_ref, "domain_ref")
    trigger_ref = _nonempty(trigger_ref, "trigger_ref")

    if classification.hourly_limit <= 0 or classification.provider_enable_seconds <= 0:
        raise ValueError("classification limits must be positive")
    provider_enable_estimate = received_at + timedelta(
        seconds=classification.provider_enable_seconds
    )
    hold_until = max(received_at + QUEUE_HOLD, provider_enable_estimate)
    probation_until = received_at + TRIGGER_PROBATION
    canonical = {
        "account_ref": account_ref,
        "domain_ref": domain_ref,
        "hourly_limit": classification.hourly_limit,
        "kind": classification.kind,
        "provider_enable_seconds": classification.provider_enable_seconds,
        "provider_event_id": provider_event_id,
        "received_at": received_at.isoformat(),
        "trigger_ref": trigger_ref,
    }
    digest = sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ProbationIncident(
        provider_event_id=provider_event_id,
        account_ref=account_ref,
        domain_ref=domain_ref,
        trigger_ref=trigger_ref,
        received_at=received_at,
        hourly_limit=classification.hourly_limit,
        provider_enable_seconds=classification.provider_enable_seconds,
        provider_enable_estimate=provider_enable_estimate,
        hold_until=hold_until,
        probation_until=probation_until,
        canonical_sha256=digest,
    )


@dataclass(frozen=True)
class ProbationState:
    account_ref: str
    domain_ref: str
    trigger_ref: str
    opened_at: datetime
    hold_until: datetime
    probation_started_at: datetime | None
    probation_until: datetime
    incident_ids: tuple[str, ...]

    @property
    def scope(self) -> tuple[str, str, str]:
        return (self.account_ref, self.domain_ref, self.trigger_ref)


@dataclass(frozen=True)
class Acceptance:
    result: Literal["accepted", "idempotent_replay"]
    state: ProbationState


class IncidentRegistry:
    """In-memory reference for the required durable atomic reconciliation."""

    def __init__(self) -> None:
        self._events: dict[str, tuple[str, tuple[str, str, str]]] = {}
        self._routes: dict[
            tuple[str, str], tuple[datetime, datetime, tuple[str, ...]]
        ] = {}
        self._triggers: dict[tuple[str, str, str], tuple[datetime, datetime]] = {}
        self._lock = RLock()

    def _state_for_scope(self, scope: tuple[str, str, str]) -> ProbationState | None:
        account_ref, domain_ref, trigger_ref = scope
        route = self._routes.get((account_ref, domain_ref))
        if route is None:
            return None
        opened_at, hold_until, incident_ids = route
        trigger = self._triggers.get(scope)
        probation_started_at, probation_until = (
            trigger if trigger is not None else (None, opened_at)
        )
        return ProbationState(
            account_ref=account_ref,
            domain_ref=domain_ref,
            trigger_ref=trigger_ref,
            opened_at=opened_at,
            hold_until=hold_until,
            probation_started_at=probation_started_at,
            probation_until=probation_until,
            incident_ids=incident_ids,
        )

    def accept(self, incident: ProbationIncident) -> Acceptance:
        with self._lock:
            existing_event = self._events.get(incident.provider_event_id)
            if existing_event is not None:
                existing_digest, existing_scope = existing_event
                if existing_digest != incident.canonical_sha256 or existing_scope != incident.scope:
                    raise DuplicateIncidentConflict(
                        "provider_event_id is already bound to another canonical incident"
                    )
                state = self._state_for_scope(existing_scope)
                if state is None:  # pragma: no cover - protected by the registry invariant
                    raise RuntimeError("incident event exists without route state")
                return Acceptance("idempotent_replay", state)

            route_scope = (incident.account_ref, incident.domain_ref)
            current_route = self._routes.get(route_scope)
            if current_route is None:
                route = (
                    incident.received_at,
                    incident.hold_until,
                    (incident.provider_event_id,),
                )
            else:
                opened_at, hold_until, incident_ids = current_route
                route = (
                    min(opened_at, incident.received_at),
                    max(hold_until, incident.hold_until),
                    incident_ids + (incident.provider_event_id,),
                )
            current_trigger = self._triggers.get(incident.scope)
            self._routes[route_scope] = route
            self._triggers[incident.scope] = (
                incident.received_at
                if current_trigger is None
                else min(current_trigger[0], incident.received_at),
                incident.probation_until
                if current_trigger is None
                else max(current_trigger[1], incident.probation_until),
            )
            self._events[incident.provider_event_id] = (
                incident.canonical_sha256,
                incident.scope,
            )
            state = self._state_for_scope(incident.scope)
            if state is None:  # pragma: no cover - protected by assignments above
                raise RuntimeError("accepted incident did not produce route state")
            return Acceptance("accepted", state)

    def state_for(self, account_ref: str, domain_ref: str, trigger_ref: str) -> ProbationState | None:
        return self._state_for_scope((account_ref, domain_ref, trigger_ref))


def queue_hold_active(state: ProbationState, now: datetime) -> bool:
    now = _utc(now, "now")
    return state.opened_at <= now < state.hold_until


def trigger_probation_active(state: ProbationState, now: datetime) -> bool:
    now = _utc(now, "now")
    return (
        state.probation_started_at is not None
        and state.probation_started_at <= now < state.probation_until
    )


@dataclass(frozen=True)
class ProviderReadback:
    account_ref: str
    domain_ref: str
    enabled: bool
    observed_at: datetime


@dataclass(frozen=True)
class ReleaseDecision:
    allowed_count: int
    reason: Literal[
        "queue_hold_active",
        "trigger_probation_active",
        "provider_enabled_readback_required",
        "provider_readback_scope_mismatch",
        "provider_readback_stale",
        "rolling_hourly_limit_reached",
        "no_pending_messages",
        "controlled_release",
    ]
    rolling_used: int
    rolling_remaining: int


def controlled_release(
    state: ProbationState,
    *,
    now: datetime,
    provider_readback: ProviderReadback | None,
    pending_count: int,
    sent_at: Iterable[datetime],
) -> ReleaseDecision:
    """Return a bounded release count; never perform provider I/O.

    The rolling window is ``(now - 1 hour, now]``.  A send exactly one hour
    old has left the window, matching the exact reset boundary.
    """

    now = _utc(now, "now")
    if not isinstance(pending_count, int) or isinstance(pending_count, bool) or pending_count < 0:
        raise ValueError("pending_count must be a non-negative integer")

    normalized_sent = [_utc(value, "sent_at") for value in sent_at]
    if any(value > now for value in normalized_sent):
        raise ValueError("sent_at cannot be in the future")
    cutoff = now - ROLLING_WINDOW
    rolling_used = sum(cutoff < value <= now for value in normalized_sent)
    rolling_remaining = max(0, ROLLING_HOURLY_LIMIT - rolling_used)

    def decision(reason: ReleaseDecision.__annotations__["reason"]) -> ReleaseDecision:
        return ReleaseDecision(0, reason, rolling_used, rolling_remaining)

    if queue_hold_active(state, now):
        return decision("queue_hold_active")
    if trigger_probation_active(state, now):
        return decision("trigger_probation_active")
    if provider_readback is None or provider_readback.enabled is not True:
        return decision("provider_enabled_readback_required")
    if (
        provider_readback.account_ref != state.account_ref
        or provider_readback.domain_ref != state.domain_ref
    ):
        return decision("provider_readback_scope_mismatch")
    observed_at = _utc(provider_readback.observed_at, "provider_readback.observed_at")
    if observed_at < state.hold_until or observed_at > now:
        return decision("provider_readback_stale")
    if rolling_remaining == 0:
        return decision("rolling_hourly_limit_reached")
    if pending_count == 0:
        return decision("no_pending_messages")

    return ReleaseDecision(
        allowed_count=min(CONTROLLED_BATCH_LIMIT, pending_count, rolling_remaining),
        reason="controlled_release",
        rolling_used=rolling_used,
        rolling_remaining=rolling_remaining,
    )
