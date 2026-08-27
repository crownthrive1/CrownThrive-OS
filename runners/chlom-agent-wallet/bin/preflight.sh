#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
POLICY_FILE="${CT_AGENT_WALLET_POLICY_FILE:-$ROOT/config/policy.base-usdc.json}"
exec python3 "$ROOT/bin/chlom_wallet_protocol.py" preflight \
  --policy "$POLICY_FILE" \
  --chain "${1:-base}" \
  --asset "${2:-USDC}" \
  --amount-minor "${3:-0}" \
  --destination "${4:-}"
