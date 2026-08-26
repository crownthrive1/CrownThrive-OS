#!/usr/bin/env python3
"""Verify PDF/DOCX rendered-text parity without emitting protected text.

The DOCX is rendered to a temporary PDF with LibreOffice. Poppler pdftotext
extracts UTF-8 from both PDFs. The verifier lowercases, normalizes common curly
apostrophes, tokenizes ASCII words with optional internal apostrophes, joins
tokens with one space, and compares SHA-256 digests. Temporary rendered and
text data are deleted when the process exits; only hashes and counts are shown.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")
APOSTROPHE_TRANSLATION = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'"})


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tool_version(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return completed.stdout.decode("utf-8", "replace").splitlines()[0].strip()


def normalized_pdf_text_evidence(path: Path, pdftotext: str) -> dict[str, Any]:
    completed = subprocess.run(
        [pdftotext, "-enc", "UTF-8", str(path), "-"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    extracted = completed.stdout.decode("utf-8", "strict")
    normalized = extracted.lower().translate(APOSTROPHE_TRANSLATION)
    tokens = TOKEN_RE.findall(normalized)
    normalized_bytes = " ".join(tokens).encode("utf-8")
    return {
        "token_count": len(tokens),
        "normalized_byte_count": len(normalized_bytes),
        "render_normalized_token_sha256": hashlib.sha256(normalized_bytes).hexdigest(),
    }


def render_docx(docx: Path, output_dir: Path, soffice: str) -> Path:
    profile = output_dir / "libreoffice-profile"
    profile.mkdir()
    completed = subprocess.run(
        [
            soffice,
            "--headless",
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(docx),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rendered = output_dir / f"{docx.stem}.pdf"
    if not rendered.is_file():
        message = (completed.stdout + completed.stderr).decode("utf-8", "replace").strip()
        raise RuntimeError(f"LibreOffice did not create the expected PDF: {message}")
    return rendered


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path, help="Source PDF master to inspect locally")
    parser.add_argument("--docx", required=True, type=Path, help="Counterpart DOCX master to render locally")
    parser.add_argument("--expected-sha256", help="Optional expected normalized-text SHA-256")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.pdf.is_file() or args.pdf.suffix.lower() != ".pdf":
        print("--pdf must identify an existing PDF", file=sys.stderr)
        return 1
    if not args.docx.is_file() or args.docx.suffix.lower() != ".docx":
        print("--docx must identify an existing DOCX", file=sys.stderr)
        return 1
    if args.expected_sha256 and not re.fullmatch(r"[0-9a-f]{64}", args.expected_sha256):
        print("--expected-sha256 must be a lowercase SHA-256 digest", file=sys.stderr)
        return 1

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    pdftotext = shutil.which("pdftotext")
    if not soffice or not pdftotext:
        print("soffice/libreoffice and pdftotext are required", file=sys.stderr)
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="virality-parity-") as directory:
            rendered = render_docx(args.docx, Path(directory), soffice)
            source_evidence = normalized_pdf_text_evidence(args.pdf, pdftotext)
            rendered_evidence = normalized_pdf_text_evidence(rendered, pdftotext)
            parity = source_evidence == rendered_evidence
            expected_match = (
                args.expected_sha256 is None
                or source_evidence["render_normalized_token_sha256"] == args.expected_sha256
            )
            result = {
                "schema": "ct.evidence.vm.source-parity.local.v1",
                "method": "DOCX_RENDER_TO_PDF_THEN_NORMALIZED_PDFTOTEXT_SHA256",
                "normalization": {
                    "case": "lowercase",
                    "apostrophes": "curly/modifier/backtick mapped to ASCII apostrophe",
                    "token_regex": TOKEN_RE.pattern,
                    "join": "single ASCII space",
                    "encoding": "UTF-8",
                },
                "tools": {
                    "libreoffice": tool_version([soffice, "--version"]),
                    "pdftotext": tool_version([pdftotext, "-v"]),
                },
                "source_pdf": {
                    "filename": args.pdf.name,
                    "binary_sha256": file_sha256(args.pdf),
                    **source_evidence,
                },
                "source_docx": {
                    "filename": args.docx.name,
                    "binary_sha256": file_sha256(args.docx),
                },
                "rendered_docx_pdf": {
                    "binary_sha256": file_sha256(rendered),
                    **rendered_evidence,
                },
                "render_normalized_token_sequence_parity": parity,
                "expected_sha256": args.expected_sha256,
                "expected_sha256_matches": expected_match,
                "protected_text_emitted": False,
            }
    except (OSError, RuntimeError, subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        print(f"Parity verification failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if parity and expected_match else 2


if __name__ == "__main__":
    raise SystemExit(main())
