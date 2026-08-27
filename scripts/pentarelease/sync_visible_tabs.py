#!/usr/bin/env python3
"""Incrementally synchronize PentaRelease metadata into GitHub-visible repository tabs.

This tool never rewrites unmanaged tab content. It owns one delimited managed block
inside each configured existing surface and fails closed if a configured surface is
missing or the release record is incomplete.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_START = "<!-- pentarelease:managed-release-surface:start -->"
DEFAULT_END = "<!-- pentarelease:managed-release-surface:end -->"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def strip_managed_block(text: str, start: str, end: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.S)
    return pattern.sub("", text).rstrip()


def upsert_managed_block(text: str, block: str, start: str, end: str) -> str:
    base = strip_managed_block(text, start, end)
    managed = f"{start}\n{block.rstrip()}\n{end}"
    return base + ("\n\n" if base else "") + managed + "\n"


def require_release_record(record: dict[str, Any]) -> None:
    required = ("tag", "official_release_url", "title", "why", "what_changed", "payload_costs", "cie_score")
    missing = [key for key in required if key not in record]
    if missing:
        raise RuntimeError(f"release record missing required fields: {', '.join(missing)}")


def release_block(label: str, record: dict[str, Any]) -> str:
    cost = record.get("payload_costs") or {}
    cie = record.get("cie_score") or {}
    direct_cost = cost.get("direct_cost_usd")
    cie_score = cie.get("score")
    return f"""## Latest PentaRelease — {record['tag']}

- **Surface:** {label}
- **Official release:** {record['official_release_url']}
- **Release title:** {record['title']}
- **Why:** {record['why']}
- **Changed paths:** {len(record.get('what_changed') or [])}
- **Direct USD execution cost:** {direct_cost if direct_cost is not None else 'not available'}
- **Cost status:** `{cost.get('status') or 'not_available'}`
- **CIE score:** {cie_score if cie_score is not None else 'not available'}
- **CIE status:** `{cie.get('status') or 'not_available'}`

This block is updated incrementally by PentaRelease. Content outside the managed markers is preserved and is not rewritten by release synchronization.
"""


def synchronize(repo_root: Path, config: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    if not config.get("enabled", True):
        raise RuntimeError("visible-tab synchronization is disabled")
    if config.get("mode") != "managed_blocks_only":
        raise RuntimeError("visible-tab synchronization must use managed_blocks_only")
    require_release_record(record)

    start = str(config.get("managed_block_start") or DEFAULT_START)
    end = str(config.get("managed_block_end") or DEFAULT_END)
    surfaces = list(config.get("surfaces") or [])
    if not surfaces:
        raise RuntimeError("no visible tab surfaces configured")

    state: dict[str, Any] = {
        "schema": "ct.pentarelease.visible-tabs-state.v1",
        "release": record["tag"],
        "official_release_url": record["official_release_url"],
        "updated_at": now_utc(),
        "mode": "managed_blocks_only",
        "surfaces": {},
    }

    for surface in surfaces:
        path = str(surface["path"])
        label = str(surface.get("label") or Path(path).stem)
        target = repo_root / path
        if not target.is_file():
            if config.get("fail_closed_on_missing_surface", True):
                raise RuntimeError(f"configured visible tab surface missing: {path}")
            continue

        before = target.read_text(encoding="utf-8")
        after = upsert_managed_block(before, release_block(label, record), start, end)
        target.write_text(after, encoding="utf-8")
        state["surfaces"][path] = {
            "label": label,
            "release": record["tag"],
            "preserved_unmanaged_content": True,
            "changed": before != after,
        }

    state_file = Path((config.get("reconciliation") or {}).get("state_file") or ".pentarelease/state/visible-tabs.json")
    write_json(repo_root / state_file, state)
    return state


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=".pentarelease/visible-tabs.json")
    ap.add_argument("--release-record", required=True)
    ap.add_argument("--repo-root", default=".")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    config = read_json(root / args.config)
    record = read_json(Path(args.release_record))
    state = synchronize(root, config, record)
    print(json.dumps({
        "status": "synchronized",
        "release": state["release"],
        "surface_count": len(state["surfaces"]),
        "changed_count": sum(1 for item in state["surfaces"].values() if item["changed"]),
        "mode": state["mode"],
    }, indent=2))


if __name__ == "__main__":
    main()
