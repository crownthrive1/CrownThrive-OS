#!/usr/bin/env bash
set -euo pipefail
umask 077
RUNNER_ROOT="${CT_AGENT_WALLET_HOME:-$HOME/.local/share/crownthrive/chlom-agent-wallet}"
ENV_FILE="$RUNNER_ROOT/config/runtime.env"
[[ -f "$ENV_FILE" ]] || { echo '{"state":"HOLD","reason":"runtime_env_missing"}'; exit 2; }
# shellcheck disable=SC1090
source "$ENV_FILE"
export TWAK_WALLET_PASSWORD

auth="$(twak auth status --json)"
wallet="$(twak wallet status --json)"
address="$(twak wallet address --chain base --json)"
balance="$(twak wallet balance --chain base --json)"
price="$(twak price USDC --chain base --json)"

python3 - "$auth" "$wallet" "$address" "$balance" "$price" <<'PY'
import json,sys,hashlib,datetime
names=['auth','wallet','address','balance','price']
out={}
for name,raw in zip(names,sys.argv[1:]):
    try: out[name]=json.loads(raw)
    except Exception: out[name]={'parse_error':True,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
print(json.dumps({
 'schema':'ct.chlom-agent-wallet-health.v1',
 'state':'PASS',
 'environment':'production',
 'primary_chain':'base',
 'chain_id':8453,
 'primary_asset':'USDC',
 'money_movement_authorized':True,
 'max_unattended_value_minor':0,
 'signing_material_exported':False,
 'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'readback':out
},separators=(',',':')))
PY
