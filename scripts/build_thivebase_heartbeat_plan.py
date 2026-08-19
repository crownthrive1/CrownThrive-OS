#!/usr/bin/env python3
"""Render the sanitized THIVEBASE monthly heartbeat execution plan.

This script performs no provider calls and reads no credentials. It converts the
machine policy into a deterministic plan that agents can execute through their
connected, governed tools.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/thivebase-operational-automation.v1.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    heartbeat = data["heartbeat"]
    targets = sorted(data["service_targets"], key=lambda row: row["service_id"])

    plan = {
        "manifest_id": data["manifest_id"],
        "phase": data["phase"],
        "first_database_activity": heartbeat["required_first_database_call"],
        "required_project_health": heartbeat["required_project_health"],
        "unknown_metric_policy": heartbeat["unknown_metric_policy"],
        "default_probe_mode": heartbeat["default_probe_mode"],
        "checks": heartbeat["checks"],
        "targets": [
            {
                "service_id": row["service_id"],
                "probe": row["probe"],
                "writes_enabled": row["writes_enabled_by_heartbeat"],
            }
            for row in targets
        ],
        "capacity_thresholds_percent": heartbeat["capacity_thresholds_percent"],
        "reward_loyalty": {
            "current_install": data["reward_loyalty_boundary"]["current_crownthrive_install"],
            "target_version": data["reward_loyalty_boundary"]["vendor_target_version"],
            "production_v5_deployed": data["reward_loyalty_boundary"]["production_v5_deployed"],
        },
        "collab_portal": {
            "event_driven_sync_enabled": data["collab_portal_webhook_boundary"]["event_driven_sync_enabled"],
            "live_provider_delivery_certified": data["collab_portal_webhook_boundary"]["live_provider_delivery_certified"],
            "remaining_gate": data["collab_portal_webhook_boundary"]["remaining_gate"],
        },
    }

    if args.as_json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(f"THIVEBASE monthly heartbeat — Phase {plan['phase']}")
        print(f"1. Database activity: {plan['first_database_activity']}")
        print(f"2. Require project state: {plan['required_project_health']}")
        print(f"3. Preserve unavailable values as: {plan['unknown_metric_policy']}")
        print("4. Run registered read-only checks:")
        for target in plan["targets"]:
            print(f"   - {target['service_id']}: {target['probe']} (writes={target['writes_enabled']})")
        print("5. Reconcile gates, evidence, #98/#99/#100 and Mintlify; never manufacture a pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
