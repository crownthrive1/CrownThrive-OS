#!/usr/bin/env python3
"""Fail-closed PentaBooks recurrence guard.

A run of this guard proves only that the guard executed and observed its declared
configuration. It never treats secret presence, a workflow badge, a Drive ID,
or a registry row as proof of provider mutation or public release.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path


def _present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _canonical_sha256(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="pentabooks-cycle-evidence.json")
    args = parser.parse_args()

    expected = int(os.getenv("PENTABOOKS_EXPECTED_SKUS", "0"))
    rotation = os.getenv("PENTABOOKS_ROTATION_ID", "UNSET")
    mode = os.getenv("PENTABOOKS_MODE", "primary")
    bindings = {
        "drive_credentials": _present("PENTABOOKS_DRIVE_CREDENTIALS_JSON"),
        "thrivebase_url": _present("PENTABOOKS_THRIVEBASE_URL"),
        "thrivebase_service_role": _present("PENTABOOKS_THRIVEBASE_SERVICE_ROLE_KEY"),
        "alert_webhook": _present("PENTABOOKS_ALERT_WEBHOOK"),
    }

    event = {
        "schema": "ct.pentabooks.recurrence-cycle-evidence.v1",
        "rotation_id": rotation,
        "mode": mode,
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "expected_skus": expected,
        "provider_bindings": bindings,
        "drive_root_id": os.getenv("PENTABOOKS_DRIVE_ROOT_ID", ""),
        "drive_product_lane_id": os.getenv("PENTABOOKS_DRIVE_PRODUCT_LANE_ID", ""),
        "control_zip_sha256": os.getenv("PENTABOOKS_CONTROL_ZIP_SHA256", ""),
        "custody_status": "PROVIDER_READBACK_NOT_IMPLEMENTED_IN_GUARD",
        "product_payload_status": "RECOVERY_REQUIRED" if expected else "UNDECLARED",
        "truth_boundary": (
            "Workflow execution proves only that the deterministic guard ran. "
            "It does not prove provider upload, database mutation, public release, "
            "sales, or entitlement delivery."
        ),
    }
    event["event_sha256"] = _canonical_sha256(event)
    Path(args.output).write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "rotation_id": rotation,
                "mode": mode,
                "bindings": bindings,
                "status": event["product_payload_status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
