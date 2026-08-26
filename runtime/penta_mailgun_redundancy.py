#!/usr/bin/env python3
"""PentaMailer Mailgun redundancy selector.

Secret values are never stored in repository state. Deployment/runtime must inject
one or both credential lanes from PentaCredentials/ThriveBase Vault.
"""
from __future__ import annotations

import dataclasses
import hashlib
import os
from typing import Iterable

PRIMARY_ENV = "MAILGUN_API_KEY_PRIMARY"
SECONDARY_ENV = "MAILGUN_API_KEY_SECONDARY"
LEGACY_ENV = "MAILGUN_API_KEY"
DOMAIN_ENV = "MAILGUN_DOMAIN"


@dataclasses.dataclass(frozen=True)
class MailgunLane:
    lane: str
    env_name: str
    fingerprint: str


def _fingerprint(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def available_lanes() -> list[MailgunLane]:
    lanes: list[MailgunLane] = []
    for lane, env_name in (
        ("primary", PRIMARY_ENV),
        ("secondary", SECONDARY_ENV),
        ("legacy", LEGACY_ENV),
    ):
        value = os.environ.get(env_name, "").strip()
        if value:
            lanes.append(MailgunLane(lane=lane, env_name=env_name, fingerprint=_fingerprint(value)))
    return lanes


def select_lane(exclude: Iterable[str] = ()) -> MailgunLane:
    excluded = set(exclude)
    for candidate in available_lanes():
        if candidate.lane not in excluded:
            return candidate
    raise RuntimeError("HOLD_UNBOUND: no Mailgun credential lane available")


def resolve_api_key(lane: MailgunLane) -> str:
    value = os.environ.get(lane.env_name, "").strip()
    if not value:
        raise RuntimeError(f"HOLD_UNBOUND: credential lane {lane.lane} disappeared")
    return value


def require_domain() -> str:
    domain = os.environ.get(DOMAIN_ENV, "").strip()
    if not domain:
        raise RuntimeError("HOLD_UNBOUND: MAILGUN_DOMAIN missing")
    return domain


def failover_order() -> list[str]:
    return [lane.lane for lane in available_lanes()]


def certification_snapshot() -> dict[str, object]:
    lanes = available_lanes()
    return {
        "schema": "ct.pentamailer.mailgun-redundancy.v1",
        "provider": "mailgun",
        "domain_bound": bool(os.environ.get(DOMAIN_ENV, "").strip()),
        "lane_count": len(lanes),
        "lanes": [dataclasses.asdict(lane) for lane in lanes],
        "redundancy_ready": len([lane for lane in lanes if lane.lane in {"primary", "secondary"}]) >= 2,
        "secret_values_persisted": False,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(certification_snapshot(), indent=2, sort_keys=True))
