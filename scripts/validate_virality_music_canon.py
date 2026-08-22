#!/usr/bin/env python3
"""Public-repository guard for the Virality Music canon projection."""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "virality-music" / "canon-registry-v1.json"
PAGE = ROOT / "platforms" / "virality-music-creative-canon-and-suno-standards.mdx"
REGISTER_PAGE = ROOT / "knowledge" / "virality-music-canon-source-and-conflict-register.mdx"

if not REGISTRY.exists():
    REGISTRY = ROOT / "14_Public_Canon_Registry.json"
if not PAGE.exists():
    PAGE = ROOT / "11_Public_Projection_Mintlify.mdx"
if not REGISTER_PAGE.exists():
    REGISTER_PAGE = ROOT / "13_Public_Source_And_Conflict_Register.mdx"

ID_RE = re.compile(r"^VM-CANON-[A-Z0-9-]+$")
FORBIDDEN_KEYS = {
    "prompt_grammar",
    "scoring_weights",
    "secret_locator",
    "credential",
    "unreleased_lyrics",
    "master_url",
    "private_identity",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    for path in (REGISTRY, PAGE, REGISTER_PAGE):
        if not path.is_file():
            fail(f"missing required public canon artifact: {path.relative_to(ROOT)}")

    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        fail("public registry must contain records")

    seen: set[str] = set()
    for record in records:
        canon_id = record.get("canon_id", "")
        if not ID_RE.fullmatch(canon_id):
            fail(f"invalid canon ID: {canon_id!r}")
        if canon_id in seen:
            fail(f"duplicate canon ID: {canon_id}")
        seen.add(canon_id)
        if record.get("classification") not in {"PUBLIC", "PUBLIC_SUMMARY"}:
            fail(f"nonpublic classification in projection: {canon_id}")
        if set(record).intersection(FORBIDDEN_KEYS):
            fail(f"restricted key in public record: {canon_id}")
        if not record.get("source_refs"):
            fail(f"missing source references: {canon_id}")

    for path in (PAGE, REGISTER_PAGE):
        text = path.read_text(encoding="utf-8")
        if "VAULT_SECRET_VALUE" in text or "PRIVATE_STORAGE_LOCATOR" in text:
            fail(f"restricted placeholder leaked into {path.relative_to(ROOT)}")

    print(f"PASS: {len(records)} public canon records validated")


if __name__ == "__main__":
    main()
