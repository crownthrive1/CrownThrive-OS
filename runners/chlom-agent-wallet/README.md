# CHLOM Agent Wallet — Governed Runtime v2

Production runner for the CrownThrive CHLOM wallet boundary on Base mainnet with native USDC. The runner provisions and health-checks the local wallet, evaluates governed intents, produces deterministic receipts, and emits a tamper-evident DAIL/Penta-ready outbox without manufacturing authority that CHLOM has not granted.

## Current CHLOM authority state

This runner is reconciled to `ct.pack.chlom-wallet.continuity-interfaces.v2` semantic version `2.1.0`, state `PRODUCTION_PRIVATE_CONTROL_PLANE_CERTIFIED`.

Current certified boundaries remain fail-closed for provider writes, money movement, rights grants, chain broadcast, credential material return, destructive recovery, authority manufacture, and AI final authority.

Therefore this runner is production-capable now for **provisioning, observation, policy validation, simulation evaluation, evidence, idempotency, and provider health**, but it does not claim autonomous value-movement or broadcast authority.

A future transfer requires both:

1. a promoted CHLOM policy whose certified capability boundary explicitly enables money movement and chain broadcast; and
2. an exact, unexpired ECAC authorization cryptographically bound to the canonical SHA-256 hashes of the intent and active policy.

Provider success never manufactures authority, and an ECAC artifact cannot override a closed policy.

## Protocol flow

`intent -> policy/continuity validation -> exact ECAC when required -> simulation -> governed adapter -> read-after-write -> receipt -> append-only outbox`

Protocol engine: `bin/chlom_wallet_protocol.py`.

Defined contracts:

- `ct.protocol.chlom-agent-wallet.intent.v1`
- `ct.protocol.chlom-agent-wallet.authorization.v1`
- `ct.protocol.chlom-agent-wallet.receipt.v1`
- `ct.event.chlom-agent-wallet.v1`

Schemas and the protocol manifest live under `protocols/`.

## Current Penta ownership

- **CHLOM** — governance/authority boundary.
- **PentaNurture** — continuity, drift, and recovery-plan stewardship.
- **PentaStatus** — current runtime state/readback.
- **PentaCredentials** — credentials and server-binding health.
- **PentaCertify** — exact-scope certification/evidence.
- **PentaFactory / PentaBuild** — software and candidate adapters.
- **PentaTriage** — incident routing.

The current continuity record identifies the latest suite as PentaGreen lineage under the legacy `ThriveEvergreen` runtime identifier. The legacy identifier is compatibility lineage, not authority.

## Base / USDC policy

- Base mainnet: `eip155:8453`
- Native Circle USDC: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- D2 ceiling encoded for future governed use: 10 USDC
- D3: human-reserved
- Unattended value: `0` minor units
- Destination allowlist: empty/fail-closed until governed
- Simulation, read-after-write, idempotency, and compensation are mandatory for value-moving intents

## Custody boundary

The protocol engine never accepts or exports a private key or mnemonic. Wallet password material remains runner-local in protected `runtime.env`. Repository, receipts, DAIL outbox, and Supabase are prohibited signer-material destinations.

## Bootstrap

```bash
cd runners/chlom-agent-wallet
bash ./bin/bootstrap.sh
```

If `twak` is absent, bootstrap no longer performs `curl | bash`. A reviewed installer digest is mandatory:

```bash
export CHLOM_TWAK_INSTALLER_SHA256='<reviewed 64-hex sha256>'
bash ./bin/bootstrap.sh
```

Bootstrap downloads only the canonical HTTPS installer, verifies the pin, then executes the verified temporary file. Missing or mismatched hashes fail closed.

Default runtime:

```text
~/.local/share/crownthrive/chlom-agent-wallet/
├── bin/          # installed governed runtime
├── config/       # policy + local runtime.env
├── evidence/     # receipts
├── protocols/    # protocol schemas
└── state/
    ├── idempotency.json
    └── outbox/events.ndjson
```

## Preflight compatibility

The existing positional interface remains supported:

```bash
bash ./bin/preflight.sh base USDC 0
```

Any positive unattended value currently returns `HOLD`. The old hard-coded `money_movement_authorized=true` behavior is removed.

## Evaluate and execute

Validate policy:

```bash
python3 bin/chlom_wallet_protocol.py validate-policy --policy config/policy.base-usdc.json
```

Evaluate without execution:

```bash
python3 bin/chlom_wallet_protocol.py evaluate \
  --policy config/policy.base-usdc.json \
  --intent /secure/path/intent.json
```

Governed execution path:

```bash
bash ./bin/execute.sh /secure/path/intent.json /secure/path/authorization.json
```

An optional reviewed external adapter is configured by absolute executable path through `CT_AGENT_WALLET_ADAPTER`. It receives a fixed verb plus canonical JSON stdin; the protocol engine does not use shell execution or `eval`.

Adapter verbs:

- `simulate` -> JSON with `{"ok":true}` only after successful simulation.
- `broadcast` -> JSON with a valid 32-byte `tx_hash`.
- `readback` -> JSON with `{"confirmed":true}` only after authoritative confirmation.

The adapter is a provider boundary, never an authority source. Under the current CHLOM policy, a transfer cannot reach it.

## Health and service hardening

```bash
bash ./bin/health.sh
```

Health v2 validates policy before wallet readback and reports the exact continuity profile/capability map. `money_movement=false` and `chain_broadcast=false` are correct governance states, not health failures.

`systemd/chlom-agent-wallet.service` adds pre-start policy validation, loopback-only serving, strict filesystem/kernel/control-group protections, namespace/device restrictions, `NoNewPrivileges`, `MemoryDenyWriteExecute`, restricted address families, and a `0077` umask.

## Evidence / DAIL / Penta

Every first execution attempt writes a receipt, idempotency entry, and hash-chained event. Events declare `dail_eligible=true` but `remote_delivery_claimed=false`: this runner creates a deterministic local handoff contract without falsely claiming remote DAIL acknowledgement.

Current event routes: `PentaStatus`, `PentaCertify`, `PentaTriage`, and CHLOM.

## Certification

```bash
bash ./tests/run.sh
```

The suite validates shell syntax, Python compilation, JSON, current policy invariants, ECAC non-escalation, zero unattended value, transfer fail-closed behavior, adapter non-invocation under HOLD, idempotent receipts, and append-only event production.

GitHub Actions: `.github/workflows/chlom-agent-wallet-v2.yml`.

The workflow also reconciles this policy directly against `developers/reference/chlom-wallet/continuity/continuity-penta-interface-pack.v2.json`. Any future CHLOM continuity change therefore forces this runner to prove it remains aligned.

## Promotion rule

Do not flip `capabilities.money_movement` or `capabilities.chain_broadcast` in isolation. Promotion must begin with an upstream CHLOM authority/certification change, then policy reconciliation, exact PentaCertify evidence, and the normal governed release path.
