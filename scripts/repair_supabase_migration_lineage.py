#!/usr/bin/env python3
"""Materialize safe Git/Supabase migration timestamp parity without publishing protected historical SQL."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

MIGRATION_DIR = Path("supabase/migrations")
LINEAGE_DIR = Path("supabase/migration_lineage")
VERSIONS_DIR = LINEAGE_DIR / "remote_versions"
LEGACY_DIR = LINEAGE_DIR / "legacy_local_timestamp_drift"
ROLLBACK_REF = "97f9d9b993e8d80f29b0ec73f290aef44960f3ab"
EXPECTED_REMOTE_COUNT = 991
CANONICAL_RE = re.compile(r"^(\d{14})_(.+)\.sql$")

RISK_ROWS = [
    ["20260822055806", "chlom_wallet_stripe_controlled_webhook_v1", ["known_token_prefix", "vault_literal_create"]],
    ["20260822075132", "chlom_wallet_phase_c_proof_settlement_portability_v1", ["known_token_prefix"]],
    ["20260822173027", "project_issue_routing_score_vault_custody_v2", ["vault_literal_create"]],
    ["20260822173829", "chlom_wallet_institutionalization_engine_v1", ["known_token_prefix"]],
    ["20260822185903", "chlom_wallet_institutionalization_package_runtime_v2", ["known_token_prefix"]],
    ["20260822192348", "chlom_wallet_institutionalization_oidc_immutable_subject_v2", ["quoted_secret_assignment"]],
    ["20260822193646", "crownthrive_interoperability_algorithms_v1", ["vault_literal_create"]],
    ["20260822202236", "create_sermon_commerce_control_plane", ["known_token_prefix"]],
    ["20260822202703", "add_sermon_membership_benefit_grants", ["known_token_prefix"]],
    ["20260822203925", "add_partner_circle_profiles_and_catalog", ["known_token_prefix"]],
    ["20260823045850", "crownthrive_services_stack_algorithms_v1", ["vault_literal_create"]],
    ["20260823194846", "thriveledger_v1_schema_core", ["known_token_prefix"]],
    ["20260823235410", "framework_production_promotion_and_cie_activation_v1", ["known_token_prefix"]],
    ["20260824014850", "thriveevergreen_autonomous_publisher_v2_production_guarded_observer", ["known_token_prefix"]],
    ["20260826045309", "reconcile_kjv_partner_terms_v1", ["known_token_prefix"]],
    ["20260826202223", "crown_connect_github_oauth_v1", ["quoted_secret_assignment", "sensitive_named_literal"]],
    ["20260826230616", "penta_context_production_v1", ["known_token_prefix"]],
    ["20260827015046", "paypal_live_app_credentials_v1", ["vault_literal_create"]],
]


def load_remote_versions() -> list[str]:
    versions: list[str] = []
    files = sorted(VERSIONS_DIR.glob("*.txt"))
    if len(files) != 4:
        raise SystemExit(f"expected four remote-version manifest shards, found {len(files)}")
    for path in files:
        for raw in path.read_text(encoding="utf-8").splitlines():
            version = raw.strip()
            if not version:
                continue
            if not re.fullmatch(r"\d{14}", version):
                raise SystemExit(f"invalid remote migration version in {path}: {version!r}")
            versions.append(version)
    if len(versions) != EXPECTED_REMOTE_COUNT:
        raise SystemExit(f"expected {EXPECTED_REMOTE_COUNT} remote versions, found {len(versions)}")
    if len(set(versions)) != EXPECTED_REMOTE_COUNT:
        raise SystemExit("duplicate remote migration version detected")
    return sorted(versions)


def unique_archive_destination(path: Path, bucket: str) -> Path:
    target_dir = LEGACY_DIR / bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    candidate = target_dir / path.name
    if not candidate.exists():
        return candidate
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return target_dir / f"{path.stem}.{digest}{path.suffix}"


def main() -> None:
    remote_versions = load_remote_versions()
    remote_set = set(remote_versions)
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)

    before_files = sorted(MIGRATION_DIR.glob("*.sql"))
    preserved: list[str] = []
    archived_local_only: list[str] = []
    archived_noncanonical: list[str] = []

    for path in before_files:
        match = CANONICAL_RE.match(path.name)
        if not match:
            destination = unique_archive_destination(path, "noncanonical")
            shutil.move(str(path), str(destination))
            archived_noncanonical.append(path.name)
            continue

        version = match.group(1)
        if version not in remote_set:
            destination = unique_archive_destination(path, "local_only_versions")
            shutil.move(str(path), str(destination))
            archived_local_only.append(path.name)
        else:
            preserved.append(path.name)

    active_by_version: dict[str, Path] = {}
    for path in sorted(MIGRATION_DIR.glob("*.sql")):
        match = CANONICAL_RE.match(path.name)
        if not match:
            raise SystemExit(f"noncanonical active migration remained after archive: {path.name}")
        version = match.group(1)
        if version in active_by_version:
            raise SystemExit(f"duplicate active migration version: {version}")
        active_by_version[version] = path

    marker_body = (
        "-- CrownThrive migration-lineage restoration marker v1\n"
        "-- This timestamp is recorded as APPLIED in production ThriveBase.\n"
        "-- Exact historical SQL is intentionally not republished from production history.\n"
        "-- Production history contains secret-like, Vault, and protected implementation patterns.\n"
        "-- Canonical applied SQL remains in supabase_migrations.schema_migrations under ThriveBase custody.\n"
        "-- This file is a no-op and exists only to restore Git/Supabase timestamp lineage parity.\n"
        "-- Clean-room reconstruction from these public markers alone is NOT certified.\n"
    )

    created: list[str] = []
    for version in remote_versions:
        if version in active_by_version:
            continue
        path = MIGRATION_DIR / f"{version}_remote_applied_lineage.sql"
        path.write_text(f"-- remote_applied_version: {version}\n{marker_body}", encoding="utf-8")
        active_by_version[version] = path
        created.append(path.name)

    active_versions = sorted(path.name[:14] for path in MIGRATION_DIR.glob("*.sql"))
    if active_versions != remote_versions:
        missing = sorted(remote_set - set(active_versions))
        extra = sorted(set(active_versions) - remote_set)
        raise SystemExit(f"lineage parity failed: missing={missing[:10]} extra={extra[:10]}")

    risk_payload = {
        "schema": "crownthrive.supabase.migration-lineage-risk-scan/v1",
        "scanned_remote_migrations": EXPECTED_REMOTE_COUNT,
        "total_recorded_sql_bytes": 10433449,
        "max_single_migration_bytes": 183801,
        "private_key_hits": 0,
        "flagged_migrations": [
            {"version": version, "name": name, "risk_categories": categories}
            for version, name, categories in RISK_ROWS
        ],
        "publication_policy": "exact_historical_sql_withheld_from_public_git; version lineage only",
    }
    (LINEAGE_DIR / "risk_scan_20260827.json").write_text(
        json.dumps(risk_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest_text = "\n".join(active_versions) + "\n"
    (LINEAGE_DIR / "active_versions_20260827.txt").write_text(manifest_text, encoding="utf-8")
    manifest_sha = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
    (LINEAGE_DIR / "active_versions_20260827.sha256").write_text(
        f"{manifest_sha}  active_versions_20260827.txt\n", encoding="utf-8"
    )

    receipt = {
        "schema": "crownthrive.supabase.migration-lineage-receipt/v1",
        "receipt_id": "ct.supabase.migration-lineage.20260827.v1",
        "remote_migration_count": EXPECTED_REMOTE_COUNT,
        "pre_repair_sql_file_count": len(before_files),
        "preserved_exact_timestamp_count": len(preserved),
        "archived_local_only_count": len(archived_local_only),
        "archived_noncanonical_count": len(archived_noncanonical),
        "created_lineage_marker_count": len(created),
        "post_repair_active_count": len(active_versions),
        "active_versions_sha256": manifest_sha,
        "remote_history_mutated": False,
        "exact_sql_published": False,
        "risk_flagged_migration_count": len(RISK_ROWS),
        "rollback_ref": ROLLBACK_REF,
        "history_policy": "append_or_supersede_never_silent_delete",
        "clean_room_rebuild_from_public_markers": "HOLD_NOT_CERTIFIED",
    }
    (LINEAGE_DIR / "receipt_20260827.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    readme = f"""# Supabase Migration Lineage Recovery

