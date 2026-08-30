#!/usr/bin/env python3
"""Reconcile structured PentaDocs metadata for PentaRelease release pages.

PentaRelease owns seven bounded release-document projections. Mintlify maintains
page metadata separately from MDX body state, so a generated page that omits an
explicit ``sidebarTitle`` can retain stale provider metadata after the release
body advances. This reconciler makes the source representation explicit and
idempotent without touching page bodies or inventing release state.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TARGET_PATHS = (
    "pentarelease/latest.mdx",
    "pentarelease/faq.mdx",
    "pentarelease/changelog.mdx",
    "pentarelease/costs.mdx",
    "pentarelease/cie.mdx",
    "pentarelease/data.mdx",
    "pentarelease/evidence.mdx",
)

FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---(?P<tail>\n|\Z)", re.S)
TITLE_RE = re.compile(r"(?m)^title:\s*(?P<value>.+?)\s*$")
SIDEBAR_RE = re.compile(r"(?m)^sidebarTitle:\s*(?P<value>.+?)\s*$")


def reconcile_text(text: str) -> tuple[str, bool, str]:
    """Return reconciled text, whether it changed, and a bounded reason."""
    match = FRONTMATTER_RE.search(text)
    if not match:
        return text, False, "frontmatter_missing"

    frontmatter = match.group("body")
    title_match = TITLE_RE.search(frontmatter)
    if not title_match:
        return text, False, "title_missing"

    title_value = title_match.group("value").strip()
    sidebar_match = SIDEBAR_RE.search(frontmatter)

    if sidebar_match:
        current_value = sidebar_match.group("value").strip()
        if current_value == title_value:
            return text, False, "already_converged"
        new_frontmatter = SIDEBAR_RE.sub(
            f"sidebarTitle: {title_value}", frontmatter, count=1
        )
        reason = "sidebar_title_updated"
    else:
        insert_at = title_match.end()
        new_frontmatter = (
            frontmatter[:insert_at]
            + f"\nsidebarTitle: {title_value}"
            + frontmatter[insert_at:]
        )
        reason = "sidebar_title_added"

    new_text = (
        text[: match.start("body")]
        + new_frontmatter
        + text[match.end("body") :]
    )
    return new_text, new_text != text, reason


def reconcile_root(root: Path, *, write: bool) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    changed_count = 0
    hard_failures = 0

    for relative in TARGET_PATHS:
        path = root / relative
        if not path.is_file():
            rows.append({"path": relative, "state": "HOLD", "reason": "file_missing"})
            hard_failures += 1
            continue

        original = path.read_text(encoding="utf-8")
        reconciled, changed, reason = reconcile_text(original)
        if reason in {"frontmatter_missing", "title_missing"}:
            rows.append({"path": relative, "state": "HOLD", "reason": reason})
            hard_failures += 1
            continue

        if changed:
            changed_count += 1
            if write:
                path.write_text(reconciled, encoding="utf-8")
        rows.append(
            {
                "path": relative,
                "state": "UPDATED" if changed and write else "DRIFT" if changed else "PASS",
                "reason": reason,
            }
        )

    state = "PASS"
    if hard_failures:
        state = "HOLD"
    elif changed_count and not write:
        state = "DRIFT"
    elif changed_count and write:
        state = "RECONCILED"

    return {
        "schema": "ct.pentarelease.pentadocs-metadata-reconciliation.v1",
        "state": state,
        "write": write,
        "targets": len(TARGET_PATHS),
        "changed": changed_count,
        "hard_failures": hard_failures,
        "rows": rows,
        "authority_expansion": False,
        "provider_state_manufactured": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    write = bool(args.write)
    result = reconcile_root(Path(args.root).resolve(), write=write)
    print(json.dumps(result, indent=2, sort_keys=True))

    if result["state"] == "HOLD":
        return 2
    if args.check and result["state"] == "DRIFT":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
