# CrownThrive OS V2 — Autonomous Runtime

Version: `2.0.0`

CrownThrive OS V2 is the governed autonomous execution plane for the CrownThrive Convergent Ecosystem. It runs inside ThriveBase/Supabase rather than depending on a ChatGPT session or a founder manually triggering work.

## Production runtime

- Edge Function: `crownthrive-os-v2-runtime`
- Autonomous dispatcher: `ct-crownthrive-os-v2-dispatch` (every minute)
- Watchdog: `ct-crownthrive-os-v2-watchdog`
- Queue/evidence schema: `os_v2`
- Notification transport: `mailgun-relay-control`
- Governance posture: fail-closed; D3 remains human-reserved
- Self-approval: disabled
- Unbounded recursive spawning: disabled
- Secret persistence in receipts: prohibited

## Execution model

`pg_cron -> os_v2.dispatch_tick() -> vault-bound runtime token -> crownthrive-os-v2-runtime -> governed queue -> provider/internal adapters -> immutable receipts -> Mailgun alerts`

The runtime seeds and executes bounded work for health, recovery, scheduler reconciliation, ThriveEvergreen commerce-mesh reconciliation, institutional knowledge projection, and notification delivery. New adapters can be added behind the same task contract without changing the scheduler topology.

## Release evidence

The first autonomous scheduler execution was observed from ThriveBase itself after installation. The runtime independently processed its queue and advanced the heartbeat without a ChatGPT-triggered request. Mailgun notification delivery also returned HTTP 200 and a provider message receipt.

DAIL release event: `0dc8da8b-f059-489e-944d-0e92ecb39214`

Runtime deployed SHA-256: `862b0ba6cfb6e6f1c2b8e73431e432bcf8758d2c70be50c5c60b8963f4acab4c`

## Safety and authority

Autonomy is operational autonomy, not unrestricted institutional authority. D0-D2 work can be performed inside established policy. D3 legal, irreversible, high-consequence, or new-authority actions remain held for authorized human governance. The runtime must never manufacture a certification, entitlement, rights grant, payment authority, credential, or approval simply to make a workflow pass.
