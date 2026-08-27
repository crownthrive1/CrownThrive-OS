# PentaVault Runtime Skill

## Ownership

Bounded **PentaVault™** capability for credential custody verification. It verifies references and custody state without surfacing secret material.

## Purpose

Keep credential custody machine-aware across ThriveBase Vault and protected provider secret stores while enforcing zero-secret repository exposure.

## Deterministic sequence

1. Read the canonical credential reference and intended consumer.
2. Verify custody metadata and allowed runtime destination.
3. Confirm that repository/source manifests contain references only.
4. Route live custody changes through PentaBind and scheduled audits through the cold route.
5. Mark missing, stale, unauthorized, or inaccessible custody as HOLD.
6. Emit non-secret audit evidence through PentaAudit.

## Hard boundaries

- Never print, serialize, commit, echo, or return a secret value.
- Never treat a secret reference as proof that a provider accepts the credential.
- Never bypass provider authentication or authorization controls.
- Never self-certify D3.

## Output

Return credential ID, vault reference, consumer, custody state, verification state, reason code, and receipt identity.
