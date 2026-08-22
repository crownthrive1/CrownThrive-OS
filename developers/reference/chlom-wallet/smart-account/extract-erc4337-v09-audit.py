#!/usr/bin/env python3
"""Extract bounded metadata from the pinned public ERC-4337 v0.9 audit PDF.

This script performs no chain access, signing, deployment, or source-profile
promotion. Its output is evidence for independent review, not approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

EXPECTED_SIZE = 498_502
EXPECTED_GIT_BLOB_SHA1 = "d0cd0ad29d341d35df1047cadde6cb67d453be91"
EXPECTED_PATH = "audits/ERC-4337 Account Abstraction v0.9 Security Review - Cantina.pdf"
KEYWORDS = (
    "audit", "review", "scope", "commit", "entrypoint", "code hash", "codehash",
    "deployment", "address", "critical", "high", "medium", "low", "informational",
    "finding", "findings", "issue", "issues", "resolved", "unresolved",
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git identity, not security use.


def run_text(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout


def parse_pdfinfo(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def bounded_markers(text: str, limit: int = 80, width: int = 240) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = clean_line(raw)
        if not line:
            continue
        lowered = line.lower()
        matched = [keyword for keyword in KEYWORDS if keyword in lowered]
        if not matched:
            continue
        clipped = line[:width]
        dedupe = clipped.lower()
        if dedupe in seen:
            continue
        seen.add(dedupe)
        markers.append({
            "line": number,
            "keywords": matched,
            "text": clipped,
            "text_sha256": sha256_hex(line.encode("utf-8")),
        })
        if len(markers) >= limit:
            break
    return markers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = args.pdf.read_bytes()
    if len(data) != EXPECTED_SIZE:
        raise SystemExit(f"audit_size_mismatch:{len(data)}")
    observed_blob = git_blob_sha1(data)
    if observed_blob != EXPECTED_GIT_BLOB_SHA1:
        raise SystemExit(f"audit_git_blob_sha1_mismatch:{observed_blob}")

    info_text = run_text(["pdfinfo", str(args.pdf)])
    pdfinfo = parse_pdfinfo(info_text)
    page_count = int(pdfinfo.get("Pages", "0"))
    if page_count < 1:
        raise SystemExit("audit_page_count_invalid")

    extracted = run_text(["pdftotext", "-layout", str(args.pdf), "-"])
    normalized = "\n".join(clean_line(line) for line in extracted.splitlines() if clean_line(line))
    if len(normalized) < 1_000:
        raise SystemExit(f"audit_text_extraction_insufficient:{len(normalized)}")

    full_commits = sorted(set(re.findall(r"(?<![0-9a-fA-F])[0-9a-fA-F]{40}(?![0-9a-fA-F])", normalized)))
    evm_addresses = sorted(set(value.lower() for value in re.findall(r"0x[0-9a-fA-F]{40}", normalized)))
    bytes32_values = sorted(set(value.lower() for value in re.findall(r"0x[0-9a-fA-F]{64}", normalized)))
    markers = bounded_markers(normalized)

    severity_mentions = {
        severity: len(re.findall(rf"\b{severity}\b", normalized, flags=re.IGNORECASE))
        for severity in ("critical", "high", "medium", "low", "informational")
    }

    body = {
        "schema_version": "1.0.0",
        "evidence_contract": "ct.wallet.erc4337.v0.9.audit-extraction.v1",
        "result": "PASS_AUDIT_PDF_IDENTITY_AND_TEXT_EXTRACTION_HOLD_INTERPRETATION",
        "source": {
            "repository": "eth-infinitism/account-abstraction",
            "path": EXPECTED_PATH,
            "git_blob_sha1": observed_blob,
            "size_bytes": len(data),
            "pdf_sha256": sha256_hex(data),
        },
        "document": {
            "page_count": page_count,
            "pdfinfo": {
                key: pdfinfo.get(key)
                for key in ("Title", "Author", "Creator", "Producer", "CreationDate", "ModDate", "Pages")
                if pdfinfo.get(key)
            },
            "text_character_count": len(normalized),
            "text_sha256": sha256_hex(normalized.encode("utf-8")),
            "full_commit_candidates": full_commits,
            "evm_address_candidates": evm_addresses,
            "bytes32_candidates": bytes32_values,
            "severity_word_mentions": severity_mentions,
            "bounded_evidence_markers": markers,
        },
        "interpretation": {
            "audit_scope_commit_confirmed": False,
            "runtime_codehash_independently_approved": False,
            "runtime_codehash_verified_for_deployment": False,
            "requires_independent_human_and_agent_review": True,
            "disposition": "HOLD_EXTRACTED_EVIDENCE_REQUIRES_INTERPRETATION",
        },
        "hard_boundaries": {
            "external_rpc_used": False,
            "rpc_write_methods_used": False,
            "signer_used": False,
            "user_operation_created": False,
            "simulation_completed": False,
            "deployment_performed": False,
            "broadcast_performed": False,
            "custody": False,
            "money_movement": False,
            "production_rights_grant": False,
            "phase_advancement": False,
        },
    }

    args.output.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(body, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
