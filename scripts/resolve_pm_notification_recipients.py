#!/usr/bin/env python3
"""Resolve CrownThrive material-pass Gmail recipient references.

Public repository policy intentionally stores logical recipient references rather
than the private Collab Portal inbound tracking address. Runtime automation
resolves those references in its authorized mail context.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/pm-notification-routing.v1.json"

REQUIRED_STATE = {
    "credential_exact_match": "passed",
    "project_meta_authenticated": "passed",
    "institutional_project_uid": "pinned",
    "approved_field_map": "approved",
    "authenticated_project_read": "passed",
    "bounded_write_readback": "passed",
    "webhook_sender_delivery_integrity": "passed",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def operational_verified(state: dict[str, Any]) -> bool:
    return all(state.get(key) == expected for key, expected in REQUIRED_STATE.items())


def resolve(manifest: dict[str, Any], state: dict[str, Any] | None) -> dict[str, Any]:
    refs = [
        ref for ref, item in manifest["recipient_policy"].items()
        if item.get("active") is True
    ]
    verified = bool(state and operational_verified(state))
    if verified:
        refs = list(manifest["collab_portal_fallback"]["after_disable_recipient_refs"])
    return {
        "transport": "gmail",
        "collab_portal_operational_verified": verified,
        "collab_tracking_fallback": "disabled" if verified else "active",
        "recipient_refs": refs,
        "reason": "all_certification_gates_passed" if verified else "collab_adapter_not_fully_certified_or_state_not_provided",
        "privacy": "resolve_addresses_only_inside_authorized_runtime; do_not_log",
    }


def self_test(manifest: dict[str, Any]) -> None:
    unverified = resolve(manifest, {"credential_exact_match": "passed"})
    assert unverified["recipient_refs"] == [
        "founder_tracking", "institutional_tracking", "collab_portal_fallback_tracking"
    ]
    verified = resolve(manifest, dict(REQUIRED_STATE))
    assert verified["recipient_refs"] == ["founder_tracking", "institutional_tracking"]
    assert verified["collab_tracking_fallback"] == "disabled"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collab-state-json", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    manifest = read_json(MANIFEST)
    if args.self_test:
        self_test(manifest)
        print("PM routing self-test passed: private Collab tracking ref stays active until all gates pass.")
        return 0
    state = read_json(args.collab_state_json) if args.collab_state_json else None
    print(json.dumps(resolve(manifest, state), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
