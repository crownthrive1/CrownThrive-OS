# PentaBind Runtime Skill

## Ownership

Bounded **PentaBind™** capability for production binding reconciliation. It does not grant credentials or elevate provider authority.

## Purpose

Keep non-secret provider bindings synchronized between CrownThrive OS manifests, ThriveBase runtime metadata, and authorized consumers.

## Deterministic sequence

1. Read canonical binding metadata and consumer identity.
2. Resolve only secret references; never read or emit secret values.
3. Verify the intended provider, runtime, and consumer boundary.
4. Route live binding changes through the hot route and scheduled drift checks through the cold route.
5. Require authoritative provider readback before declaring a binding active.
6. Emit a non-secret receipt through PentaAudit.
7. Hand provider denial to PentaBound/PentaRetry without weakening governance.

## Hard boundaries

- No plaintext credential export.
- No secret logging.
- No provider permission manufacture.
- No D3 self-approval.
- No PASS without readback.

## Output

Return binding ID, provider, consumer, runtime, secret reference, route class, observed provider state, and receipt identity.
