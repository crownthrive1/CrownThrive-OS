#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER_ROOT="${CT_AGENT_WALLET_HOME:-$HOME/.local/share/crownthrive/chlom-agent-wallet}"
ENV_FILE="$RUNNER_ROOT/config/runtime.env"
POLICY_FILE="${CT_AGENT_WALLET_POLICY_FILE:-$ROOT/config/policy.base-usdc.json}"
[[ -f "$ENV_FILE" ]] || { echo '{"schema":"ct.chlom-agent-wallet-health.v2","state":"HOLD","reason":"runtime_env_missing"}'; exit 2; }
# shellcheck disable=SC1090
source "$ENV_FILE"
export TWAK_WALLET_PASSWORD
policy_validation="$(python3 "$ROOT/bin/chlom_wallet_protocol.py" validate-policy --policy "$POLICY_FILE")" || {
  printf '%s\n' "$policy_validation"
  exit 3
}
command -v twak >/dev/null 2>&1 || { echo '{"schema":"ct.chlom-agent-wallet-health.v2","state":"HOLD","reason":"twak_missing"}'; exit 2; }
auth="$(twak auth status --json)"
wallet="$(twak wallet status --json)"
address="$(twak wallet address --chain base --json)"
balance="$(twak wallet balance --chain base --json)"
price="$(twak price USDC --chain base --json)"
python3 - "$POLICY_FILE" "$policy_validation" "$auth" "$wallet" "$address" "$balance" "$price" <<'PY'
import datetime,hashlib,json,sys
policy=json.load(open(sys.argv[1]))
validation=json.loads(sys.argv[2])
names=['auth','wallet','address','balance','price']
out={}
parse_errors=[]
for name,raw in zip(names,sys.argv[3:]):
    try: out[name]=json.loads(raw)
    except Exception:
        parse_errors.append(name)
        out[name]={'parse_error':True,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
print(json.dumps({
 'schema':'ct.chlom-agent-wallet-health.v2',
 'state':'PASS' if not parse_errors else 'HOLD',
 'execution_state':'READ_ONLY_SIMULATION_READY' if not parse_errors else 'READBACK_INVALID',
 'environment':'production',
 'primary_chain':'base',
 'chain_id':8453,
 'primary_asset':'USDC',
 'policy_id':policy['policy_id'],
 'policy_sha256':validation['policy_sha256'],
 'continuity_profile_id':policy['continuity_boundary']['profile_id'],
 'continuity_state':policy['continuity_boundary']['state'],
 'capabilities':policy['capabilities'],
 'exact_ecac_required':policy['authority']['exact_ecac_required'],
 'max_unattended_value_minor':policy['execution']['max_unattended_value_minor'],
 'signing_material_exported':False,
 'parse_errors':parse_errors,
 'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'readback':out
},sort_keys=True,separators=(',',':')))
PY
