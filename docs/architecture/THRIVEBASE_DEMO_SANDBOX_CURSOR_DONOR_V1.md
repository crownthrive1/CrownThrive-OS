# ThriveBase Demo Sandbox Cursor Donor v1

**Status:** Production active  
**Provider project:** `uipojzbnnfifsbkivxoh`  
**Provider name:** `ThriveBase-Public`  
**Operational alias:** `ThriveBase Demo Sandbox`  
**Node:** `node:thrivebase.demo-sandbox.cursor-donor`  
**Assignment:** `ct.assignment.thrivebase-demo-sandbox-cursor-donor-v1`

## Decision

The underused ThriveBase-Public Micro project now reserves 70 percent of its managed discretionary scheduler and worker capacity for DAIL Cursor service. Thirty percent remains available to existing request-driven public endpoints and Vercel staging projects.

This is a governed runtime budget, not a claim that Supabase exposes a literal provider CPU partition. The reservation is enforced in CrownThrive control tables as 100 managed units per minute:

- 70 units reserved for Cursor
- 30 units retained for existing public and Vercel staging services
- two Cursor dispatch slots per minute
- 35 units per dispatch
- unused Cursor units are not reassigned

The provider project name remains ThriveBase-Public to preserve bindings. ThriveBase Demo Sandbox is the authoritative operating alias.

## Runtime path

```text
ThriveBase Demo Sandbox
        |
        | local 70/30 reservation
        v
thrivebase-demo-sandbox-cursor-donor
        |
        | local signed sender
        v
ct.bridge.thrivebase.public-to-private.v1
        |
        | ECDSA P-256, replay protected
        v
ThriveBase bridge receiver
        |
        v
DAIL Cursor MeshAssist
        |
        v
one canonical CHLOM DAIL writer
```

The donor never receives direct private database access and does not create a second ledger, second authority source, or second canonical writer.

## Production controls

- Capacity policy: `ct.demo-sandbox.capacity-donation.70-30.v1`
- Interop contract: `ct.contract.dail.cursor-demo-sandbox-donor.v1`
- Formula: `ct.dail.formula.demo-sandbox-donor-share.v1`
- Recipe: `ct.dail.recipe.demo-sandbox-cursor-donation.v1`
- Public cron: `ct-demo-sandbox-cursor-donor-v1`
- Schedule: every 30 seconds
- Main dispatch: `chlom_runtime.dail_cursor_demo_sandbox_donor_dispatch_v1`
- Safe status: `public.ct_dail_cursor_demo_sandbox_donor_status_v1()`

The signed bridge envelope is D1, has no authority effect, and is idempotent. The main receiver validates the exact donor project, alias, 70/30 split, manifest SHA-256, time window, signature, replay key, and allowlisted operation.

## Admission and safety

Actual route work remains subject to PentaBalancer. A reserved donor slot may be deferred without returning that reserved capacity to other services. A successful run uses the existing Cursor MeshAssist limit of 600 routes and zero Archive selection while the 500K continuity lock is active.

The donor Edge Function retries one pressure/contention deferral once after a six-second offset. This improves phase separation without bypassing PentaBalancer.

## Initial evidence

First bound donor run:

- Donor run: `d161422f-c4a0-417b-b3de-134dfde9e5c3`
- Bridge event: `34b40faf-06de-455d-afc5-fbe47cb9b7ee`
- Mesh run: `672cf83c-430a-4a64-bb2c-01419f4053bb`
- Routes delivered: 600
- Route failures: 0
- PentaGas quoted: 5,528
- PentaGas actual: 5,528
- Terminal DAIL event: `0dc69feb-1fe9-4652-9b52-e3d8f2a6e84f`
- Terminal DAIL sequence: `2,526,427`
- Evidence SHA-256: `7a643b12acc601c9a62e9eca9c54c171b920191015a445b9698a82dd1c77950e`

Observed deployment window:

- Five bound donor runs
- 3,000 donor-attributed routes delivered
- Zero donor route failures
- Backlog baseline: 548,013
- Deployment-receipt observation: 539,230
- Observed delta: -8,783

The backlog delta includes all active Cursor paths and is not attributed solely to the donor. The donor's exact attributable contribution in that snapshot is 3,000 delivered routes.

Production deployment DAIL event:

- Event: `24f55171-b562-47ec-9603-bae09beab31a`
- Sequence: `2,529,972`
- Event hash: `9488e6a1be2fbf4475937aebe87e138c6f31bc28dc7464f8daa9d135bae68d8d`
- Payload SHA-256: `246f978025e2c1120f0e2ca7b5ddf58caa8236dcc7c85a8fc9e350feb23d118f`

## Release behavior

The 70 percent reservation remains enforced continuously. Route-drain dispatch becomes dormant when the 500K continuity lock releases. During an unlocked period the reserved share remains Cursor standby capacity for verification, projection, canary, and deferred-evidence work rather than being reassigned.

## Non-effects

This extension creates no customer charge, provider billing change, token issuance, rights grant, entitlement, payment, or expanded authority.
