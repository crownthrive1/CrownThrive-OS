"""Emit bounded public-safe failure metadata, never provider detail or body."""
import json
from pathlib import Path
import re
import sys

ALLOWED_ERRORS = frozenset({
    "release_evidence_projection_rejected",
    "github_oidc_verification_failed",
    "github_oidc_bearer_required",
    "method_not_allowed",
})
MAX_BYTES = 65536


def diagnostic(path, http_status):
    code = "unavailable"
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) <= MAX_BYTES:
            payload = json.loads(raw)
            value = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(value, str) and value in ALLOWED_ERRORS:
                code = value
    except (OSError, ValueError, RecursionError):
        pass
    return {
        "status": "HOLD",
        "http_status": http_status if re.fullmatch(r"[1-5][0-9]{2}", http_status) else "unavailable",
        "error_code": code,
    }


def main():
    if len(sys.argv) != 3:
        print(json.dumps({"status": "HOLD", "http_status": "unavailable", "error_code": "unavailable"}))
        return 1
    print(json.dumps(diagnostic(sys.argv[1], sys.argv[2]), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
