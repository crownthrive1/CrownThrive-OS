#!/usr/bin/env python3
"""Verify exact provider-applied CHLOM replay foundation custody v7."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / 'supabase' / 'migrations'
RECEIPT = ROOT / 'supabase' / 'migration_lineage' / 'chlom_replay_dependency_custody_v7.json'

EXPECTED = {
    '20260819020805': ('20260819020805_integration_control_plane_v1.sql',11270,'81e5c748802c737ed693b669a2b1aa5a1e441cb46b3beafdebaaf1885cb0bb97'),
    '20260819164517': ('20260819164517_credential_continuity_registry_v1.sql',5461,'3e6b2ac248bbd1e4e2275ac4284226e8ce813b41349e139eb25b697ff6d5283a'),
    '20260820182344': ('20260820182344_chlom_identity_foundation.sql',10263,'7ea521ea4e527d447c80b0e64bbf8e5d4383ae8b30f5ebb75a270dd1482daa62'),
    '20260821021521': ('20260821021521_chlom_modular_metaprotocol_control_plane_v1.sql',24326,'bcb74cdb9c177ea623ad97becf2b908416a86025ba57f3129501c283992c6d85'),
    '20260821021702': ('20260821021702_chlom_runtime_rpc_surface_v1.sql',5486,'34bf0a565ee72012d1b8e39a64da080dc316f213a960d005c7f3aa65a82ef6db'),
    '20260821021745': ('20260821021745_chlom_dedicated_mcp_server_scope_v1.sql',2869,'25dcb0d1f7b0287bf51680a8269bfb731c81c44b2a351628a026ebe20c8c0f8f'),
    '20260821021758': ('20260821021758_chlom_public_identity_admin_rpc_v1.sql',577,'7d80ec60c02556cda2818d949dc63b0e9a5cad00c7773fe3bca2281112367bf2'),
    '20260821022105': ('20260821022105_chlom_runtime_deployment_evidence_v1.sql',3024,'8fb7d24baa2e169c864cd387f8291f5a3db7c1db6888f8415324afbe31c70755'),
    '20260821022237': ('20260821022237_chlom_google_drive_recovery_capsule_verified_v1.sql',2134,'f9156439c56defe85340fa18cacb6f3ee44b92e833888d1c0f105a53b9db96e5'),
}

ALLOWED_SOURCE_STATES = {
    'EXACT_FOUNDATION_BODIES_MATERIALIZED_PREVIEW_PENDING',
    'FRESH_REPLAY_MIGRATIONS_PASSED_TOPOLOGY_PENDING',
    'FRESH_REPLAY_VALIDATED',
}
ALLOWED_PENTA_STATES = {
    'HOLD_PENDING_FRESH_REPLAY_AFTER_FOUNDATION_REPAIR',
    'AUTHORIZED_AFTER_FRESH_REPLAY_PASS',
    'ADVANCED_TO_DEPENDENT_VALIDATION',
}
PROHIBITED = (
    re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    re.compile(rb'\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b'),
    re.compile(rb'\bsbp_[A-Za-z0-9_-]{12,}\b'),
    re.compile(rb'\bgh[opusr]_[A-Za-z0-9_-]{20,}\b'),
)


def hold(errors: list[str]) -> None:
    print(json.dumps({'status':'HOLD','errors':errors},indent=2,sort_keys=True))
    raise SystemExit(1)


def main() -> None:
    errors: list[str] = []
    evidence: list[dict[str, object]] = []
    for version,(filename,expected_bytes,expected_sha) in EXPECTED.items():
        matches=sorted(path.name for path in MIGRATIONS.glob(f'{version}_*.sql'))
        if matches != [filename]:
            errors.append(f'provider version identity {version}: expected={[filename]} actual={matches}')
            continue
        path=MIGRATIONS/filename
        raw=path.read_bytes()
        actual_sha=hashlib.sha256(raw).hexdigest()
        if len(raw)!=expected_bytes:
            errors.append(f'byte mismatch {filename}: expected={expected_bytes} actual={len(raw)}')
        if actual_sha!=expected_sha:
            errors.append(f'SHA-256 mismatch {filename}: expected={expected_sha} actual={actual_sha}')
        for pattern in PROHIBITED:
            if pattern.search(raw):
                errors.append(f'credential-like literal in {filename}')
        evidence.append({
            'version':version,
            'path':str(path.relative_to(ROOT)),
            'bytes':len(raw),
            'sha256':actual_sha,
        })

    if not RECEIPT.exists():
        errors.append(f'receipt missing: {RECEIPT.relative_to(ROOT)}')
        receipt={}
    else:
        try:
            receipt=json.loads(RECEIPT.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            errors.append(f'invalid receipt JSON: {exc}')
            receipt={}
        if receipt.get('source_state') not in ALLOWED_SOURCE_STATES:
            errors.append(f"invalid source_state: {receipt.get('source_state')!r}")
        if receipt.get('dependent_penta_advance') not in ALLOWED_PENTA_STATES:
            errors.append(f"invalid dependent_penta_advance: {receipt.get('dependent_penta_advance')!r}")
        if receipt.get('production_history_mutated') is not False:
            errors.append('production_history_mutated must remain false')
        if receipt.get('production_schema_mutated') is not False:
            errors.append('production_schema_mutated must remain false')
        if receipt.get('production_data_copied') is not False:
            errors.append('production_data_copied must remain false')
        points=receipt.get('custody_points')
        if not isinstance(points,list) or len(points)!=9:
            errors.append('receipt must contain nine exact foundation custody points')
        else:
            by_version={str(row.get('version')):row for row in points if isinstance(row,dict)}
            if set(by_version)!=set(EXPECTED):
                errors.append('receipt foundation version set mismatch')
            for version,(filename,expected_bytes,expected_sha) in EXPECTED.items():
                row=by_version.get(version)
                if row is None:
                    continue
                if row.get('path')!=f'supabase/migrations/{filename}':
                    errors.append(f'receipt path mismatch {version}')
                if row.get('bytes')!=expected_bytes:
                    errors.append(f'receipt byte mismatch {version}')
                if row.get('sha256')!=expected_sha:
                    errors.append(f'receipt SHA mismatch {version}')

    if errors:
        hold(errors)
    print(json.dumps({
        'status':'PASS',
        'scope':'CHLOM_REPLAY_FOUNDATION_CUSTODY_V7',
        'source_state':receipt.get('source_state'),
        'dependent_penta_advance':receipt.get('dependent_penta_advance'),
        'production_mutated':False,
        'evidence':evidence,
    },indent=2,sort_keys=True))


if __name__=='__main__':
    try:
        main()
    except OSError as exc:
        hold([f'filesystem error: {exc}'])
