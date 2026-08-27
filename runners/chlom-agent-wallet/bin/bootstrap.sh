#!/usr/bin/env bash
set -euo pipefail
umask 077

SOURCE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER_ROOT="${CT_AGENT_WALLET_HOME:-$HOME/.local/share/crownthrive/chlom-agent-wallet}"
STATE_DIR="$RUNNER_ROOT/state"
CONFIG_DIR="$RUNNER_ROOT/config"
EVIDENCE_DIR="$RUNNER_ROOT/evidence"
BIN_DIR="$RUNNER_ROOT/bin"
PROTOCOL_DIR="$RUNNER_ROOT/protocols"
ENV_FILE="$CONFIG_DIR/runtime.env"
POLICY_FILE="$CONFIG_DIR/policy.base-usdc.json"
mkdir -p "$STATE_DIR" "$CONFIG_DIR" "$EVIDENCE_DIR" "$BIN_DIR" "$PROTOCOL_DIR"
chmod 700 "$RUNNER_ROOT" "$STATE_DIR" "$CONFIG_DIR" "$EVIDENCE_DIR" "$BIN_DIR" "$PROTOCOL_DIR"

log(){ printf '[chlom-agent-wallet] %s\n' "$*"; }
die(){ printf '[chlom-agent-wallet] ERROR: %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 is required"
command -v curl >/dev/null 2>&1 || die "curl is required"
command -v sha256sum >/dev/null 2>&1 || die "sha256sum is required"

# Install the CrownThrive protocol runtime into the persistent runner. No secrets
# are copied from source control; runtime.env remains local-only.
install -m 700 "$SOURCE_ROOT/bin/chlom_wallet_protocol.py" "$BIN_DIR/chlom_wallet_protocol.py"
install -m 700 "$SOURCE_ROOT/bin/preflight.sh" "$BIN_DIR/preflight.sh"
install -m 700 "$SOURCE_ROOT/bin/execute.sh" "$BIN_DIR/execute.sh"
install -m 700 "$SOURCE_ROOT/bin/health.sh" "$BIN_DIR/health.sh"
install -m 700 "$SOURCE_ROOT/bin/serve.sh" "$BIN_DIR/serve.sh"
install -m 600 "$SOURCE_ROOT/config/policy.base-usdc.json" "$POLICY_FILE"
install -m 600 "$SOURCE_ROOT"/protocols/*.json "$PROTOCOL_DIR/"

python3 "$BIN_DIR/chlom_wallet_protocol.py" validate-policy --policy "$POLICY_FILE" > "$STATE_DIR/policy-validation.json"
chmod 600 "$STATE_DIR/policy-validation.json"

if ! command -v twak >/dev/null 2>&1; then
  installer_url="${CHLOM_TWAK_INSTALLER_URL:-https://agent-kit.trustwallet.com/install.sh}"
  installer_sha="${CHLOM_TWAK_INSTALLER_SHA256:-}"
  [[ "$installer_url" == "https://agent-kit.trustwallet.com/install.sh" ]] || die "non-canonical installer URL rejected"
  [[ "$installer_sha" =~ ^[a-fA-F0-9]{64}$ ]] || die "CHLOM_TWAK_INSTALLER_SHA256 must pin the installer before bootstrap can install twak"
  tmp_installer="$(mktemp)"
  trap 'rm -f "$tmp_installer"' EXIT
  log "Downloading pinned Trust Wallet Agent Kit installer"
  curl --proto '=https' --tlsv1.2 -fsSL "$installer_url" -o "$tmp_installer"
  actual_sha="$(sha256sum "$tmp_installer" | awk '{print $1}')"
  [[ "${actual_sha,,}" == "${installer_sha,,}" ]] || die "Trust Wallet installer SHA-256 mismatch"
  chmod 700 "$tmp_installer"
  "$tmp_installer"
  rm -f "$tmp_installer"
  trap - EXIT
fi
command -v twak >/dev/null 2>&1 || die "twak was not installed into PATH"

if ! twak auth status --json >/dev/null 2>&1; then
  log "Trust Wallet API authentication is not configured on this runner."
  read -r -p 'Trust Wallet Access ID: ' TWAK_ACCESS_ID_INPUT
  read -r -s -p 'Trust Wallet HMAC Secret: ' TWAK_HMAC_SECRET_INPUT
  printf '\n'
  [[ -n "$TWAK_ACCESS_ID_INPUT" && -n "$TWAK_HMAC_SECRET_INPUT" ]] || die "credentials are required"
  twak auth setup --api-key "$TWAK_ACCESS_ID_INPUT" --api-secret "$TWAK_HMAC_SECRET_INPUT" >/dev/null
  unset TWAK_ACCESS_ID_INPUT TWAK_HMAC_SECRET_INPUT
fi

twak auth status --json > "$STATE_DIR/auth-status.json"
chmod 600 "$STATE_DIR/auth-status.json"

if ! twak wallet status --json > "$STATE_DIR/wallet-status.json" 2>/dev/null; then
  : > "$STATE_DIR/wallet-status.json"
fi

if ! grep -Eiq 'created|ready|unlocked|locked|address|wallet' "$STATE_DIR/wallet-status.json"; then
  log "Creating dedicated local Agent Wallet; recovery material is never retained by bootstrap."
  read -r -s -p 'Create a strong Agent Wallet password: ' WALLET_PASSWORD_1
  printf '\n'
  read -r -s -p 'Confirm Agent Wallet password: ' WALLET_PASSWORD_2
  printf '\n'
  [[ "$WALLET_PASSWORD_1" == "$WALLET_PASSWORD_2" ]] || die "wallet passwords do not match"
  [[ ${#WALLET_PASSWORD_1} -ge 16 ]] || die "wallet password must be at least 16 characters"
  export TWAK_WALLET_PASSWORD="$WALLET_PASSWORD_1"
  TMP_CREATE="$(mktemp "$STATE_DIR/.wallet-create.XXXXXX")"
  chmod 600 "$TMP_CREATE"
  twak wallet create --json > "$TMP_CREATE"
  if command -v shred >/dev/null 2>&1; then shred -u "$TMP_CREATE"; else rm -f "$TMP_CREATE"; fi
  {
    printf 'TWAK_WALLET_PASSWORD=%q\n' "$WALLET_PASSWORD_1"
    printf 'CT_AGENT_WALLET_PRIMARY_CHAIN=base\n'
    printf 'CT_AGENT_WALLET_CHAIN_ID=8453\n'
    printf 'CT_AGENT_WALLET_PRIMARY_ASSET=USDC\n'
    printf 'CT_AGENT_WALLET_USDC_CONTRACT=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913\n'
    printf 'CT_AGENT_WALLET_MAX_UNATTENDED_VALUE_MINOR=0\n'
  } > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  unset WALLET_PASSWORD_1 WALLET_PASSWORD_2 TWAK_WALLET_PASSWORD
fi

[[ -f "$ENV_FILE" ]] || die "runtime.env missing after wallet setup"
# shellcheck disable=SC1090
source "$ENV_FILE"
export TWAK_WALLET_PASSWORD

log "Deriving Base public address and collecting read-only evidence"
twak wallet address --chain base --json > "$STATE_DIR/base-address.json"
twak wallet status --json > "$STATE_DIR/wallet-status.json"
twak wallet balance --chain base --json > "$STATE_DIR/base-balance.json"
twak price USDC --chain base --json > "$STATE_DIR/usdc-price.json"
chmod 600 "$STATE_DIR"/*.json

log "Running governed health check"
"$BIN_DIR/health.sh" > "$STATE_DIR/health.json"
chmod 600 "$STATE_DIR/health.json"

log "Bootstrap complete: CHLOM wallet is provisioned with current certified value-movement/broadcast boundary fail-closed."
log "No mnemonic/private key was written to CrownThrive source, the evidence outbox, or Supabase."
