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
ALLOWED_DIAGNOSTIC_STAGES = frozenset({
    "authorization",
    "oidc_verification",
    "request_validation",
    "database_connect",
    "resolve_release_evidence_bundle",
    "enqueue_release_projection",
    "dispatch_release_footer",
})
ALLOWED_DIAGNOSTIC_CODES = frozenset({
    "github_oidc_bearer_required",
    "github_oidc_verification_failed",
    "method_not_allowed",
    "request_body_invalid",
    "request_validation_rejected",
    "database_unavailable",
    "database_connection_failed",
    "database_unique_conflict",
    "database_foreign_key_conflict",
    "database_constraint_rejected",
    "database_permission_denied",
    "database_contract_missing",
    "database_timeout_or_lock",
    "database_serialization_conflict",
    "database_value_rejected",
    "database_capacity_exhausted",
    "database_application_exception",
    "database_provider_error",
    "unclassified_provider_error",
})
MAX_BYTES = 65536


def _legacy_detail_code(detail):
    """Classify legacy raw provider detail locally; never return or log it."""
    if not isinstance(detail, str):
        return "unavailable"
    value = detail[:8192].lower()
    if value == "database_unavailable":
        return "database_unavailable"
    if value in {
        "release_version_invalid",
        "release_tag_mismatch",
        "pr_number_invalid",
        "payload_bytes_invalid",
    }:
        return "request_validation_rejected"
    if any(token in value for token in ("oidc_", "jwt", "signature", "audience", "issuer")):
        return "github_oidc_verification_failed"
    if "duplicate key value" in value or "unique constraint" in value:
        return "database_unique_conflict"
    if "foreign key constraint" in value:
        return "database_foreign_key_conflict"
    if "check constraint" in value or "not-null constraint" in value:
        return "database_constraint_rejected"
    if "permission denied" in value or "insufficient privilege" in value:
        return "database_permission_denied"
    if "does not exist" in value and any(
        noun in value for noun in ("function ", "relation ", "schema ")
    ):
        return "database_contract_missing"
    if any(token in value for token in ("statement timeout", "lock timeout", "canceling statement", "could not obtain lock")):
        return "database_timeout_or_lock"
    if "could not serialize access" in value or "serialization failure" in value:
        return "database_serialization_conflict"
    if any(token in value for token in ("invalid input syntax", "numeric field overflow", "out of range")):
        return "database_value_rejected"
    if any(token in value for token in ("connection refused", "connection reset", "could not connect")):
        return "database_connection_failed"
    if re.search(r"\\bP0001\\b", value, flags=re.IGNORECASE) or "raise exception" in value:
        return "database_application_exception"
    return "unclassified_provider_error"


def diagnostic(path, http_status):
    code = "unavailable"
    stage = "unavailable"
    diagnostic_code = "unavailable"
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) <= MAX_BYTES:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                value = payload.get("error")
                if isinstance(value, str) and value in ALLOWED_ERRORS:
                    code = value
                stage_value = payload.get("diagnostic_stage")
                if isinstance(stage_value, str) and stage_value in ALLOWED_DIAGNOSTIC_STAGES:
                    stage = stage_value
                diagnostic_value = payload.get("diagnostic_code")
                if isinstance(diagnostic_value, str) and diagnostic_value in ALLOWED_DIAGNOSTIC_CODES:
                    diagnostic_code = diagnostic_value
                elif isinstance(payload.get("detail"), str):
                    diagnostic_code = _legacy_detail_code(payload.get("detail"))
    except (OSError, ValueError, RecursionError):
        pass
    return {
        "status": "HOLD",
        "http_status": http_status if re.fullmatch(r"[1-5][0-9]{2}", http_status) else "unavailable",
        "error_code": code,
        "diagnostic_stage": stage,
        "diagnostic_code": diagnostic_code,
    }


def main():
    if len(sys.argv) != 3:
        print(json.dumps({
            "status": "HOLD",
            "http_status": "unavailable",
            "error_code": "unavailable",
            "diagnostic_stage": "unavailable",
            "diagnostic_code": "unavailable",
        }))
        return 1
    print(json.dumps(diagnostic(sys.argv[1], sys.argv[2]), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
