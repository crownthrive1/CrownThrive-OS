#!/usr/bin/env python3
"""Report secret-pattern labels and file paths without printing matched values.

This diagnostic complements validate_docs.py. It is safe for CI logs because it
never prints the matching credential-shaped substring or surrounding context.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".mdx", ".json", ".svg", ".yml", ".yaml", ".py", ".txt"}
SKIP_DIRECTORIES = {".git", ".venv", "venv", "node_modules", ".mintlify", "__pycache__"}
ALLOWED_TEMPLATE_NOTICE_PATHS = {Path("THIRD_PARTY_NOTICES.md")}

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "Stripe live secret": re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
    "Stripe test secret": re.compile(r"\bsk_test_[A-Za-z0-9]{16,}\b"),
    "Stripe webhook secret": re.compile(r"\bwhsec_[A-Za-z0-9]{16,}\b"),
    "OpenAI project key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b"),
    "GitHub classic token": re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
    "GitHub fine-grained token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "AWS access key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "Private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def iter_text_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and not any(part in SKIP_DIRECTORIES for part in path.relative_to(ROOT).parts)
    ]


def main() -> int:
    findings: list[tuple[str, Path]] = []
    for path in iter_text_files():
        relative = path.relative_to(ROOT)
        if relative in ALLOWED_TEMPLATE_NOTICE_PATHS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append((label, relative))

    if findings:
        print("Credential-shaped pattern locations (matched values redacted):")
        for label, relative in sorted(findings, key=lambda item: (str(item[1]), item[0])):
            print(f"- {label}: {relative}")
        print(f"Total redacted findings: {len(findings)}")
        return 1

    print("Credential-shaped pattern location scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
