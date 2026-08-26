#!/usr/bin/env python3
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
manifest_path = ROOT / 'developers/manifests/chlom-agentic-foundry.v1.json'
contract_path = ROOT / 'developers/contracts/chlom-agentic-foundry-production.v1.json'
cert_path = ROOT / 'developers/certification/chlom-agentic-foundry-production-2026-08-24.mdx'
runbook_path = ROOT / 'developers/runbooks/chlom-agentic-foundry-production-activation.mdx'

errors = []
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
contract = json.loads(contract_path.read_text(encoding='utf-8'))
cert = cert_path.read_text(encoding='utf-8')
runbook = runbook_path.read_text(encoding='utf-8')

if manifest['system_id'] != 'ct.system.chlom-agentic-foundry.v1': errors.append('manifest system ID drift')
if contract['system_id'] != manifest['system_id']: errors.append('contract/manifest system mismatch')
if manifest['semantic_version'] != contract['version']: errors.append('version mismatch')
if manifest['production_package_state'] != 'PASS': errors.append('package must be PASS')
if manifest['runtime_activation_state'] != 'HOLD_MAINTENANCE': errors.append('runtime must remain HOLD_MAINTENANCE before live readback')
if contract['runtime_state']['activation_state'] != 'HOLD_MAINTENANCE': errors.append('contract runtime activation state drift')
if len(manifest['planes']) != 7: errors.append('expected exactly 7 planes')
if len(manifest['sidecar_classes']) != 13: errors.append('expected exactly 13 reusable sidecar classes')
if manifest['sidecar_rules']['max_depth'] != 1: errors.append('sidecar depth must be 1')
for key in ['vote_eligible','quorum_eligible','authority_inheritance','d3_allowed','external_scheduler_allowed','raw_secret_export']:
    if manifest['sidecar_rules'][key] is not False: errors.append(f'sidecar invariant must be false: {key}')
if manifest['scheduling']['external_scheduler_slots_added'] != 0: errors.append('new external scheduler slot detected')
if manifest['protected_custody']['raw_secret_export'] is not False: errors.append('raw secret export enabled')
if manifest['protected_custody']['public_body_allowed'] is not False: errors.append('protected body publication enabled')
if contract['authority']['maximum_machine_authority'] != 'D2': errors.append('machine authority ceiling drift')
if contract['authority']['d3_human_reserved'] is not True: errors.append('D3 reservation drift')
if contract['patch_contract']['candidate_apply_authorized_default'] is not False: errors.append('patch default apply must be false')
if contract['relay_contract']['new_external_task_allowed'] is not False: errors.append('new external task allowed unexpectedly')

expected_pipeline = ['OBSERVE','DIFF','CLASSIFY','BUILD_PATCH','TEST','SECURITY','ROLLBACK_PROBE','INDEPENDENT_VERIFY','APPLY_IF_AUTHORIZED','READBACK','DAIL']
if manifest['patch_pipeline'] != expected_pipeline: errors.append('manifest patch pipeline drift')
if contract['patch_contract']['pipeline'] != expected_pipeline: errors.append('contract patch pipeline drift')

for marker in [
    'PASS_PACKAGE / HOLD_MAINTENANCE_RUNTIME',
    'External scheduler slots added: 0',
    'ct.maintenance.2026-08-24.targeted-quiescence.v1',
    'chlom_agentic_foundry_control_v1',
    'ct.plugin.chlom-agentic-foundry.v1',
]:
    if marker not in cert: errors.append(f'certification missing marker: {marker}')

for marker in [
    'PASS_PRODUCTION_RUNTIME',
    'agentic_foundry_stress_test_v1',
    'D3 is always human-reserved',
    'no additional ChatGPT recurring scheduler was created',
]:
    if marker not in runbook: errors.append(f'runbook missing marker: {marker}')

for path, text in [(cert_path, cert), (runbook_path, runbook)]:
    if re.search(r'(?i)(private[_ -]?key|seed[_ -]?phrase|mnemonic|client[_ -]?secret|webhook[_ -]?secret)\s*[:=]\s*[^\s`]{8,}', text):
        errors.append(f'possible secret value in {path.relative_to(ROOT)}')

# Until a later governed runtime-certification commit intentionally changes both public artifacts,
# public docs may not claim the runtime is already active.
for text_name, text in [('certification',cert),('runbook',runbook)]:
    if 'runtime_activation_state: PASS_PRODUCTION_RUNTIME' in text or 'Live ThriveBase activation: `PASS_PRODUCTION_RUNTIME`' in text:
        errors.append(f'premature runtime activation claim in {text_name}')

if errors:
    print('FAIL_CHLOM_AGENTIC_FOUNDRY_PUBLIC')
    for error in errors: print(error)
    sys.exit(1)
print('PASS_CHLOM_AGENTIC_FOUNDRY_PUBLIC')
print('planes=7')
print('sidecar_classes=13')
print('production_package_state=PASS')
print('runtime_activation_state=HOLD_MAINTENANCE')
print('external_scheduler_slots_added=0')
print('raw_secret_export=false')
print('d3_human_reserved=true')
