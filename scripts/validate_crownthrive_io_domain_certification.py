#!/usr/bin/env python3
"""Validate fail-closed crownthrive.io domain/deployment certification manifest."""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'developers/manifests/crownthrive-io-domain-deployment-certification.v1.json'
HEX64=re.compile(r'^[0-9a-f]{64}$')

def main()->int:
    m=json.loads(MANIFEST.read_text(encoding='utf-8'))
    errors=[]
    snap=m['source_snapshot']
    if snap['domain_count']!=12 or snap['inventory_complete'] is not True:
        errors.append('provider inventory must remain exact 12/complete')
    if not HEX64.match(snap['inventory_sha256']):
        errors.append('inventory digest must be SHA-256')
    targets=m['commercial_site_targets']
    if {x['hostname'] for x in targets}!={'launch.crownthrive.com','ready.crownthrive.com','procure.crownthrive.com'}:
        errors.append('commercial target set drift')
    for t in targets:
        if t['provider_anonymous_http_state']!='401_sign_in_required':
            errors.append(f"{t['hostname']}: anonymous provider state drift")
        if t['dns_state']!='unresolved':
            errors.append(f"{t['hostname']}: unresolved DNS HOLD changed without evidence")
        if t['provider_dns_target'] is not None or t['provider_dns_record_type'] is not None:
            errors.append(f"{t['hostname']}: provider DNS target must not be invented")
        if t['canonical_route_state']!='unverified':
            errors.append(f"{t['hostname']}: canonical route must remain unverified")
    ctl=m['provider_control_state']
    if ctl['dns_mutation_authorized'] or ctl['force_https_mutation_authorized'] or ctl['provider_write_executed']:
        errors.append('provider mutation must remain fail-closed')
    for key in ('cpanel_api_adapter','ftps_adapter'):
        a=ctl[key]
        if a['write_canary_state']!='unverified' or a['read_after_write_state']!='unverified':
            errors.append(f'{key}: write/readback must remain unverified')
        if a['supports_rollback'] or a['supports_read_after_write']:
            errors.append(f'{key}: unsupported provider authority drift')
    if m['state']!='HOLD_CURRENT_READBACK_AND_PROVIDER_WRITE_CERTIFICATION_PENDING':
        errors.append('certification must remain HOLD')
    if m['phase_3_advancement']:
        errors.append('Phase 3 advancement prohibited')
    if errors:
        for e in errors: print('ERROR:',e)
        return 1
    print('PASS_CROWNTHRIVE_IO_DOMAIN_CERTIFICATION_CONTRACT')
    print('domains=12 commercial_targets=3 dns_mutations=0 provider_writes=0')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
