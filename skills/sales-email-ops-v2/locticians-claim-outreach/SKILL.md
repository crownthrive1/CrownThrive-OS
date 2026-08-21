---
name: "Locticians Claimable-Profile Outreach"
skill_id: "ct.skill.sales.locticians-claim-outreach.v2"
version: "2.0.0"
release_state: "CONTROLLED_TEST"
parent_agent: "ct.chlom.agent.sales-enablement"
agent_id: "ct.chlom.agent.locticians-claim-outreach"
autonomy_class: "A2"
authority_ceiling: "D2"
visibility: "public-safe contract"
---

# Locticians Claimable-Profile Outreach

## Purpose

Research claimable Locticians profiles, verify public business contact paths, personalize category-specific claim outreach, and send only when compliance and suppression gates are satisfied.

## Invoke when

- scheduled claim outreach run
- manual claim-profile campaign

## Required inputs

- Exact Locticians listing URL and claimable/unclaimed state.
- Verified business category, location, public website/social presence, and lawful public business email source when available.
- Current suppression, prior-outreach, risk, and claim state.
- Current outbound compliance configuration.

## Operating contract

Research first. Personalization must use verified business facts rather than invented familiarity. Choose the message structure according to the listing category and the prospect's actual public presence. Primary hooks are ownership/control of an already-discoverable profile, data accuracy, trust/identity, category/location discovery, and a clearer discovery-to-contact path.

### Allowed

- verify claimable state
- research business/category/location
- source public business contact information
- select the category-specific outreach pattern
- personalize from verified facts
- use logo/image references as research inputs where lawful
- queue or send governed outreach when all gates pass
- record evidence and claim status

### Stop / escalate

- do not guess private emails or owner identities
- do not invent services, traffic, reviews, awards, credentials, or referrals
- do not copy or attach third-party creative without rights
- do not send when the compliance or suppression gate is closed
- stop immediately on opt-out, wrong-person, bounce, complaint, claim completion, risk hold, or legal issue

## Cold-outreach gate

A send requires the governed configuration to confirm outbound commercial email is enabled, a valid physical postal address is configured, the recipient is not suppressed, the business contact source is verified, and the listing remains claimable. Until then, research and queue only.

## Follow-up pattern

- Touch 1: Day 0
- Touch 2: after 3 business days
- Touch 3: after 7 business days
- Touch 4: after 14 business days

Any reply pauses the automated cold sequence for response classification.

## Output contract

Record profile URL, category, location, contact source, verified research facts, personalization hook, selected template, send/hold state, suppression state, next touch, and conversion/claim outcome.

## Verification

Verify both provider delivery state and Locticians claim state. A sent email is not evidence that the profile was claimed.