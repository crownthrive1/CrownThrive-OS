#!/usr/bin/env python3
"""Print bounded diagnostics for PR #2070 operational-knowledge admission.

The script is temporary and emits source locations/structures only. It does not
mutate institutional state or lower any validator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
NEEDLES = (
    "snapshot baseline missing title",
    "family baseline missing title",
    "supplied penta docs missing title",
    "PentaMail",
    "PentaCommunicationsFactory",
)


def iter_text_files() -> Iterable[Path]:
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "node_modules", "__pycache__"} for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".json", ".md", ".mdx", ".yml", ".yaml", ".toml"}:
            continue
        yield path


def context(text: str, needle: str, radius: int = 1800) -> str:
    index = text.find(needle)
    if index < 0:
        return ""
    start = max(0, index - radius)
    end = min(len(text), index + len(needle) + radius)
    return text[start:end]


def main() -> None:
    findings: dict[str, list[str]] = {needle: [] for needle in NEEDLES}
    for path in iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for needle in NEEDLES:
            if needle in text:
                findings[needle].append(rel)

    print("PR2070_OPERATIONAL_DIAGNOSTIC_INDEX")
    print(json.dumps(findings, indent=2, sort_keys=True))

    primary = ROOT / "scripts" / "penta_operational_knowledge.py"
    text = primary.read_text(encoding="utf-8")
    for needle in NEEDLES[:3]:
        snippet = context(text, needle)
        print(f"\n--- SOURCE_CONTEXT:{needle} ---")
        print(snippet or "NOT_FOUND_IN_PRIMARY_MODULE")

    for needle in NEEDLES[3:]:
        print(f"\n--- FILE_CONTEXTS:{needle} ---")
        for rel in findings[needle][:30]:
            path = ROOT / rel
            file_text = path.read_text(encoding="utf-8")
            snippet = context(file_text, needle, radius=700)
            print(f"\n### {rel}\n{snippet}")


if __name__ == "__main__":
    main()
