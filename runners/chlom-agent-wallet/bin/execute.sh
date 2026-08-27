#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER_ROOT="${CT_AGENT_WALLET_HOME:-$HOME/.local/share/crownthrive/chlom-agent-wallet}"
POLICY_FILE="${CT_AGENT_WALLET_POLICY_FILE:-$ROOT/config/policy.base-usdc.json}"
INTENT_FILE="${1:?usage: execute.sh INTENT_JSON [AUTHORIZATION_JSON]}"
AUTH_FILE="${2:-}"
args=(execute --policy "$POLICY_FILE" --intent "$INTENT_FILE" --state-dir "$RUNNER_ROOT/state" --evidence-dir "$RUNNER_ROOT/evidence")
[[ -z "$AUTH_FILE" ]] || args+=(--authorization "$AUTH_FILE")
[[ -z "${CT_AGENT_WALLET_ADAPTER:-}" ]] || args+=(--adapter "$CT_AGENT_WALLET_ADAPTER")
exec python3 "$ROOT/bin/chlom_wallet_protocol.py" "${args[@]}"
