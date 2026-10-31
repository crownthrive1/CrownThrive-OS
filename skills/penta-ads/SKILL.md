# PentaAds Production Skill

**Skill ID:** `ct.skill.penta-ads.production.v1`

Use this skill for CrownThrive advertising inventory, placement planning, installation, verification, maintenance, pricing observation, campaign/ad routing, and recovery.

## Required order

1. Pin the exact private PentaAds source version.
2. Re-read ThriveBase site/zone/provider inventory.
3. Resolve the exact site, surface, zone, format, consent and exclusion policy.
4. Dedupe existing installations and bindings.
5. Require exact connector write, read-after-write and rollback authority.
6. Build and validate the placement manifest.
7. Stage/canary before public release.
8. Require public DOM/network and provider readback.
9. Record release, recovery and DAIL evidence.
10. Roll back or HOLD on mismatch.

## Current hard hold

Locticians Brilliant Directories live installation remains `HOLD_BD_TEMPLATE_WRITE_AUTHORITY` until the exact template/widget write/readback/rollback path is independently certified.

## Boundaries

Do not invent provider IDs, expose credentials, disguise advertising as editorial, infer revenue from a tag render, bypass consent, duplicate billing, move money, settle payouts, grant rights, or perform D3.
