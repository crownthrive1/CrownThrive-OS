# PentaCrawler™ Communications Research Runtime v1

## Canonical identity

- System key: `ct.penta.crawler.communications.v1`
- Canonical repository: `crownthrive1/CrownThrive-OS`
- Runtime: `supabase/functions/penta-crawler`
- Canonical parent agent: `ct.ops.agent.email-attention`
- External scheduler slots added: **0**

PentaCrawler™ is the bounded public-business research subruntime for the CrownThrive communications failure domain. It discovers and revalidates public contact evidence, classifies Locticians claim candidates, records append-only observations, promotes corroborated research into the CRM, and feeds the existing governed outreach planner.

## Authority boundary

PentaCrawler does **not** inherit commercial-send authority. Research, website crawling, evidence collection, classification, CRM enrichment, copy preparation, and planning may execute autonomously under the existing communications control plane. Commercial delivery remains fail-closed until all of the following are true:

1. NORMAL maintenance state.
2. An active, exact-scope, founder-issued CHLOM authority lease exists for agent `ct.ops.agent.email-attention`, capability `commercial_outbound.send`, resource type `communications_lane`, resource id `crm.outreach`, sensitivity >= D3-equivalent level 3.
3. The lease has a corresponding DAIL `authority.lease.issued` receipt.
4. The specific offer is within its valid date window and its public evidence and checkout verification states are verified/certified.
5. Existing research, suppression, claimability, fit, legitimacy, frequency, monthly cap, postal-address, copy, bounce, complaint, wrong-person, conversion, and opt-out gates pass.
6. PentaMail rechecks commercial authority at the delivery-claim boundary.

No financial transaction, agreement execution, credential disclosure, rights grant, payment authorization, or founder-reserved security decision is part of this runtime.

## Runtime flow

`crm.outreach_control_plane_v1()` is the canonical orchestration entrypoint. It seeds due public-site research, promotes already corroborated records, reads commercial authority and offer readiness, and plans outbound work only when all send gates pass.

`crm.contact_discovery_claim_v1()` leases a bounded batch of due website-research jobs. `penta-crawler` validates public HTTP(S) targets, blocks local/private URL forms, honors robots directives, uses a bounded response size and redirect count, follows only a few same-origin contact/about/team-style links, extracts publicly displayed business email addresses, hashes minimal evidence, and calls `crm.contact_discovery_complete_v1()`.

`crm.contact_discovery_complete_v1()` appends immutable observations to `crm.contact_discovery_observations_v1` and corresponding `crm.research_evidence` rows. It never deletes historical evidence. High-confidence business-owned contact evidence can refresh `crm.prospects.public_email`; lack of an email never fabricates one.

`crm.promote_verified_prospects_v1()` promotes only relevant, claimable Locticians records. Beauty, hair, salon, lash, skin/esthetics, wellness, spa, barber, makeup, brow, massage, loc/locks, and directly evidenced related training profiles qualify. Music/entertainment and partnership/sponsor records are excluded from the Locticians claim lane.

`crm.outreach_eligibility_v1()` and `crm.outreach_scheduler_tick_v1()` recheck authority before scheduling/enqueueing. `public.penta_mail_claim_outbox_v2()` independently refuses to claim `sales_outreach`, `lead_nurture`, or `locticians_claim` messages when commercial authority is absent. PentaMail v3 inherits the same delivery boundary through v2.

## Evidence and privacy

The crawler stores only evidence needed to establish public-business relevance/contact provenance: source URL/type, normalized public email when present, page title, confidence, bounded signals, SHA-256 evidence digest, and timestamps. Full page bodies are not archived by the crawler. Raw secrets, credentials, private mail content, and unrelated personal data are outside scope.

## Current production gate expectation

The runtime is intentionally expected to report `PRODUCTION_FAIL_CLOSED` when research is healthy but commercial authority or verified offer evidence is absent. That state is a successful governance condition, not an outage. Research can continue and the queue can converge while commercial delivery remains at zero.
