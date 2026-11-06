#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATIONS="$ROOT/supabase/migrations"
ENVELOPES="$ROOT/supabase/migration_lineage/provider_custody/envelopes_v6"
RECEIPT="$ROOT/supabase/migration_lineage/chlom_agent_runtime_custody_v6.json"
TMP="$(mktemp -d)"
GNUPGHOME="$TMP/gnupg"
TRANSPORT_KEY='ct-replay-custody-transport-v6'
export GNUPGHOME
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"
trap 'rm -rf "$TMP"' EXIT

hold() {
  printf 'HOLD_CHLOM_PROVIDER_CUSTODY_ASSEMBLY: %s\n' "$*" >&2
  exit 1
}

sha256_of() {
  sha256sum "$1" | awk '{print $1}'
}

verify_exact() {
  local path="$1"
  local expected_bytes="$2"
  local expected_sha="$3"
  local actual_bytes actual_sha
  [[ -f "$path" ]] || hold "missing file: $path"
  actual_bytes="$(wc -c < "$path" | tr -d ' ')"
  [[ "$actual_bytes" == "$expected_bytes" ]] || \
    hold "byte mismatch for $(basename "$path"): expected=$expected_bytes actual=$actual_bytes"
  actual_sha="$(sha256_of "$path")"
  [[ "$actual_sha" == "$expected_sha" ]] || \
    hold "SHA-256 mismatch for $(basename "$path"): expected=$expected_sha actual=$actual_sha"
}

materialize() {
  local version="$1"
  local canonical_name="$2"
  local expected_cipher_bytes="$3"
  local expected_cipher_sha="$4"
  local expected_plain_bytes="$5"
  local expected_plain_sha="$6"
  local envelope="$ENVELOPES/${version}.pgp"
  local output="$MIGRATIONS/${canonical_name}"
  local staged="$TMP/${canonical_name}"

  verify_exact "$envelope" "$expected_cipher_bytes" "$expected_cipher_sha"
  gpg --batch --yes --quiet --pinentry-mode loopback \
    --passphrase "$TRANSPORT_KEY" --decrypt "$envelope" > "$staged" 2>/dev/null || \
    hold "OpenPGP transport materialization failed for $version"
  verify_exact "$staged" "$expected_plain_bytes" "$expected_plain_sha"

  python3 - "$staged" <<'PY'
from pathlib import Path
import re
import sys
raw = Path(sys.argv[1]).read_bytes()
patterns = (
    rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    rb'\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b',
    rb'\bsbp_[A-Za-z0-9_-]{12,}\b',
    rb'\bgh[opusr]_[A-Za-z0-9_-]{20,}\b',
    rb"(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*'[^']{8,}'",
)
for pattern in patterns:
    if re.search(pattern, raw):
        raise SystemExit(f'HOLD_CREDENTIAL_LIKE_LITERAL: {pattern!r}')
PY

  cp "$staged" "$output"
}

materialize \
  '20260821022535' \
  '20260821022535_chlom_fluid_module_agent_oracle_registry_v1.sql' \
  '5202' \
  '6ffdd9ebe5eac4deccd429319092f2f31be596400a3a98eee10509884c8a681b' \
  '24867' \
  '081d1898846830b7eb954a6c25f5b9c673a4f105b6cb1599ffd192bfafc04eb8'

materialize \
  '20260821030452' \
  '20260821030452_chlom_construction_work_queue_v1.sql' \
  '4951' \
  '90c09896b6e4cd5bb156b9c331843181416472f536d5352508c85e800215fe75' \
  '16864' \
  'e7c6567c6b459996ba0d96c4807d63b9ca70093dc4f813bd11ae16e1983c9b41'

materialize \
  '20260821050436' \
  '20260821050436_agent_capability_master_suite_v1.sql' \
  '9073' \
  '317f864d8f9f926aafe0a91419c9ba042b7e7b7ea8aa332553414e106c7001a5' \
  '44773' \
  '61d7303de12b8748a8277bfbe11e5f49f6affbd398be40fde7e0e81db18ad54e'

materialize \
  '20260822193302' \
  '20260822193302_institutional_capability_runtime_v1.sql' \
  '4105' \
  '7155b2d7e33beb7620373b7ef270cf6e7992a2e1cd0ba8e41f419a8a280b5311' \
  '25676' \
  '8cae8a4e8d067bcdaa6104746b25272e38aaa8e8f0430f8aba3f5407e72b835f'

