---
name: "Locticians Claimable-Profile Outreach"
skill_id: "ct.skill.sales.locticians-claim-outreach.v2"
version: "2.1.0"
release_state: "CONTROLLED_TEST"
parent_agent: "ct.chlom.agent.sales-enablement"
agent_id: "ct.chlom.agent.locticians-claim-outreach"
autonomy_class: "A2"
authority_ceiling: "D2"
visibility: "public-safe contract"
---

# Locticians Claimable-Profile Outreach

## Purpose

Research claimable Locticians profiles, verify public business contact paths, personalize category-specific claim outreach, resolve the current governed acquisition offer, and send only when compliance and suppression gates are satisfied.

## Invoke when

- scheduled claim outreach run
- manual claim-profile campaign
- inbound request asking how to claim or upgrade a claimable Locticians profile

## Required inputs

- Exact Locticians listing URL and claimable/unclaimed state.
- Verified business category, location, public website/social presence, and lawful public business email source when available.
- Current suppression, prior-outreach, risk, and claim state.
- Current outbound compliance configuration.
- Current governed offer record and checkout-verification state.
- Current first-party membership price/benefit evidence when economics are discussed.

## Operating contract

Research first. Personalization must use verified business facts rather than invented familiarity. Choose the message structure according to the listing category and the prospect's actual public presence. Primary hooks are ownership/control of an already-discoverable profile, data accuracy, trust/identity, category/location discovery, a clearer discovery-to-contact path, relevant ecosystem tools, and an eligible claim incentive.

### Allowed

- verify claimable state
- research business/category/location
- source public business contact information
- select the category-specific outreach pattern
- personalize from verified facts
- use logo/image references as research inputs where lawful
- resolve the current claim offer from the private offer registry
- calculate savings from current verified public prices after plan eligibility is verified
- use truthful urgency based on claimable/new-signup eligibility and an actual redemption window
- queue or send governed outreach when all gates pass
- record evidence and claim status

### Stop / escalate

- do not guess private emails or owner identities
- do not invent services, traffic, reviews, awards, credentials, referrals, demand, ranking or savings
- do not copy or attach third-party creative without rights
- do not send when the compliance or suppression gate is closed
- do not promise higher-tier coupon eligibility from an admin screenshot alone when current public offer copy is narrower
- do not call an offer “for life” unless an eligible checkout verifies recurring discount treatment
- stop immediately on opt-out, wrong-person, bounce, complaint, claim completion, risk hold, or legal issue

## Governed claim offer

The current private offer key is `locticians.claimmonth50.v1`.

Founder-attested configuration establishes:

```yaml
coupon_code: CLAIMMONTH50
discount_type: percentage
discount_value: 50
scope: signups_and_upgrades
new_signups_only: true
apply_to_recurring_payments: true
require_card_when_zero: true
new_redemption_start: 2026-01-01
new_redemption_expiration: 2028-10-31
maximum_uses: unlimited
selected_plans:
  - Basic
  - Blogger
  - Community+
  - Featured
  - Premium
  - Sponsor
```

Current first-party `/join` copy publicly advertises `CLAIMMONTH50` for claimable listings but names only Community+ and Basic. Treat that difference as an evidence conflict. Until a checkout/readback verifies another selected plan, external copy must say **50% off eligible recurring membership payments** and must not promise Premium, Featured, Sponsor or Blogger eligibility.

## Recurring discount language

Provider coupon behavior distinguishes recurring and first-payment discounts. When recurring is configured `YES`, the discount applies to recurring payments; coupon expiration controls future redemption rather than the order's own end date.

After an eligible checkout confirms recurring treatment, approved customer-safe wording is:

> 50% off recurring payments for the life of the active eligible membership after redemption.

This is not permission to say `lifetime membership`, `forever after cancellation`, or that the code can be newly redeemed after the configured expiration date.

## Current plan economics

Use live first-party pricing at execution time. The August 21, 2026 `/join` evidence showed Community+ `$4.99/month`, Basic `$9.99/month` or `$99.99/year`, Premium `$19.99/month` or `$199.99/year`, Featured `$99.99/month` or `$999.99/year`, and Sponsor `$299.99/month` or `$2,999.99/year`.

If eligibility is verified, 50% arithmetic yields annual savings up to approximately `$1,500` on the Sponsor annual price or approximately `$1,799.94` annualized from the Sponsor monthly price. Those figures may **not** be used in prospect outreach until the exact plan's coupon eligibility is verified at checkout. Blogger pricing is not supported by the current `/join` evidence and must not be invented.

## Value-stack personalization

Current public Locticians value surfaces can support fit-based messaging when relevant:

- rich directory profiles, services, galleries and tags;
- category/city discovery;
- direct client communication on applicable plans;
- ThriveSeat booking-link path;
- reviews and reputation building;
- Premium profile engagement analytics;
- Featured/Sponsor priority visibility and multi-site/team scale;
- CrownThriveU learning;
- ThrivePeer mentorship;
- ThriveTickets events/workshops;
- Nexus Credits for Locticians visibility, boosts, coupons and event amplification;
- CrownRewards as a separate loyalty system.

Do not treat public feature copy as proof of individual customer results.

## FOMO policy

### Permitted

- claimable-profile/new-signup exclusivity;
- the actual coupon redemption window;
- the fact that a verified recurring redemption can preserve the discounted rate while the eligible active membership continues;
- a verified current plan's actual savings.

### Prohibited

- fake countdowns;
- fake limited quantities;
- fabricated “others are claiming your profile” statements;
- invented traffic/demand;
- unsupported `$1,200+` or other savings claims;
- “50% for life” before recurring checkout treatment is verified.

## Cold-outreach gate

A send requires the governed configuration to confirm outbound commercial email is enabled, a valid physical postal address is configured, the recipient is not suppressed, the business contact source is verified, and the listing remains claimable. Until then, research and queue only.

## Follow-up pattern

- Touch 1: Day 0
- Touch 2: after 3 business days
- Touch 3: after 7 business days
- Touch 4: after 14 business days

Any reply pauses the automated cold sequence for response classification.

## Output contract

Record profile URL, category, location, contact source, verified research facts, personalization hook, selected template, resolved offer/version, plan eligibility state, savings claim state, send/hold state, suppression state, next touch, and conversion/claim outcome.

For a converted paid claim, capture coupon acceptance, selected plan, billing cycle, recurring-discount message/readback, pre-discount amount, post-discount amount, recurring amount and provider order reference where permitted.

## Verification

Verify provider delivery state, Locticians claim state, and—when the incentive is part of the close—the actual checkout coupon behavior. A sent email is not evidence that the profile was claimed. A successful first payment is not sufficient proof that the recurring discount will continue.