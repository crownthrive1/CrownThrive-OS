#!/usr/bin/env python3
"""PentaMigrationLineage™ — fail-closed Git/Supabase migration-lineage verifier.

The verifier proves that the active local migration timestamp set exactly
matches the checked-in remote-version snapshot. Lineage markers must remain
comment-only. This tool never mutates the database and never treats a no-op
marker as recovered historical SQL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

CANONICAL = re.compile(r"^(\d{14})_(.+)\.sql$")


def load_remote_versions(directory: Path) -> list[str]:
    versions: list[str] = []
    for path in sorted(directory.glob("*.txt")):
        for raw in path.read_text(encoding="utf-8").splitlines():
            version = raw.strip()
            if not version:
                continue
            if not re.fullmatch(r"\d{14}", version):
                raise SystemExit(f"invalid remote migration version in {path}: {version!r}")
            versions.append(version)
    if not versions:
        raise SystemExit("remote migration manifest is empty")
    if len(versions) != len(set(versions)):
        raise SystemExit("duplicate remote migration version detected")
    return sorted(versions)


def load_active_versions(directory: Path) -> tuple[list[str], int]:
    versions: list[str] = []
    marker_count = 0
    for path in sorted(directory.glob("*.sql")):
        match = CANONICAL.fullmatch(path.name)
        if not match:
            raise SystemExit(f"noncanonical active migration filename: {path.name}")
        versions.append(match.group(1))
        if path.name.endswith("_remote_applied_lineage.sql"):
            marker_count += 1
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.strip() and not line.lstrip().startswith("--"):
                    raise SystemExit(f"executable lineage-marker content: {path}:{line_number}")
    if len(versions) != len(set(versions)):
        raise SystemExit("duplicate active migration version detected")
    return sorted(versions), marker_count


def digest_versions(versions: list[str]) -> str:
    payload = "\n".join(versions) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--migration-dir", default="supabase/migrations")
    parser.add_argument("--remote-manifest-dir", default="supabase/migration_lineage/remote_versions")
    parser.add_argument("--snapshot", default="supabase/migration_lineage/current_remote_snapshot_20260827_v3.json")
    parser.add_argument("--output", default="supabase/migration_lineage/local_parity_20260827_v3.json")
    args = parser.parse_args()

    migration_dir = Path(args.migration_dir)
    remote_dir = Path(args.remote_manifest_dir)
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))

    remote = load_remote_versions(remote_dir)
    active, marker_count = load_active_versions(migration_dir)
    if active != remote:
        missing = sorted(set(remote) - set(active))
        extra = sorted(set(active) - set(remote))
        raise SystemExit(f"migration lineage mismatch: missing={missing[:20]} extra={extra[:20]}")

    digest = digest_versions(active)
    expected_count = int(snapshot["migration_count"])
    expected_digest = str(snapshot["versions_sha256"])
    expected_last = str(snapshot["last_version"])

    if len(active) != expected_count:
        raise SystemExit(f"migration count mismatch: local={len(active)} expected={expected_count}")
    if digest != expected_digest:
        raise SystemExit(f"migration digest mismatch: local={digest} expected={expected_digest}")
    if active[-1] != expected_last:
        raise SystemExit(f"migration head mismatch: local={active[-1]} expected={expected_last}")

    evidence = {
        "schema": "ct.penta.migration-lineage-verification/v3",
        "software": "PentaMigrationLineage",
        "status": "PASS",
        "active_migration_count": len(active),
        "remote_manifest_count": len(remote),
        "lineage_marker_count": marker_count,
        "versions_sha256": digest,
        "first_version": active[0],
        "last_version": active[-1],
        "marker_executable_content": False,
        "production_history_mutated": False,
        "historical_sql_reconstruction_claimed": False,
    }
    Path(args.output).write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
