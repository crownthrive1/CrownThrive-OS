#!/usr/bin/env python3
"""Candidate-first internal-link scanner and additive approved-link applicator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
TITLE_RE = re.compile(r"(?m)^title:\s*[\"']?(.+?)[\"']?\s*$")
EDGE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_RECEIPT_LIFETIME = timedelta(days=30)
MAX_CLOCK_SKEW = timedelta(minutes=5)
ALLOWED_DOCUMENT_PREFIXES = (
    ("automation",),
    ("changelog",),
    ("developers", "agents"),
    ("docs",),
    ("governance",),
    ("pages",),
    ("reference",),
    ("runbooks",),
)


def inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes documentation root: {candidate}") from exc
    return resolved


def doc_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in {".md", ".mdx"} and path.is_file())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def governed_document(root: Path, path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    if path.suffix.lower() not in {".md", ".mdx"}:
        return False
    parts = relative.parts
    return any(parts[: len(prefix)] == prefix for prefix in ALLOWED_DOCUMENT_PREFIXES)


def canonical_receipt_payload(receipt: dict[str, Any]) -> bytes:
    payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_detached_receipt(
    edge: dict[str, Any],
    manifest: Path,
    trusted_receipt_sha256: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    reference = edge.get("approval_receipt_ref")
    expected_file_sha256 = edge.get("approval_receipt_file_sha256")
    if not isinstance(reference, str) or not reference.endswith(".json"):
        return None, "detached approval receipt reference absent"
    if not isinstance(expected_file_sha256, str) or not SHA256_RE.fullmatch(expected_file_sha256):
        return None, "detached approval receipt file digest absent"
    if not isinstance(trusted_receipt_sha256, str) or not SHA256_RE.fullmatch(trusted_receipt_sha256):
        return None, "out-of-band trusted receipt digest absent"
    if expected_file_sha256 != trusted_receipt_sha256:
        return None, "manifest receipt digest is not the out-of-band trusted digest"
    requested = manifest.parent / reference
    if requested.is_symlink():
        return None, "approval receipt symlink forbidden"
    try:
        receipt_path = inside(manifest.parent, requested)
    except ValueError:
        return None, "approval receipt escapes manifest directory"
    if not receipt_path.is_file():
        return None, "detached approval receipt file missing"
    if sha256_file(receipt_path) != expected_file_sha256:
        return None, "detached approval receipt file digest mismatch"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "detached approval receipt is not valid JSON"
    if not isinstance(receipt, dict):
        return None, "detached approval receipt must be an object"
    return receipt, None


def receipt_error(
    edge: dict[str, Any],
    receipt: dict[str, Any],
    source: Path,
    target: Path,
    authorized_reviewer_ids: set[str],
) -> str | None:
    required = {
        "receipt_sha256",
        "edge_id",
        "decision",
        "scope",
        "originator_id",
        "reviewer_kind",
        "reviewer_id",
        "review_execution_id",
        "issued_at",
        "expires_at",
        "source_sha256",
        "target_sha256",
        "independent",
    }
    if required - receipt.keys():
        return "approval receipt fields incomplete"
    if receipt["edge_id"] != edge.get("edge_id") or receipt["decision"] != "APPROVED":
        return "approval receipt decision or edge mismatch"
    if receipt["scope"] != "INTERNAL_LINK_ADD":
        return "approval receipt scope mismatch"
    if receipt["originator_id"] != edge.get("originator_id"):
        return "approval receipt originator mismatch"
    if receipt["independent"] is not True or receipt["reviewer_id"] == receipt["originator_id"]:
        return "independent reviewer evidence absent"
    if receipt["reviewer_kind"] not in {"human", "agent_d"}:
        return "reviewer kind is not authorized"
    if not isinstance(receipt["reviewer_id"], str) or receipt["reviewer_id"] not in authorized_reviewer_ids:
        return "reviewer identity is absent from the out-of-band authorized set"
    if receipt["reviewer_kind"] == "agent_d" and receipt["reviewer_id"] != "ct.relay.agent-d":
        return "Agent D reviewer identity mismatch"
    if not isinstance(receipt["review_execution_id"], str) or not receipt["review_execution_id"].strip():
        return "review execution reference absent"
    try:
        issued_at = datetime.fromisoformat(str(receipt["issued_at"]).replace("Z", "+00:00"))
        expires_at = datetime.fromisoformat(str(receipt["expires_at"]).replace("Z", "+00:00"))
    except ValueError:
        return "approval receipt time window invalid"
    if issued_at.tzinfo is None or expires_at.tzinfo is None:
        return "approval receipt time window lacks timezone"
    if expires_at <= issued_at:
        return "approval receipt expiry does not follow issuance"
    now = datetime.now(timezone.utc)
    if issued_at > now + MAX_CLOCK_SKEW:
        return "approval receipt issuance is in the future"
    if expires_at - issued_at > MAX_RECEIPT_LIFETIME:
        return "approval receipt lifetime exceeds the governed maximum"
    if now >= expires_at:
        return "approval receipt expired"
    if receipt["source_sha256"] != sha256_file(source) or receipt["target_sha256"] != sha256_file(target):
        return "approval receipt content digest mismatch"
    receipt_sha256 = receipt.get("receipt_sha256")
    if not isinstance(receipt_sha256, str) or not SHA256_RE.fullmatch(receipt_sha256):
        return "approval receipt digest invalid"
    expected = hashlib.sha256(canonical_receipt_payload(receipt)).hexdigest()
    if receipt_sha256 != expected:
        return "approval receipt digest mismatch"
    return None


def resolve_link(source: Path, target: str, root: Path) -> Path | None:
    if target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    plain = target.split("#", 1)[0].split("?", 1)[0]
    if not plain:
        return None
    base = root if plain.startswith("/") else source.parent
    candidate = inside(root, base / plain.lstrip("/"))
    possibilities = [candidate]
    if not candidate.suffix:
        possibilities.extend([candidate.with_suffix(".mdx"), candidate.with_suffix(".md"), candidate / "index.mdx", candidate / "index.md"])
    return next((path for path in possibilities if path.is_file()), candidate)


def scan(root: Path) -> dict[str, Any]:
    broken: list[dict[str, str]] = []
    titles: list[dict[str, str]] = []
    files = doc_files(root)
    for path in files:
        text = path.read_text(encoding="utf-8")
        title_match = TITLE_RE.search(text)
        titles.append({"path": path.relative_to(root).as_posix(), "title": title_match.group(1).strip() if title_match else path.stem})
        for target in LINK_RE.findall(text):
            resolved = resolve_link(path, target, root)
            if resolved is not None and not resolved.is_file():
                broken.append({"source": path.relative_to(root).as_posix(), "target": target})
    digest = hashlib.sha256(json.dumps(titles, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"status": "PASS" if not broken else "NEED_TO_DO", "document_count": len(files), "title_index_sha256": digest, "broken_links": broken}


def validate_candidates(root: Path, manifest: Path) -> dict[str, Any]:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    errors: list[str] = []
    edge_ids: list[str] = []
    for edge in data.get("edges", []):
        edge_id = edge.get("edge_id")
        if not isinstance(edge_id, str) or not EDGE_ID_RE.fullmatch(edge_id):
            errors.append("invalid edge identifier")
            continue
        edge_ids.append(edge_id)
        if edge.get("status") not in {"CANDIDATE", "APPROVED", "SUPERSEDED"}:
            errors.append(f"{edge_id}: invalid status")
        for key in ("source", "target"):
            relative = edge.get(key)
            if not isinstance(relative, str):
                errors.append(f"{edge_id}: {key} path absent")
                continue
            requested = root / relative
            if requested.is_symlink():
                errors.append(f"{edge_id}: {key} symlink forbidden")
                continue
            try:
                resolved = inside(root, requested)
            except ValueError as exc:
                errors.append(f"{edge_id}: {exc}")
                continue
            if not resolved.is_file():
                errors.append(f"{edge_id}: {key} missing: {relative}")
            elif not governed_document(root, resolved):
                errors.append(f"{edge_id}: {key} is outside governed documentation roots")
        if edge.get("status") == "CANDIDATE" and (
            edge.get("approval_receipt_ref") is not None
            or edge.get("approval_receipt_file_sha256") is not None
        ):
            errors.append(f"{edge_id}: candidate edge carries approval evidence")
    if len(edge_ids) != len(set(edge_ids)):
        errors.append("duplicate edge identifiers")
    return {
        "status": "PASS" if not errors else "NEED_TO_DO",
        "edge_count": len(edge_ids),
        "errors": errors,
        "write_count": 0,
    }


def apply_approved(
    root: Path,
    manifest: Path,
    *,
    trusted_receipt_sha256: str | None = None,
    authorized_reviewer_ids: set[str] | None = None,
) -> dict[str, Any]:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    skipped: list[dict[str, str]] = []
    approved_edges = [edge for edge in data.get("edges", []) if edge.get("status") == "APPROVED"]
    if len(approved_edges) > 1:
        return {
            "status": "HOLD",
            "applied": [],
            "skipped": [{"edge_id": "<batch>", "reason": "one approved edge per atomic apply is required"}],
            "delete_count": 0,
        }
    plan: list[dict[str, Any]] = []
    for edge in data.get("edges", []):
        edge_id = edge.get("edge_id", "<missing>")
        if not isinstance(edge_id, str) or not EDGE_ID_RE.fullmatch(edge_id):
            skipped.append({"edge_id": str(edge_id), "reason": "edge identifier invalid"})
            continue
        if edge.get("status") != "APPROVED":
            skipped.append({"edge_id": edge_id, "reason": "edge is not approved"})
            continue
        source_request = root / edge["source"]
        target_request = root / edge["target"]
        if source_request.is_symlink() or target_request.is_symlink():
            skipped.append({"edge_id": edge_id, "reason": "document symlink forbidden"})
            continue
        source = inside(root, source_request)
        target = inside(root, target_request)
        if not source.is_file() or not target.is_file():
            skipped.append({"edge_id": edge_id, "reason": "source or target missing"})
            continue
        if not governed_document(root, source) or not governed_document(root, target):
            skipped.append({"edge_id": edge_id, "reason": "path is outside governed documentation roots"})
            continue
        receipt, load_error = load_detached_receipt(edge, manifest, trusted_receipt_sha256)
        if load_error or receipt is None:
            skipped.append({"edge_id": edge_id, "reason": load_error or "approval receipt absent"})
            continue
        approval_error = receipt_error(edge, receipt, source, target, authorized_reviewer_ids or set())
        if approval_error:
            skipped.append({"edge_id": edge_id, "reason": approval_error})
            continue
        relative = os.path.relpath(target, source.parent).replace(os.sep, "/")
        current = source.read_text(encoding="utf-8")
        marker = f"<!-- CT-MANAGED-LINK:{edge_id} -->"
        if marker in current or f"]({relative})" in current:
            skipped.append({"edge_id": edge_id, "reason": "already present"})
            continue
        label = target.stem.replace("-", " ").title()
        separator = "\n" if current.endswith("\n") else "\n\n"
        block = f"{separator}{marker}\n- [{label}]({relative})\n"
        plan.append(
            {
                "edge_id": edge_id,
                "source": source,
                "expected_source_sha256": receipt["source_sha256"],
                "new_bytes": current.encode("utf-8") + block.encode("utf-8"),
            }
        )
    if approved_edges and not plan:
        return {"status": "HOLD", "applied": [], "skipped": skipped, "delete_count": 0}
    if not plan:
        return {"status": "NO_CHANGE", "applied": [], "skipped": skipped, "delete_count": 0}

    operation = plan[0]
    source = operation["source"]
    if sha256_file(source) != operation["expected_source_sha256"]:
        return {
            "status": "HOLD",
            "applied": [],
            "skipped": [{"edge_id": operation["edge_id"], "reason": "compare-and-swap source digest changed"}],
            "delete_count": 0,
        }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=source.parent, prefix=".ct-link-", delete=False) as handle:
            temporary_path = Path(handle.name)
            handle.write(operation["new_bytes"])
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, source.stat().st_mode & 0o777)
        if sha256_file(source) != operation["expected_source_sha256"]:
            return {
                "status": "HOLD",
                "applied": [],
                "skipped": [{"edge_id": operation["edge_id"], "reason": "compare-and-swap source changed before commit"}],
                "delete_count": 0,
            }
        os.replace(temporary_path, source)
        temporary_path = None
        directory_fd = os.open(source.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return {"status": "APPLIED", "applied": [operation["edge_id"]], "skipped": skipped, "delete_count": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", action="store_true")
    group.add_argument("--apply-approved", type=Path)
    group.add_argument("--validate-candidates", type=Path)
    parser.add_argument(
        "--trusted-receipt-sha256",
        help="receipt-file digest obtained through a separate trusted control-plane channel",
    )
    parser.add_argument(
        "--authorized-reviewer-id",
        action="append",
        default=[],
        help="reviewer identity authorized through a separate trusted control-plane channel",
    )
    args = parser.parse_args()
    try:
        if args.scan:
            result = scan(args.root)
        elif args.validate_candidates:
            result = validate_candidates(args.root, args.validate_candidates)
        else:
            result = apply_approved(
                args.root,
                args.apply_approved,
                trusted_receipt_sha256=args.trusted_receipt_sha256,
                authorized_reviewer_ids=set(args.authorized_reviewer_id),
            )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("status") in {"FAIL", "HOLD", "NEED_TO_DO"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
