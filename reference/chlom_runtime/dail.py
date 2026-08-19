from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .model import canonical_json


class DAILLedger:
    """Append-only in-memory DAIL hash chain for reference-runtime tests."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(event) for event in self._events)

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        sequence = len(self._events) + 1
        previous_hash = self._events[-1]["event_hash"] if self._events else "GENESIS"
        core = {
            "event_id": f"ct.event.ref.{sequence:08d}",
            "sequence": sequence,
            "event_type": event_type,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "previous_hash": previous_hash,
            "payload": payload,
        }
        event_hash = hashlib.sha256(canonical_json(core).encode("utf-8")).hexdigest()
        event = {**core, "event_hash": event_hash}
        self._events.append(event)
        return dict(event)

    def verify(self) -> bool:
        previous_hash = "GENESIS"
        for event in self._events:
            if event.get("previous_hash") != previous_hash:
                return False
            core = {key: value for key, value in event.items() if key != "event_hash"}
            expected = hashlib.sha256(canonical_json(core).encode("utf-8")).hexdigest()
            if event.get("event_hash") != expected:
                return False
            previous_hash = expected
        return True
