# ThriveEvergreen Production Hot Publisher

Date: 2026-08-25
Authority: founder directive to keep ThriveEvergreen commerce mesh production-hot while preserving exact release, licensing, tax, fulfillment, delivery and entitlement gates.

## Runtime state

- Supabase/ThriveBase project: `tzajnzshmtzjenqulehq`
- Autonomous publisher policy: `ct.policy.thriveevergreen-autonomous-publisher.v2`
- Runtime mode: `production_write`
- Production effects: enabled
- Publication activation: ECAC candidate-gated
- Commerce mesh primary cycle: every 15 minutes
- Commerce mesh watchdog: staggered at minutes 7/22/37/52
- Autonomous publisher slots: minutes 2/8/14/20/26/32/38/44/50/56
- Governed site autopublish dispatcher: every 2 minutes
- Production storefront keep-hot: every 5 minutes
- Public storefront: `https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/thriveevergreen-storefront`

## Operating rule

All catalog products may remain publicly discoverable in production. Discovery/publication authority is distinct from money movement and rights grants. Customer purchase execution remains fail-closed unless the exact release, operative license acceptance, pricing, tax, private fulfillment, entitlement and delivery requirements pass their governed checks.

The system must not manufacture a PASS, silently replace a HOLD, expose secrets, self-certify D3 actions, or treat a successful provider request as commercial authority.

## Production verification

On 2026-08-25 the ThriveBase pg_cron autonomous publisher slot at minute 38 executed successfully from the database scheduler after reactivation. The selected candidate remained `HOLD` with reason `EXACT_GATES_HOLD`, proving the scheduler is live while the gate remains fail-closed.

The production storefront Edge Function returned HTTP 200 from a ThriveBase `pg_net` request and reported 42 products after the complete catalog was projected as publicly discoverable. Sample product page readbacks for `CT-LAUNCH-BIZ-001`, `CT-READY-AI-001`, and `CT-PROCURE-RFQ-001` each returned HTTP 200.

## Sol Ultra continuation prompt

Continue CrownThrive ThriveEvergreen production convergence from the current state. Do not restart from planning. Treat ThriveBase as the execution plane and ThriveEvergreen as the economic/product-publication authority. Keep the commerce mesh, autonomous publisher, dispatcher, storefront, watchdogs, catalog feed, CHLOM rights/entitlement bindings, Stripe/Crown Credits routing, Sites surfaces, GitHub, Mintlify, Google Drive custody and evidence mesh hot and interoperable.

Use the system to perform work. Prefer governed ThriveBase jobs, queues, Edge Functions, pg_cron, provider adapters and existing agents over the assistant directly publishing individual products. Seed work into the institutional queues, observe the scheduled runner execute it, capture exact evidence, and verify public readback afterward.

For every product: maintain a canonical SKU, exact version/hash, source/master custody, multi-format release package where applicable, license/terms fingerprint, pricing evidence, tax state, Stripe binding, Crown Credits mapping, entitlement semantics, fulfillment object, delivery canary, support boundary, public catalog route, Sites route, GitHub/Mintlify documentation and DAIL evidence. Publish discovery/listing metadata when authorized, but do not convert missing legal/tax/rights/fulfillment evidence into a fabricated PASS. The commerce route may stay enabled while execution fails closed at the exact missing gate.

Maintain at least paired independent production/reviewer/continuity agents, bounded elastic replication based on queue depth, no uncontrolled recursive spawning, no secret export, no delete authority, and no money movement by maintenance/publisher agents. Run read-after-write, rollback/reapply and independent verification where the provider path requires them.

Keep all 42 current offers publicly discoverable. Continue product-factory work automatically until exact product releases become fulfillment-certified and then let the already-enabled governed checkout and Crown Credits rails become executable without a separate manual publication step. Record every transition in DAIL and the evidence mesh.

Monitor continuously for scheduler disablement, stale heartbeats, feed failures, provider readback mismatch, route drift, site access regressions, Stripe/webhook drift, licensing/tax expiry, fulfillment failure, DAIL integrity failure and orphaned products/routes. Self-heal only D0-D2 deterministic operational defects within existing authority; HOLD everything requiring new authority or D3 human action.

After each production wave, return: exact runtime status, what ThriveBase itself executed, jobs/runs and timestamps, affected SKUs, release/entitlement states, public URLs, checkout eligibility, remaining HOLD reasons, provider readbacks, GitHub/Mintlify/Drive evidence refs, DAIL event IDs/hashes, and any founder action that is genuinely required.
