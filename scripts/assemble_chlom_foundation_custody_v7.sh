#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATIONS="$ROOT/supabase/migrations"
ENVELOPE="$ROOT/supabase/migration_lineage/provider_custody/foundation_v7/20260819_20260821_foundation_bundle.pgp"
RECEIPT="$ROOT/supabase/migration_lineage/chlom_replay_dependency_custody_v7.json"
TMP="$(mktemp -d)"
GNUPGHOME="$TMP/gnupg"
TRANSPORT_KEY='ct-replay-custody-foundation-v7'
export GNUPGHOME
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"
trap 'rm -rf "$TMP"' EXIT

hold() {
  printf 'HOLD_CHLOM_FOUNDATION_CUSTODY: %s\n' "$*" >&2
  exit 1
}

sha256_of() {
  sha256sum "$1" | awk '{print $1}'
}

[[ -f "$ENVELOPE" ]] || hold "foundation carrier missing"
[[ "$(wc -c < "$ENVELOPE" | tr -d ' ')" == '13746' ]] || hold "foundation carrier byte mismatch"
[[ "$(sha256_of "$ENVELOPE")" == 'f5b3fda1b13bf739fb23518afe6bfe0af01d8695558b3f53db3a3611a882be42' ]] || \
  hold "foundation carrier SHA-256 mismatch"

gpg --batch --yes --quiet --pinentry-mode loopback \
  --passphrase "$TRANSPORT_KEY" --decrypt "$ENVELOPE" > "$TMP/foundation.json" 2>/dev/null || \
  hold "foundation carrier materialization failed"

[[ "$(wc -c < "$TMP/foundation.json" | tr -d ' ')" == '67823' ]] || hold "foundation payload byte mismatch"
[[ "$(sha256_of "$TMP/foundation.json")" == '8a1aa0c6c39221b9bcd35aab6cd10dbb011ca9ccf71235b0d6288126ecad1846' ]] || \
  hold "foundation payload SHA-256 mismatch"

python3 - "$TMP/foundation.json" "$MIGRATIONS" "$RECEIPT" <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import sys

payload_path = Path(sys.argv[1])
migrations_dir = Path(sys.argv[2])
receipt_path = Path(sys.argv[3])

expected = {
    '20260819020805': {
        'name': 'integration_control_plane_v1',
        'file': '20260819020805_integration_control_plane_v1.sql',
        'bytes': 11270,
        'sha256': '81e5c748802c737ed693b669a2b1aa5a1e441cb46b3beafdebaaf1885cb0bb97',
    },
    '20260819164517': {
        'name': 'credential_continuity_registry_v1',
        'file': '20260819164517_credential_continuity_registry_v1.sql',
        'bytes': 5461,
        'sha256': '3e6b2ac248bbd1e4e2275ac4284226e8ce813b41349e139eb25b697ff6d5283a',
    },
    '20260820182344': {
        'name': 'chlom_identity_foundation',
        'file': '20260820182344_chlom_identity_foundation.sql',
        'bytes': 10263,
        'sha256': '7ea521ea4e527d447c80b0e64bbf8e5d4383ae8b30f5ebb75a270dd1482daa62',
    },
    '20260821021521': {
        'name': 'chlom_modular_metaprotocol_control_plane_v1',
        'file': '20260821021521_chlom_modular_metaprotocol_control_plane_v1.sql',
        'bytes': 24326,
        'sha256': 'bcb74cdb9c177ea623ad97becf2b908416a86025ba57f3129501c283992c6d85',
    },
    '20260821021702': {
        'name': 'chlom_runtime_rpc_surface_v1',
        'file': '20260821021702_chlom_runtime_rpc_surface_v1.sql',
        'bytes': 5486,
        'sha256': '34bf0a565ee72012d1b8e39a64da080dc316f213a960d005c7f3aa65a82ef6db',
    },
    '20260821021745': {
        'name': 'chlom_dedicated_mcp_server_scope_v1',
        'file': '20260821021745_chlom_dedicated_mcp_server_scope_v1.sql',
        'bytes': 2869,
        'sha256': '25dcb0d1f7b0287bf51680a8269bfb731c81c44b2a351628a026ebe20c8c0f8f',
    },
    '20260821021758': {
        'name': 'chlom_public_identity_admin_rpc_v1',
        'file': '20260821021758_chlom_public_identity_admin_rpc_v1.sql',
        'bytes': 577,
        'sha256': '7d80ec60c02556cda2818d949dc63b0e9a5cad00c7773fe3bca2281112367bf2',
    },
    '20260821022105': {
        'name': 'chlom_runtime_deployment_evidence_v1',
        'file': '20260821022105_chlom_runtime_deployment_evidence_v1.sql',
        'bytes': 3024,
        'sha256': '8fb7d24baa2e169c864cd387f8291f5a3db7c1db6888f8415324afbe31c70755',
    },
    '20260821022237': {
        'name': 'chlom_google_drive_recovery_capsule_verified_v1',
        'file': '20260821022237_chlom_google_drive_recovery_capsule_verified_v1.sql',
        'bytes': 2134,
        'sha256': 'f9156439c56defe85340fa18cacb6f3ee44b92e833888d1c0f105a53b9db96e5',
    },
}

