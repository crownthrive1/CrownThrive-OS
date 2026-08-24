#!/usr/bin/env bash
set -euo pipefail

umask 077

RUNNER_ROOT="${CT_AGENT_WALLET_HOME:-$HOME/.local/share/crownthrive/chlom-agent-wallet}"
STATE_DIR="$RUNNER_ROOT/state"
CONFIG_DIR="$RUNNER_ROOT/config"
ENV_FILE="$CONFIG_DIR/runtime.env"
mkdir -p "$STATE_DIR" "$CONFIG_DIR"
chmod 700 "$RUNNER_ROOT" "$STATE_DIR" "$CONFIG_DIR"

log(){ printf '[chlom-agent-wallet] %s\n' "$*"; }
die(){ printf '[chlom-agent-wallet] ERROR: %s\n' "$*" >&2; exit 1; }

if ! command -v curl >/dev/null 2>&1; then die "curl is required"; fi

if ! command -v twak >/dev/null 2>&1; then
  log "Installing Trust Wallet Agent Kit from the official installer"
  curl -fsSL https://agent-kit.trustwallet.com/install.sh | bash
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
  log "Creating a dedicated local Agent Wallet. Wallet creation output is not printed or retained."
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
  # The create response may contain sensitive recovery material. Never retain it.
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

# Load only the local wallet password and public execution configuration.
# shellcheck disable=SC1090
source "$ENV_FILE"
export TWAK_WALLET_PASSWORD

log "Deriving Base public address"
twak wallet address --chain base --json > "$STATE_DIR/base-address.json"
chmod 600 "$STATE_DIR/base-address.json"

log "Running local wallet health checks"
twak wallet status --json > "$STATE_DIR/wallet-status.json"
twak wallet balance --chain base --json > "$STATE_DIR/base-balance.json"
twak price USDC --chain base --json > "$STATE_DIR/usdc-price.json"

log "Bootstrap complete. No mnemonic/private key was written to CrownThrive source or ThriveBase."
log "Next: run bin/health.sh, then register the public Base address through the CHLOM Agent Wallet control plane."
