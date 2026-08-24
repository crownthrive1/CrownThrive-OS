#!/usr/bin/env bash
set -euo pipefail

CHAIN="${1:-base}"
ASSET="${2:-USDC}"
AMOUNT_MINOR="${3:-0}"
DESTINATION="${4:-}"
POLICY_FILE="${CT_AGENT_WALLET_POLICY_FILE:-$(cd "$(dirname "$0")/.." && pwd)/config/policy.base-usdc.json}"

python3 - "$POLICY_FILE" "$CHAIN" "$ASSET" "$AMOUNT_MINOR" "$DESTINATION" <<'PY'
import json,sys,re
policy=json.load(open(sys.argv[1]))
chain=sys.argv[2].lower()
asset=sys.argv[3].upper()
try: amount=int(sys.argv[4])
except: raise SystemExit('invalid amount_minor')
dest=sys.argv[5]
reasons=[]
if chain != policy['primary_chain']['name']: reasons.append('CHAIN_NOT_ALLOWLISTED')
if asset != policy['primary_asset']['symbol']: reasons.append('ASSET_NOT_ALLOWLISTED')
if amount < 0: reasons.append('NEGATIVE_AMOUNT')
if amount > int(policy['execution']['max_unattended_value_minor']): reasons.append('UNATTENDED_LIMIT_EXCEEDED')
if dest and not re.fullmatch(r'0x[a-fA-F0-9]{40}',dest): reasons.append('DESTINATION_INVALID')
if dest and dest.lower() not in [x.lower() for x in policy['allowlists']['destination_addresses']]: reasons.append('DESTINATION_NOT_ALLOWLISTED')
print(json.dumps({
  'schema':'ct.chlom-agent-wallet-preflight.v1',
  'decision':'PASS' if not reasons else 'HOLD',
  'chain':chain,
  'asset':asset,
  'amount_minor':amount,
  'destination':dest or None,
  'money_movement_authorized':True,
  'exact_ecac_required':True,
  'max_unattended_value_minor':policy['execution']['max_unattended_value_minor'],
  'reasons':reasons
},separators=(',',':')))
if reasons: raise SystemExit(3)
PY
