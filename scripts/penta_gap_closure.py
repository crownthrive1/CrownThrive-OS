#!/usr/bin/env python3
"""Fail closed on unmanaged retired institutional phase aliases.

Historical evidence is preserved. Every surviving decimal-phase reference must
match an exact governed path and expected hit count so new or changed usage
cannot silently become current instruction. A registry entry whose retired alias
has been removed from source is safe cleanup debt: it remains visible as
STALE_REGISTRATION but does not block merge.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

try:
    from scripts import build_substantive_rebuild_wave1 as substantive_wave1
    from scripts import pentadocs_quality
except ImportError:  # Direct execution places scripts/ itself on sys.path.
    import build_substantive_rebuild_wave1 as substantive_wave1
    import pentadocs_quality

RETIRED = re.compile(
    r"\bPhase(?:(?:\*\*)?[ \t]*:[ \t]*(?:\*\*)?[ \t]*|[ \t]+)"
    r"2\.(?:5|7|8|9|95|97|98|99)\b",
    re.I,
)
CURRENT_STALE = re.compile(
    r"(?:"
    r"(?:current institutional phase|phase remains|remains current|current state)"
    r"[^\n]{0,100}Phase\s+2\.(?:5|7|8|9|95|97|98|99)"
    r"|^[ \t]*(?:[-*][ \t]+)?(?:\*\*Phase:\*\*|(?:\*\*)?Phase(?:\*\*)?[ \t]*:)[ \t]*"
    r"(?:\*\*)?2\.(?:5|7|8|9|95|97|98|99)\b"
    r"|\b(?:evaluates?|evaluation)[^\n]{0,60}Phase\s+2\."
    r"(?:5|7|8|9|95|97|98|99)\b"
    r")",
    re.I | re.M,
)
HISTORICAL_HINTS = (
    "archive/",
    "changelog/",
    "historical",
    "superseded",
    "retired",
    "lineage",
    "recovery",
    "recovered",
)
TEXT_SUFFIXES = {".md", ".mdx", ".json", ".yml", ".yaml", ".py", ".sql"}
SKIP_PARTS = {".git", "__pycache__", ".venv", "venv", "node_modules"}
REGISTRY = pathlib.Path("developers/manifests/penta-phase-alias-dispositions.v1.json")
CATEGORIES = {"historical_alias_evidence", "current_record_contextual_reference"}


def classify(path: pathlib.Path, text: str) -> dict:
    rel = path.as_posix()
    profile_values: dict[str, str] = {}
    if path.suffix.lower() in {".md", ".mdx"}:
        parsed = pentadocs_quality.split_frontmatter(text)
        if parsed is not None:
            profile_values = pentadocs_quality.parse_frontmatter(parsed[0]).values
        scan_text = substantive_wave1.normalize_pentadocs_envelope(text)
    else:
        scan_text = text
    hits = [match.group(0) for match in RETIRED.finditer(scan_text)]
    stale = [match.group(0) for match in CURRENT_STALE.finditer(scan_text)]
    historical_profile = (
        profile_values.get("primary_audience") == "historical"
        or profile_values.get("content_state") in {"historical", "superseded"}
    )
    historical = historical_profile or any(
        hint in rel.lower() or hint in scan_text[:1200].lower()
        for hint in HISTORICAL_HINTS
    )
    return {
        "path": rel,
        "retired_alias_hits": len(hits),
        "stale_current_claim_hits": len(stale),
        "historical_context": historical,
    }


def load_registry(root: pathlib.Path) -> tuple[dict[str, dict], list[str]]:
    path = root / REGISTRY
    errors: list[str] = []
    if not path.is_file():
        return {}, [f"missing governed phase-alias registry: {REGISTRY}"]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, [f"invalid governed phase-alias registry: {exc}"]
    if manifest.get("schema_version") != "1.0.0":
        errors.append("phase-alias registry schema must remain 1.0.0")
    if manifest.get("owner") != "crownthrive_os_convergence":
        errors.append("phase-alias registry must retain an accountable owner")
    category_policy = manifest.get("category_policy", {})
    dispositions = manifest.get("dispositions", {})
    if set(category_policy) != CATEGORIES or set(dispositions) != CATEGORIES:
        errors.append("phase-alias registry category inventory drifted")

    expected: dict[str, dict] = {}
    for category in sorted(CATEGORIES):
        entries = dispositions.get(category, [])
        if not isinstance(entries, list):
            errors.append(f"phase-alias category must be a list: {category}")
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append(f"phase-alias entry must be an object: {category}")
                continue
            rel = entry.get("path")
            if not isinstance(rel, str) or not rel:
                errors.append(f"phase-alias entry lacks path: {category}")
                continue
            if rel in expected:
                errors.append(f"duplicate phase-alias disposition: {rel}")
                continue
            if not isinstance(entry.get("retired_alias_hits"), int) or not isinstance(
                entry.get("stale_current_claim_hits"), int
            ):
                errors.append(f"phase-alias entry lacks integer hit counts: {rel}")
                continue
            expected[rel] = {**entry, "category": category}
    return expected, errors


def scan(root: pathlib.Path) -> tuple[dict, int]:
    expected, registry_errors = load_registry(root)
    observed: dict[str, dict] = {}
    for path in root.rglob("*"):
        if (
            not path.is_file()
            or path.suffix.lower() not in TEXT_SUFFIXES
            or any(part in SKIP_PARTS for part in path.relative_to(root).parts)
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        row = classify(path.relative_to(root), text)
        if row["retired_alias_hits"]:
            observed[row["path"]] = row

    findings: list[dict] = []
    governed_counts = {category: 0 for category in CATEGORIES}
    for rel, row in sorted(observed.items()):
        registered = expected.get(rel)
        if not registered:
            findings.append(
                {**row, "disposition": "REVIEW_CONTEXT", "reason": "unregistered_alias_use"}
            )
            continue
        expected_counts = (
            registered["retired_alias_hits"],
            registered["stale_current_claim_hits"],
        )
        observed_counts = (row["retired_alias_hits"], row["stale_current_claim_hits"])
        if observed_counts != expected_counts:
            findings.append(
                {
                    **row,
                    "disposition": "REVIEW_CONTEXT",
                    "reason": "registered_hit_count_drift",
                    "expected_retired_alias_hits": expected_counts[0],
                    "expected_stale_current_claim_hits": expected_counts[1],
                }
            )
            continue
        category = registered["category"]
        if row["stale_current_claim_hits"] and category != "historical_alias_evidence":
            findings.append(
                {
                    **row,
                    "disposition": "REPAIR_REQUIRED",
                    "reason": "stale_current_claim_in_active_record",
                }
            )
            continue
        if category == "historical_alias_evidence" and not row["historical_context"]:
            findings.append(
                {
                    **row,
                    "disposition": "REPAIR_REQUIRED",
                    "reason": "historical_overlay_missing",
                }
            )
            continue
        governed_counts[category] += 1

    # A registered retired alias disappearing from source reduces legacy surface.
    # Keep it visible for registry cleanup, but never force source to re-introduce
    # obsolete language merely to satisfy an exact-count manifest.
    for rel in sorted(set(expected) - set(observed)):
        findings.append(
            {
                "path": rel,
                "disposition": "STALE_REGISTRATION",
                "reason": "registered_alias_use_no_longer_present_or_file_missing",
                "blocking": False,
            }
        )

    counts = {
        name: sum(item.get("disposition") == name for item in findings)
        for name in ("REPAIR_REQUIRED", "REVIEW_CONTEXT", "STALE_REGISTRATION")
    }
    blocking_count = counts["REPAIR_REQUIRED"] + counts["REVIEW_CONTEXT"]
    summary = {
        "service": "ct.penta.gap-closure.v2",
        "rule": "new/changed/stale-current retired phase aliases fail closed; removed registered aliases are advisory cleanup",
        "registry": REGISTRY.as_posix(),
        "observed_alias_paths": len(observed),
        "governed_counts": governed_counts,
        "counts": counts,
        "blocking_findings": blocking_count,
        "stale_registration_policy": "ADVISORY_CLEANUP",
        "registry_errors": registry_errors,
        "findings": findings,
    }
    return summary, 2 if registry_errors or blocking_count else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    summary, status = scan(pathlib.Path(args.root).resolve())
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    elif status:
        for finding in summary["findings"]:
            if finding.get("disposition") != "STALE_REGISTRATION":
                print(f"{finding['disposition']}: {finding['path']} ({finding['reason']})")
        for error in summary["registry_errors"]:
            print(f"REGISTRY_ERROR: {error}")
    else:
        print(
            "PASS: "
            f"{summary['observed_alias_paths']} retired-alias paths are exact-count governed; "
            f"{summary['counts']['STALE_REGISTRATION']} removed registrations remain advisory cleanup; "
            "no unmanaged or stale-current alias claims block the gate."
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
