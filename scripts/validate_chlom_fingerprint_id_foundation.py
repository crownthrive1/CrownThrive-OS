#!/usr/bin/env python3
"""Validate the Phase-2.99 CHLOM Fingerprint ID foundation."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from chlom_fingerprint_registry import FINGERPRINT_PREFIX, PROFILE_ID, fingerprint_record

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers" / "manifests" / "chlom-fingerprint-id-foundation.v1.json"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FP = re.compile(r"^ctfp:v1:sha256:[0-9a-f]{64}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(data["schema_version"] == "1.0.0", "unexpected schema version")
    require(data["manifest_id"] == "ct.manifest.chlom-fingerprint-id-foundation.v1", "manifest id drift")
    require(data["phase"] == "2.99", "phase drift")
    require(data["issue"] == 150, "issue binding drift")
    require(data["publication_classification"] == "PUBLIC_STANDARD+PUBLIC_DOCTRINE", "publication classification drift")
    require(data["canonicalization_profile"]["profile_id"] == PROFILE_ID, "canonicalization profile drift")
    require(data["fingerprint_contract"]["format"] == "ctfp:v1:sha256:<64-lowercase-hex>", "fingerprint format drift")
    require(data["fingerprint_contract"]["fingerprint_is_not"] == "biometric_fingerprint", "biometric boundary missing")
    require(data["phase3_state"].startswith("blocked_pending_phase_2_99"), "Phase 3 may not be promoted by this packet")

    runtime = data["runtime_evidence"]
    require(runtime["subjects"] == 70, "runtime subject count drift")
    require(runtime["s100_source_subjects"] == 68, "runtime S100 subject count drift")
    require(runtime["fingerprints"] == 69, "runtime fingerprint count drift")
    require(runtime["s100_fingerprints"] == 68, "runtime S100 fingerprint count drift")
    require(runtime["founder_override_attestations"] == 1, "founder override attestation missing")
    require(runtime["did_bindings"] == 0, "DID binding must remain unactivated in Phase 2.99 foundation")
    require(runtime["credential_records"] == 0, "credential issuance must remain unactivated")
    require(runtime["proof_anchors"] == 0, "external proof anchoring must remain unactivated")
    require(runtime["security_advisor_lints_after_self_heal"] == 0, "security advisor must be clean")
    require(runtime["chlom_identity_unindexed_foreign_keys_after_self_heal"] == 0, "new-schema FK indexes incomplete")

    receipts = runtime["migration_receipts"]
    require(len(receipts) == 3, "expected three bounded migration receipts")
    for receipt in receipts:
        require(HEX64.fullmatch(receipt["sha256"]) is not None, f"invalid migration digest: {receipt['name']}")
        require(receipt["classification"] == "RESTRICTED_INSTITUTIONAL", "DDL must remain restricted")

    override = data["founder_override"]
    record = override["canonical_record"]
    require(record["signer_name"].strip() != "", "override signer is required")
    require(record["signature_attestation_type"] == "typed_name_attestation", "typed-name attestation drift")
    require(override["cryptographic_nonrepudiation"] is False, "typed name must not claim cryptographic nonrepudiation")
    _, digest, fingerprint_id = fingerprint_record(record)
    require(digest == override["sha256"], "override SHA-256 mismatch")
    require(fingerprint_id == override["fingerprint_id"], "override Fingerprint ID mismatch")
    require(FP.fullmatch(fingerprint_id) is not None, "override Fingerprint ID format invalid")

    s100 = data["s100_source_registry"]
    ledger = ROOT / s100["ledger_path"]
    ledger_bytes = ledger.read_bytes()
    require(hashlib.sha256(ledger_bytes).hexdigest() == s100["ledger_sha256"], "S100 ledger transport hash mismatch")
    with ledger.open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    require(s100["source_row_count"] == 68, "S100 row-count contract drift")
    require(len(records) == 68, "fingerprint ledger must contain exactly 68 rows")
    require(HEX64.fullmatch(s100["source_file_sha256"]) is not None, "source file SHA-256 invalid")

    seen_rows: set[str] = set()
    seen_subjects: set[str] = set()
    seen_fps: set[str] = set()
    for index, item in enumerate(records, start=1):
        expected_row = f"S100-PORT-{index:03d}"
        expected_subject = f"ct.source.s100.port.{index:03d}"
        require(item["source_row_id"] == expected_row, f"row sequence drift at {index}")
        require(item["source_subject_id"] == expected_subject, f"subject sequence drift at {index}")
        require(item["source_row_id"] not in seen_rows, f"duplicate source row {expected_row}")
        require(item["source_subject_id"] not in seen_subjects, f"duplicate source subject {expected_subject}")
        require(item["fingerprint_id"] not in seen_fps, f"duplicate fingerprint at {expected_row}")

        canonical_record = {
            "corridor": item["corridor"],
            "priority": item["priority"],
            "record_kind": "holdings_portfolio_source_row",
            "source_function": item["source_function"],
            "source_id": "S100",
            "source_name": item["source_name"],
            "source_row_id": item["source_row_id"],
            "source_status": item["source_status"],
        }
        _, calculated_digest, calculated_fp = fingerprint_record(canonical_record)
        require(calculated_digest == item["sha256"], f"digest mismatch at {expected_row}")
        require(calculated_fp == item["fingerprint_id"], f"fingerprint mismatch at {expected_row}")
        require(FP.fullmatch(item["fingerprint_id"]) is not None, f"fingerprint format invalid at {expected_row}")

        seen_rows.add(item["source_row_id"])
        seen_subjects.add(item["source_subject_id"])
        seen_fps.add(item["fingerprint_id"])

    cohorts = {x["cohort_id"]: x for x in data["future_cohorts"]}
    require(cohorts["ct.cohort.fingerprint.s100-domains"]["count"] == 82, "domain cohort drift")
    require(cohorts["ct.cohort.fingerprint.s100-engines"]["count"] == 85, "engine cohort drift")
    require(cohorts["ct.cohort.fingerprint.phase2-7-frameworks"]["count"] == 74, "framework cohort drift")
    require(cohorts["ct.cohort.fingerprint.help-center-795"]["count"] == 795, "Help Center cohort drift")
    require("held_for_#131" in cohorts["ct.cohort.fingerprint.help-center-795"]["state"], "795 exposure/IP HOLD missing")

    require("token_issuance" in data["prohibited_activations"], "token prohibition missing")
    require("public_chain_launch" in data["prohibited_activations"], "chain-launch prohibition missing")
    require("value_bearing_smart_contract" in data["prohibited_activations"], "value-bearing contract prohibition missing")

    print("PASS: CHLOM Fingerprint ID foundation validated")
    print(f"  override: {override['fingerprint_id']}")
    print(f"  S100 source fingerprints: {len(records)}")
    print(f"  first: {records[0]['fingerprint_id']}")
    print(f"  last:  {records[-1]['fingerprint_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
