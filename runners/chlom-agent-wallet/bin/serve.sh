#!/usr/bin/env bash
set -euo pipefail
umask 077
RUNNER_ROOT="${CT_AGENT_WALLET_HOME:-$HOME/.local/share/crownthrive/chlom-agent-wallet}"
ENV_FILE="$RUNNER_ROOT/config/runtime.env"
[[ -f "$ENV_FILE" ]] || { printf '{"state":"HOLD","reason":"runtime_env_missing"}\n' >&2; exit 2; }
# shellcheck disable=SC1090
source "$ENV_FILE"
export TWAK_WALLET_PASSWORD
# Provider remains loopback-only; CHLOM protocol gates are the authority boundary.
exec twak serve --rest --host 127.0.0.1 --port "${CT_AGENT_WALLET_PORT:-8787}" --auto-lock 15 --watch --watch-interval 60s
