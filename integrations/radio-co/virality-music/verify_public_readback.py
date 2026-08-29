#!/usr/bin/env python3
"""Verify the public Radio.co contract for the Virality Music station.

This verifier is intentionally read-only and secret-free. It only contacts
HTTPS endpoints on public.radio.co declared in verification-contract.json.
It never reads the live-broadcast password or mutates provider state.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INTEGRATION_ID = "virality-music.radio-co.s0831f6c44"
STATION_ID = "s0831f6c44"
ALLOWED_HOST = "public.radio.co"
USER_AGENT = "CrownThrive-OS-RadioCo-Readback/1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def nested_get(document: Any, dotted_path: str) -> tuple[bool, Any]:
    current = document
    for component in dotted_path.split("."):
        if not isinstance(current, dict) or component not in current:
            return False, None
        current = current[component]
    return True, current


def validate_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
        raise ValueError(
            f"readback URL must be HTTPS on {ALLOWED_HOST}; received {url!r}"
        )


def fetch_json(url: str, timeout: float) -> tuple[int | None, Any | None, str | None]:
    validate_url(url)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )

    status: int | None = None
    body = b""
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return None, None, f"transport_error: {type(error).__name__}: {error}"

    if not body:
        return status, None, None

    try:
        return status, json.loads(body.decode("utf-8")), None
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return status, None, f"json_decode_error: {type(error).__name__}: {error}"


def run_check(check: dict[str, Any], timeout: float) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": check["id"],
        "class": check["class"],
        "url": check["url"],
        "checked_at": utc_now(),
        "state": "failed",
    }

    try:
        status, payload, error = fetch_json(check["url"], timeout)
    except ValueError as exc:
        result["error"] = str(exc)
        return result

    result["http_status"] = status
    expected_http = set(check.get("expected_http", [200]))

    if status not in expected_http:
        result["error"] = error or f"unexpected_http_status: {status}"
        return result

    # An explicitly accepted non-2xx observational response means the public
    # API was reached but the optional resource is not presently available.
    # Its error body is not required to be JSON.
    if status is not None and not (200 <= status < 300):
        result["state"] = "observed_absent"
        return result

    if error:
        result["error"] = error
        return result

    if check.get("expect_json") and payload is None:
        result["error"] = "expected_json_payload"
        return result

    for path in check.get("required_json_paths", []):
        exists, _ = nested_get(payload, path)
        if not exists:
            result["error"] = f"missing_json_path: {path}"
            return result

    for path, allowed in check.get("allowed_values", {}).items():
        exists, value = nested_get(payload, path)
        if not exists:
            result["error"] = f"missing_json_path: {path}"
            return result
        if value not in allowed:
            result["error"] = f"disallowed_value: {path}={value!r}"
            return result
        result.setdefault("observations", {})[path] = value

    if check["id"] == "station_metadata" and isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            result["observations"] = {
                "name": data.get("name"),
                "streaming_links": data.get("streaming_links"),
            }
    elif check["id"] in {"current_track", "next_track"} and isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            result["observations"] = {
                "title": data.get("title"),
                "start_time": data.get("start_time"),
            }
    elif check["id"] == "track_history" and isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            result["observations"] = {"items": len(data)}

    result["state"] = "passed"
    return result


def overall_state(results: list[dict[str, Any]]) -> str:
    required = [item for item in results if item.get("class") == "required"]
    if not required or any(item.get("state") != "passed" for item in required):
        return "unverified"

    observational_failures = [
        item
        for item in results
        if item.get("class") == "observational" and item.get("state") == "failed"
    ]
    return "degraded" if observational_failures else "verified"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=10.0, help="per-request timeout")
    parser.add_argument("--output", type=Path, help="optional JSON evidence output path")
    args = parser.parse_args()

    contract_path = Path(__file__).with_name("verification-contract.json")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    if contract.get("integration_id") != INTEGRATION_ID:
        raise SystemExit("verification contract integration_id mismatch")
    if contract.get("station_id") != STATION_ID:
        raise SystemExit("verification contract station_id mismatch")

    results = [run_check(check, args.timeout) for check in contract.get("checks", [])]
    evidence = {
        "checked_at": utc_now(),
        "integration_id": INTEGRATION_ID,
        "station_id": STATION_ID,
        "overall_state": overall_state(results),
        "checks": results,
        "security": {
            "secret_accessed": False,
            "provider_mutated": False,
        },
    }

    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")

    return 0 if evidence["overall_state"] in {"verified", "degraded"} else 1


if __name__ == "__main__":
    sys.exit(main())
