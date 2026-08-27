#!/usr/bin/env python3
"""Shared GitHub label taxonomy for PentaTagger, PentaPR, PentaMerge, and PentaCloser."""
from __future__ import annotations

import urllib.parse
from collections.abc import Iterable
from typing import Any

LABEL_SPECS: dict[str, tuple[str, str]] = {
    # Core identity and authority.
    "penta:tagged": ("5319e7", "GitHub-native PentaTagger classification read back"),
    "penta:entity:pr": ("1d76db", "Entity is a pull request"),
    "penta:entity:issue": ("1d76db", "Entity is an issue"),
    "penta:authority:tagger": ("5319e7", "PentaTagger owns semantic classification only"),
    "penta:authority:pr": ("0052cc", "PentaPR owns pull-request lifecycle classification"),
    "penta:authority:merge": ("0e8a16", "PentaMerge owns governed merge execution"),
    "penta:authority:closer": ("b60205", "PentaCloser owns terminal close execution"),
    # Risk and corridor/lane classification.
    "penta:risk:d0": ("c5def5", "D0 low-risk informational or documentation change"),
    "penta:risk:d1": ("fbca04", "D1 bounded operational change"),
    "penta:risk:d2": ("b60205", "D2 production, security, rights, money, or destructive change"),
    "penta:lane:docs": ("0075ca", "Documentation and institutional knowledge lane"),
    "penta:lane:workflow": ("6f42c1", "GitHub Actions, automation, and workflow lane"),
    "penta:lane:database": ("d93f0b", "Database, schema, migration, or RLS lane"),
    "penta:lane:provider": ("006b75", "Provider adapter, API, credential binding, or integration lane"),
    "penta:lane:security": ("b60205", "Security, authentication, credentials, or incident lane"),
    "penta:lane:commerce": ("0e8a16", "Commerce, checkout, payments, licensing, or economic lane"),
    "penta:lane:media": ("c2e0c6", "Media, music, video, television, radio, or publishing lane"),
    "penta:lane:observability": ("5319e7", "Logging, errors, reports, alerts, or telemetry lane"),
    "penta:lane:general": ("ededed", "General CrownThrive/Penta work without a narrower lane"),
    # Current and terminal lifecycle state.
    "penta:stage:open": ("1d76db", "Open issue awaiting resolution"),
    "penta:stage:review": ("1d76db", "PR awaiting PentaPR lifecycle classification"),
    "penta:stage:merge-ready": ("0e8a16", "PR is classified for governed merge"),
    "penta:stage:restack": ("fbca04", "PR requires restack or branch repair"),
    "penta:stage:nurture": ("1d76db", "PR requires additional work or evidence"),
    "penta:stage:close-candidate": ("b60205", "PR is classified as a close candidate"),
    "penta:terminal:merged": ("0e8a16", "Terminal state: merged"),
    "penta:terminal:closed": ("b60205", "Terminal state: closed without merge"),
    # Existing PentaPR disposition contract retained for compatibility.
    "penta:merge": ("0e8a16", "PentaPR disposition: merge"),
    "penta:restack": ("fbca04", "PentaPR disposition: restack"),
    "penta:nurture": ("1d76db", "PentaPR disposition: nurture"),
    "penta:close": ("b60205", "PentaPR disposition: close"),
    "penta:deadline-12h": ("5319e7", "PentaPR hard terminal deadline is active"),
    "penta:hold": ("000000", "Founder/operator hold: do not auto-merge or auto-close"),
}

ENTITY_PREFIXES = ("penta:entity:",)
RISK_PREFIXES = ("penta:risk:",)
LANE_PREFIXES = ("penta:lane:",)
STAGE_PREFIXES = ("penta:stage:",)
TERMINAL_PREFIXES = ("penta:terminal:",)
DISPOSITION_LABELS = {
    "MERGE": "penta:merge",
    "RESTACK": "penta:restack",
    "NURTURE": "penta:nurture",
    "CLOSE": "penta:close",
}
DISPOSITION_STAGE = {
    "MERGE": "penta:stage:merge-ready",
    "RESTACK": "penta:stage:restack",
    "NURTURE": "penta:stage:nurture",
    "CLOSE": "penta:stage:close-candidate",
}


def _quote(label: str) -> str:
    return urllib.parse.quote(label, safe="")


def read_labels(gh: Any, issue_number: int) -> set[str]:
    issue = gh.get(f"/repos/{gh.repo}/issues/{issue_number}")
    return {item["name"] for item in issue.get("labels", [])}


def ensure_labels(gh: Any, names: Iterable[str] | None = None) -> None:
    wanted = set(names or LABEL_SPECS)
    unknown = sorted(wanted.difference(LABEL_SPECS))
    if unknown:
        raise ValueError(f"unknown_label_specs:{','.join(unknown)}")

    existing = {
        item["name"]
        for item in gh.paginate(f"/repos/{gh.repo}/labels?per_page=100")
    }
    for name in sorted(wanted.difference(existing)):
        color, description = LABEL_SPECS[name]
        try:
            gh.post(
                f"/repos/{gh.repo}/labels",
                {"name": name, "color": color, "description": description},
            )
        except RuntimeError as exc:
            # A concurrent run may have created the same label after readback.
            text = str(exc).lower()
            if "422" not in text or (
                "already_exists" not in text
                and "already exists" not in text
            ):
                raise


def _looks_like_missing_label(exc: RuntimeError) -> bool:
    text = str(exc).lower()
    return "422" in text and (
        "validation failed" in text
        or '"code":"missing"' in text
        or "label does not exist" in text
        or "could not resolve" in text
    )


def add_labels(gh: Any, issue_number: int, labels: Iterable[str]) -> None:
    """Add labels in one provider write, bootstrapping only on a real 422.

    PentaTagger v2 enumerated the entire repository label catalog for every
    event. v3 optimistically uses the established taxonomy, then performs the
    more expensive catalog reconciliation only when GitHub proves a label is
    missing.
    """
    desired = sorted(set(labels))
    if not desired:
        return
    path = f"/repos/{gh.repo}/issues/{issue_number}/labels"
    try:
        gh.post(path, {"labels": desired})
    except RuntimeError as exc:
        if not _looks_like_missing_label(exc):
            raise
        ensure_labels(gh, desired)
        gh.post(path, {"labels": desired})


def remove_label(gh: Any, issue_number: int, label: str) -> None:
    try:
        gh.delete(f"/repos/{gh.repo}/issues/{issue_number}/labels/{_quote(label)}")
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise


def reconcile_group(
    gh: Any,
    issue_number: int,
    current: set[str],
    desired: Iterable[str],
    prefixes: tuple[str, ...],
) -> set[str]:
    desired_set = set(desired)
    managed = {name for name in current if name.startswith(prefixes)}
    for name in sorted(managed.difference(desired_set)):
        remove_label(gh, issue_number, name)
        current.discard(name)
    missing = desired_set.difference(current)
    if missing:
        add_labels(gh, issue_number, missing)
        current.update(missing)
    return current