prohibited = (
    re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    re.compile(rb'\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b'),
    re.compile(rb'\bsbp_[A-Za-z0-9_-]{12,}\b'),
    re.compile(rb'\bgh[opusr]_[A-Za-z0-9_-]{20,}\b'),
    re.compile(rb"(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*'[^']{8,}'"),
)

payload = json.loads(payload_path.read_text(encoding='utf-8'))
if payload.get('schema') != 'crownthrive.supabase.provider-custody-bundle/v1':
    raise SystemExit('HOLD_FOUNDATION_BUNDLE_SCHEMA')
if payload.get('project_ref') != 'tzajnzshmtzjenqulehq':
    raise SystemExit('HOLD_FOUNDATION_BUNDLE_PROJECT_REF')
rows = payload.get('migrations')
if not isinstance(rows, list):
    raise SystemExit('HOLD_FOUNDATION_BUNDLE_ROWS')
by_version = {str(row.get('version')): row for row in rows if isinstance(row, dict)}
if set(by_version) != set(expected):
    raise SystemExit(
        f"HOLD_FOUNDATION_VERSION_SET: expected={sorted(expected)} actual={sorted(by_version)}"
    )

points = []
for version, contract in expected.items():
    row = by_version[version]
    if row.get('name') != contract['name']:
        raise SystemExit(f'HOLD_FOUNDATION_NAME_DRIFT: {version}: {row.get("name")!r}')
    sql_text = row.get('sql_text')
    if not isinstance(sql_text, str):
        raise SystemExit(f'HOLD_FOUNDATION_BODY_MISSING: {version}')
    raw = sql_text.encode('utf-8')
    actual_sha = hashlib.sha256(raw).hexdigest()
    if len(raw) != contract['bytes']:
        raise SystemExit(
            f"HOLD_FOUNDATION_BYTE_DRIFT: {version}: expected={contract['bytes']} actual={len(raw)}"
        )
    if actual_sha != contract['sha256']:
        raise SystemExit(
            f"HOLD_FOUNDATION_SHA_DRIFT: {version}: expected={contract['sha256']} actual={actual_sha}"
        )
    for pattern in prohibited:
        if pattern.search(raw):
            raise SystemExit(f'HOLD_FOUNDATION_CREDENTIAL_LITERAL: {version}')
    path = migrations_dir / contract['file']
    path.write_bytes(raw)
    points.append({
        'version': version,
        'provider_name': contract['name'],
        'path': f"supabase/migrations/{contract['file']}",
        'bytes': len(raw),
        'sha256': actual_sha,
    })

for version, contract in expected.items():
    for path in migrations_dir.glob(f'{version}_*.sql'):
        if path.name != contract['file']:
            path.unlink()
    matches = sorted(path.name for path in migrations_dir.glob(f'{version}_*.sql'))
    if matches != [contract['file']]:
        raise SystemExit(
            f"HOLD_FOUNDATION_IDENTITY_NOT_UNIQUE: {version}: {matches}"
        )

receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
receipt.update({
    'source_state': 'EXACT_FOUNDATION_BODIES_MATERIALIZED_PREVIEW_PENDING',
    'materialized_from_head_sha': os.environ.get('GITHUB_SHA'),
    'materialization_workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
    'materialized_at_utc': datetime.now(timezone.utc).isoformat(),
    'custody_points': points,
    'production_history_mutated': False,
    'production_schema_mutated': False,
    'production_data_copied': False,
    'dependent_penta_advance': 'HOLD_PENDING_FRESH_REPLAY_AFTER_FOUNDATION_REPAIR',
})
receipt_path.write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8'
)
print(json.dumps({
    'status': 'PASS',
    'provider_versions': sorted(expected),
    'source_state': receipt['source_state'],
    'dependent_penta_advance': receipt['dependent_penta_advance'],
    'production_mutated': False,
}, indent=2, sort_keys=True))
PY

printf 'PASS_CHLOM_FOUNDATION_CUSTODY\n'
