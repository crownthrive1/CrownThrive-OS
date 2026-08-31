# COS V1 Commercialization Fabric Rollback

The commercialization fabric is additive and fail-closed. Rolling it back must not delete source manifests, historical evidence, prior releases, licenses already executed under separate authority, or settled transaction records.

## Source rollback

1. Revert the commercialization-fabric merge commit or disable `.github/workflows/cos-v1-commercialization-fabric.yml` by a reviewed change.
2. Preserve the release request, release manifest, DAIL/Penta continuity receipt, test logs, and published artifacts as historical evidence.
3. Mark generated catalog entries `RETIRED` or `HOLD`; do not silently remove them from institutional history.

## Runtime degradation

- Catalog and install resolution may remain read-only.
- New paid license acceptance, wallet authorization, settlement, and entitlement issuance must stop.
- Existing entitlements are preserved until CHLOM reconciliation determines their valid state.
- Wallet/provider outage degrades to quote-only; it never falls back to uncontrolled money movement.
- DAIL outage denies all side effects.

## Compensation

Refunds, reversals, entitlement revocation, or settlement corrections must reference the original transaction/license and create append-only CHLOM/DAIL evidence. A Git revert alone does not reverse money, rights, or entitlement.

## Restore

Restore only from an immutable source SHA after tests, security checks, release-package verification, independent verification, and provider readback pass for the exact restored revision.
