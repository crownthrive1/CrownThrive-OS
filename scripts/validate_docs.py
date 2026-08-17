#!/usr/bin/env python3
"""Validate CrownThrive's public-safe institutional documentation repository.

The validator intentionally uses only the Python standard library so it can run
locally and in CI without introducing a package-install dependency.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

TEXT_SUFFIXES = {".md", ".mdx", ".json", ".svg", ".yml", ".yaml", ".py", ".txt"}
SKIP_DIRECTORIES = {".git", ".venv", "venv", "node_modules", ".mintlify", "__pycache__"}
ALLOWED_TEMPLATE_NOTICE_PATHS = {Path("THIRD_PARTY_NOTICES.md")}

# Strict enough to identify credential-shaped values rather than ordinary prose.
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

ROOT_TEMPLATE_FILES = {
    Path("README.md"),
    Path("AGENTS.md"),
    Path("docs.json"),
    Path("logo/light.svg"),
    Path("logo/dark.svg"),
    Path("favicon.svg"),
}

FORBIDDEN_ROOT_RESIDUE = {
    "Mintlify Starter Kit",
    "hi@mintlify.com",
    "https://github.com/mintlify",
    "https://linkedin.com/company/mintlify",
    "https://x.com/mintlify",
    "> **First-time setup**: Customize this file for your project.",
}

REQUIRED_ROOT_FILES = {
    Path("README.md"),
    Path("AGENTS.md"),
    Path("LICENSE"),
    Path("THIRD_PARTY_NOTICES.md"),
    Path("docs.json"),
    Path("logo/light.svg"),
    Path("logo/dark.svg"),
    Path("favicon.svg"),
}

FRONTMATTER_REQUIRED_FIELDS = {"title", "description"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of scripts/.",
    )
    return parser.parse_args()


def iter_navigation_pages(node: Any) -> Iterable[str]:
    """Yield page paths from Mintlify navigation structures."""
    if isinstance(node, str):
        yield node
        return
    if isinstance(node, list):
        for item in node:
            yield from iter_navigation_pages(item)
        return
    if not isinstance(node, dict):
        return

    for key in ("pages", "groups", "tabs", "dropdowns", "products", "versions", "languages"):
        value = node.get(key)
        if value is not None:
            yield from iter_navigation_pages(value)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path}: not valid UTF-8 ({exc})") from exc


def split_frontmatter(text: str) -> tuple[str, str] | None:
    if not text.startswith("---\n"):
        return None
    closing = text.find("\n---", 4)
    if closing == -1:
        return None
    frontmatter = text[4:closing]
    body = text[closing + 4 :].lstrip("\r\n")
    return frontmatter, body


def frontmatter_keys(frontmatter: str) -> set[str]:
    keys: set[str] = set()
    for line in frontmatter.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.:-]+)\s*:", line)
        if match:
            keys.add(match.group(1))
    return keys


def iter_text_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        yield path


def normalized_page_file(root: Path, page: str) -> Path:
    page_without_anchor = page.split("#", 1)[0].split("?", 1)[0].strip("/")
    candidate = root / page_without_anchor
    if candidate.suffix in {".md", ".mdx"}:
        return candidate
    return candidate.with_suffix(".mdx")


def validate(root: Path) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, int] = {
        "navigation_pages": 0,
        "mdx_pages": 0,
        "text_files_scanned": 0,
        "internal_links_checked": 0,
    }

    if not root.exists():
        return [f"Repository root does not exist: {root}"], warnings, stats

    for required in sorted(REQUIRED_ROOT_FILES):
        if not (root / required).is_file():
            errors.append(f"Missing required repository file: {required}")

    docs_path = root / "docs.json"
    if not docs_path.is_file():
        return errors, warnings, stats

    try:
        docs_config = json.loads(read_text(docs_path))
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid docs.json: {exc}")
        return errors, warnings, stats

    navigation = docs_config.get("navigation")
    if not isinstance(navigation, dict):
        errors.append("docs.json must contain an object at navigation")
        navigation = {}

    # Current Mintlify uses navigation.groups for this project. A legacy
    # navigation.pages field may still exist as an editor compatibility value;
    # do not count both trees as separate public navigation.
    primary_navigation: Any
    if navigation.get("groups"):
        primary_navigation = navigation["groups"]
    elif navigation.get("pages"):
        primary_navigation = navigation["pages"]
    else:
        primary_navigation = navigation

    page_paths = list(iter_navigation_pages(primary_navigation))
    stats["navigation_pages"] = len(page_paths)

    duplicates = sorted(path for path, count in Counter(page_paths).items() if count > 1)
    for duplicate in duplicates:
        errors.append(f"Duplicate navigation page: {duplicate}")

    navigated_files: set[Path] = set()
    for page in page_paths:
        if page.startswith(("http://", "https://", "mailto:")):
            continue
        file_path = normalized_page_file(root, page)
        navigated_files.add(file_path.resolve())
        relative = file_path.relative_to(root)
        if not file_path.is_file():
            errors.append(f"Navigation page is missing: {page} -> {relative}")
            continue

        try:
            text = read_text(file_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        parsed = split_frontmatter(text)
        if parsed is None:
            errors.append(f"Missing or malformed frontmatter: {relative}")
            continue

        frontmatter, body = parsed
        missing_fields = sorted(FRONTMATTER_REQUIRED_FIELDS - frontmatter_keys(frontmatter))
        if missing_fields:
            errors.append(f"Missing frontmatter fields {missing_fields}: {relative}")

        substantive = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
        if len(substantive) < 120:
            errors.append(f"Navigated page has insufficient substantive body content: {relative}")
        if not re.search(r"(?m)^#\s+\S", substantive):
            errors.append(f"Navigated page is missing an H1 heading: {relative}")

    mdx_files = [path for path in root.rglob("*.mdx") if not any(part in SKIP_DIRECTORIES for part in path.relative_to(root).parts)]
    stats["mdx_pages"] = len(mdx_files)
    for path in sorted(mdx_files):
        if path.resolve() not in navigated_files:
            warnings.append(f"Unlisted MDX page: {path.relative_to(root)}")

    for relative in sorted(ROOT_TEMPLATE_FILES):
        path = root / relative
        if not path.is_file():
            continue
        try:
            text = read_text(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        for residue in FORBIDDEN_ROOT_RESIDUE:
            if residue in text:
                errors.append(f"Template residue in {relative}: {residue!r}")

    for logo_path in (root / "logo/light.svg", root / "logo/dark.svg", root / "favicon.svg"):
        if not logo_path.is_file():
            continue
        text = read_text(logo_path)
        if "CrownThrive" not in text:
            errors.append(f"Brand asset does not identify CrownThrive: {logo_path.relative_to(root)}")
        if re.search(r"mintlify|starter kit", text, flags=re.IGNORECASE):
            errors.append(f"Third-party starter identity remains in {logo_path.relative_to(root)}")
        try:
            import xml.etree.ElementTree as ET

            ET.fromstring(text)
        except Exception as exc:  # noqa: BLE001 - report parser detail to contributor
            errors.append(f"Invalid SVG/XML in {logo_path.relative_to(root)}: {exc}")

    navbar_dump = json.dumps(
        {
            "navbar": docs_config.get("navbar"),
            "footer": docs_config.get("footer"),
        },
        sort_keys=True,
    )
    if "app.mintlify.com" in navbar_dump:
        errors.append("Public navbar/footer must not route ordinary users to Mintlify administration")
    if "contact@crownthrive.com" not in navbar_dump:
        errors.append("CrownThrive support contact is missing from navbar/footer configuration")

    for path in iter_text_files(root):
        stats["text_files_scanned"] += 1
        relative = path.relative_to(root)
        try:
            text = read_text(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        if relative not in ALLOWED_TEMPLATE_NOTICE_PATHS:
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"Possible {label} exposed in {relative}")

    internal_link_pattern = re.compile(r"(?:href=[\"']|\]\()(/[^\"')\s]+)")
    for path in mdx_files:
        text = read_text(path)
        for match in internal_link_pattern.finditer(text):
            target = match.group(1)
            if target.startswith("//"):
                continue
            target_path = target.split("#", 1)[0].split("?", 1)[0]
            if not target_path or target_path == "/":
                continue
            stats["internal_links_checked"] += 1
            target_file = normalized_page_file(root, target_path)
            if not target_file.is_file():
                errors.append(
                    f"Broken internal documentation link in {path.relative_to(root)}: {target}"
                )

    return errors, warnings, stats


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    errors, warnings, stats = validate(root)

    print("CrownThrive documentation governance validation")
    print(f"Repository: {root}")
    print(
        "Scanned "
        f"{stats['navigation_pages']} navigation entries, "
        f"{stats['mdx_pages']} MDX files, "
        f"{stats['text_files_scanned']} text files, and "
        f"{stats['internal_links_checked']} internal links."
    )

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"FAILED with {len(errors)} error(s) and {len(warnings)} warning(s).")
        return 1

    print(f"PASSED with {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
