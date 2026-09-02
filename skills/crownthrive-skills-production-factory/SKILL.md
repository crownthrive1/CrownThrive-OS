---
name: crownthrive-skills-production-factory
description: Produce, validate, package, ledger, and hand off stable CrownThrive skills to PentaGreen on an idempotent hourly cycle.
---

# CrownThrive Skills Production Factory

Use this skill when CrownThrive needs to create or maintain reusable operating skills, commercial bundles, runtime packages, master-ledger records, or PentaGreen handoffs.

## Procedure

1. Resolve the highest-level institutional objective and the owning corridor.
2. Reconcile existing skills and exact stable identities before generating a successor.
3. Produce bounded `SKILL.md` and machine-readable contract artifacts.
4. Validate structure, uniqueness, secret boundaries, negative cases, and version preservation.
5. Build an exact-subject package and evidence manifest.
6. Append the factory and asset ledgers.
7. Hand the package to PentaGreen with rights, price, tax, fulfillment, entitlement, destination, and provider-readback fields.
8. Process the handoff through `ct.pentagreen.skills.processor.v1`; emit ECAC only for complete exact provider bindings.
9. Move reversible preparation immediately; keep irreversible missing proof as an explicit HOLD.
10. Project current state to the command center and verify provider readback.

## Output rule

Never claim commerce activation, deployment, entitlement, payment, or provider success without exact provider readback.