verify_exact \
  "$MIGRATIONS/20260821231328_remote_applied_lineage.sql" \
  "$(wc -c < "$MIGRATIONS/20260821231328_remote_applied_lineage.sql" | tr -d ' ')" \
  'd380b37f211cccab9af5f98381e34d125372c7783f8d90afec1d1d7bea04e85b'
verify_exact \
  "$MIGRATIONS/20260823203546_execution_builder_capability_contract_identity_v1.sql" \
  '1262' \
  '3cf1a5887757740a14aeb75e17bea093b47886fa8f89d20982b5b5456817acb8'
verify_exact \
  "$MIGRATIONS/20260823203649_execution_builder_agent_v1_0_1.sql" \
  '21980' \
  '722b86270ca57b837ffb62e91a71d673cd76d7f72cb90891cb439f2d0b8cbc5a'

rm -f \
  "$MIGRATIONS/20260821022535_remote_applied_lineage.sql" \
  "$MIGRATIONS/20260821030452_remote_applied_lineage.sql" \
  "$MIGRATIONS/20260821050436_remote_applied_lineage.sql" \
  "$MIGRATIONS/20260822193302_remote_applied_lineage.sql" \
  "$MIGRATIONS/20260823202950_execution_builder_capability_contract_identity_v1.sql" \
  "$MIGRATIONS/20260823203100_execution_builder_agent_v1_0_1.sql" \
  "$MIGRATIONS/20260823203546_remote_applied_lineage.sql" \
  "$MIGRATIONS/20260823203649_remote_applied_lineage.sql"

python3 - "$MIGRATIONS" "$RECEIPT" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import sys

migrations = Path(sys.argv[1])
receipt_path = Path(sys.argv[2])
contracts = [
    ('20260821022535','chlom_fluid_module_agent_oracle_registry_v1','20260821022535_chlom_fluid_module_agent_oracle_registry_v1.sql'),
    ('20260821030452','chlom_construction_work_queue_v1','20260821030452_chlom_construction_work_queue_v1.sql'),
    ('20260821050436','agent_capability_master_suite_v1','20260821050436_agent_capability_master_suite_v1.sql'),
    ('20260822193302','institutional_capability_runtime_v1','20260822193302_institutional_capability_runtime_v1.sql'),
    ('20260823203546','execution_builder_capability_contract_identity_v1','20260823203546_execution_builder_capability_contract_identity_v1.sql'),
    ('20260823203649','execution_builder_agent_v1_0_1','20260823203649_execution_builder_agent_v1_0_1.sql'),
]
points=[]
for version,name,filename in contracts:
    matches=sorted(path.name for path in migrations.glob(f'{version}_*.sql'))
    if matches != [filename]:
        raise SystemExit(f'HOLD_PROVIDER_VERSION_IDENTITY: {version}: {matches}')
    raw=(migrations/filename).read_bytes()
    points.append({
        'version':version,
        'provider_name':name,
        'path':f'supabase/migrations/{filename}',
        'bytes':len(raw),
        'sha256':hashlib.sha256(raw).hexdigest(),
    })
if list(migrations.glob('20260823203100_*.sql')):
    raise SystemExit('HOLD_NONPROVIDER_EXECUTION_BUILDER_VERSION_REMAINS')

receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
receipt.update({
    'source_state':'EXACT_PROVIDER_BODIES_MATERIALIZED_PREVIEW_PENDING',
    'materialized_from_head_sha':os.environ.get('GITHUB_SHA'),
    'materialization_workflow_run_id':os.environ.get('GITHUB_RUN_ID'),
    'materialized_at_utc':datetime.now(timezone.utc).isoformat(),
    'custody_points':points,
    'transport':{
        'kind':'OpenPGP symmetric compression/integrity carrier',
        'confidentiality_claimed':False,
        'provider_read_performed_outside_repository':True,
        'provider_write_performed':False,
    },
    'production_history_mutated':False,
    'production_schema_mutated':False,
    'production_data_copied':False,
    'dependent_penta_advance':'HOLD_PENDING_SECOND_FRESH_PREVIEW_PASS',
})
receipt['fresh_preview']={
    'generation':2,
    'state':'NOT_PROVISIONED',
    'project_ref':None,
    'branch_id':None,
    'with_data':False,
    'validated_head_sha':None,
    'migration_state':None,
    'topology_readback':None,
}
receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({
    'status':'PASS',
    'source_state':receipt['source_state'],
    'provider_versions':[row['version'] for row in points],
    'production_mutated':False,
    'dependent_penta_advance':receipt['dependent_penta_advance'],
},indent=2,sort_keys=True))
PY

printf 'PASS_CHLOM_PROVIDER_CUSTODY_ASSEMBLY\n'
