# CHLOM Agent Wallet Production Runner

Dedicated CrownThrive/CHLOM autonomous wallet runner using Trust Wallet Agent Kit.

## Canonical production identity

- Provider: Trust Wallet Agent Kit (`twak`)
- Wallet mode: `ct.wallet-mode.agent-wallet.autonomous.v1`
- Default chain: Base mainnet
- Default stablecoin: native USDC
- Native Base USDC contract: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- Bridged USDbC is not an approved default asset.
- Authority ceiling: D2
- D3: human-reserved
- Money movement capability: production-authorized
- Unattended execution ceiling: `0` until a separate bounded-value promotion is certified

## Custody rule

Private wallet material must remain on the persistent trusted runner. Never place mnemonic/private key/wallet password in GitHub, Supabase tables, public APIs, logs, screenshots, or ordinary ChatGPT runtime state.

The runner may report only public wallet addresses, chain IDs, public transaction hashes, health state, policy digests and secret-free receipts.

## Install

Run on a persistent Linux/macOS/WSL/Codex runner:

```bash
bash runners/chlom-agent-wallet/bin/bootstrap.sh
```

The bootstrap uses Trust Wallet's official Agent Kit installer and official CLI wallet creation flow. Credentials and wallet password are entered/stored locally; they are not embedded in this repository.

## Production activation sequence

1. Install `twak` using the official installer.
2. Authenticate with the CrownThrive Trust Wallet API credentials.
3. Create a dedicated Agent Wallet locally.
4. Save the wallet password in the OS keychain where supported.
5. Derive the Base public address.
6. Run the local health and no-value signing canaries.
7. Register only the Base public address and runner evidence with ThriveBase.
8. Keep unattended value at `0` until balance, simulation, unauthorized-sign, execution-policy and rollback/compensation certifications pass.
9. Before every economic execution, obtain exact ThriveEvergreen/CHLOM ECAC authorization for that intent.

## Files

- `bin/bootstrap.sh` — install/auth/create wallet locally.
- `bin/health.sh` — secret-free local runner/wallet health readback.
- `bin/preflight.sh` — chain/asset/policy preflight.
- `config/policy.base-usdc.json` — canonical Base + native USDC policy.
- `systemd/chlom-agent-wallet.service` — persistent runner service template.

## Safety boundaries

A quote, route, wallet signature, broadcast, provider success or transaction confirmation is evidence. It cannot independently create Crown Credits, entitlement, rights, payout truth, settlement truth or sovereign authority.

The dedicated Agent Wallet is autonomous-capable, but actual unattended transaction value remains zero until a later exact policy promotion. WalletConnect/MetaMask remain the human-approved transaction lanes.