This directory records the 2026-08-27 repair of Git/Supabase migration-history drift after the canonical repository transition to `crownthrive1/CrownThrive-OS`.

## Certified facts

- Production ThriveBase recorded migration versions: **{EXPECTED_REMOTE_COUNT}**.
- SQL files present in `supabase/migrations` before repair: **{len(before_files)}**.
- Existing local migrations preserved at exact production timestamps: **{len(preserved)}**.
- Local-only timestamp-drift migrations archived append-only: **{len(archived_local_only)}**.
- Noncanonical local migration filenames archived append-only: **{len(archived_noncanonical)}**.
- Missing production timestamps materialized as public no-op lineage markers: **{len(created)}**.
- Final active timestamp parity: **{len(active_versions)} / {EXPECTED_REMOTE_COUNT}**.
- Production migration-history rows changed: **0**.

## Security boundary

Exact historical SQL was not bulk-published from ThriveBase because a bounded scan identified **{len(RISK_ROWS)}** migrations containing secret-like literals, Vault literal creation patterns, or similarly protected implementation material. The production `supabase_migrations.schema_migrations` table remains the authoritative custody location for exact applied statements.

The marker files in `supabase/migrations` are intentionally non-executable no-ops. They repair timestamp lineage for Supabase deployment/branching reconciliation without pretending protected historical SQL is safe for a public repository. Existing source migrations whose timestamps already match production remain intact.

## Rebuild boundary

A clean-room database rebuild using the public lineage markers alone is **HOLD** and is not certified. Clean-room recovery must use the protected ThriveBase recovery package / exact migration history or a separately certified sanitized schema baseline.

## Rollback

Pre-repair repository base: `{ROLLBACK_REF}`. No production database rollback is required because this repair does not mutate production migration history.
"""
    (LINEAGE_DIR / "README.md").write_text(readme, encoding="utf-8")

    print(f"REMOTE_COUNT={EXPECTED_REMOTE_COUNT}")
    print(f"PRE_REPAIR_SQL_FILE_COUNT={len(before_files)}")
    print(f"PRESERVED_EXACT_TIMESTAMP_COUNT={len(preserved)}")
    print(f"ARCHIVED_LOCAL_ONLY_COUNT={len(archived_local_only)}")
    print(f"ARCHIVED_NONCANONICAL_COUNT={len(archived_noncanonical)}")
    print(f"CREATED_LINEAGE_MARKER_COUNT={len(created)}")
    print(f"POST_REPAIR_ACTIVE_COUNT={len(active_versions)}")
    print("PARITY=PASS")


if __name__ == "__main__":
    main()
