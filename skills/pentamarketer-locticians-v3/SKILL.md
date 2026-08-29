# PentaMarketer Locticians Dynamic Outreach V3

Status: **PRODUCTION CONTRACT**  
Version: **3.0.0**  
Authority: `ct.locticians.brilliant-directories.api-fabric.v3`

## Purpose

Generate evidence-grounded, persona-led Locticians claim outreach dynamically for each eligible prospect. This skill is the public execution contract. Proprietary rendering and scoring implementation remains restricted under CHLOM/private custody.

## Owners

- PentaMarketer — campaign and communication control plane
- PentaCrawler — public-business research evidence
- PentaMail — sole governed outbound transport
- PentaSkills — reusable skill contract
- PentaCertify / PentaAudit — independent validation and receipts
- PentaSELF — fail-closed healing and drift routing

## Required inputs

- verified claimable Locticians prospect
- safe public business email
- canonical Locticians profile URL
- current public-business research evidence
- canonical safe offer state
- active campaign authority and remaining capacity
- suppression / opt-out / complaint / bounce state
- assigned persona identity

## Dynamic output contract

Every cold-outreach message is rendered per prospect at enqueue time and MUST include:

1. business-specific subject and greeting;
2. evidence-grounded personalization from verified public facts or verified vertical context;
3. canonical Locticians profile link;
4. CTA link carrying campaign attribution and `ct_offer=CLAIMMONTH50`;
5. visible coupon code `CLAIMMONTH50`;
6. canonical safe offer copy only;
7. persona voice (default: Avery — Locticians Member Success);
8. multipart HTML plus plain-text fallback;
9. CrownThrive promotional identification, postal address and opt-out language;
10. minimal operational metadata and delivery receipts.

The tracking parameter carries offer context. It MUST NOT be represented as proof that checkout automatically redeems or applies a coupon unless independently verified by the checkout provider.

## Personalization rules

Allowed personalization is restricted to independently observed public business evidence, canonical listing fields, and bounded vertical classification. Never invent customer counts, popularity, scarcity, rankings, competitor behavior, revenue, traffic, awards, urgency, or business-owner identity.

FOMO may describe the verified state that a public profile is already visible while unclaimed and that the business has not yet taken control of that public touchpoint. Unsupported social-proof or scarcity claims are prohibited.

## Provider/reference rule

The CrownThrive Brilliant Directories fork and BD upstream may be used for provider reference and schema understanding. They are NOT CrownThrive execution authority. All provider execution remains governed by `ct.locticians.brilliant-directories.api-fabric.v3`, its route decision, credential, rate, rights and D3 boundaries.

## Send boundary

The skill does not send directly. Eligible messages enter the PentaMail outbox and inherit all existing campaign caps, working-hour rules, provider-adaptive pacing, Mailgun cooldowns, suppression, one-click unsubscribe, sender sanctions, reconciliation and provider-readback gates.

## Autonomy

Autonomy ceiling: **A3** within the bounded D1 communication contract. Fail closed whenever evidence, recipient validation, offer state, profile URL, provider authority, capacity, or suppression state is not valid.

## Receipts

- per-message schedule/outbox/provider receipts remain authoritative for delivery;
- BD reference continuity is receipted daily;
- DAIL receives institutional reference/repair evidence;
- public contract contains no provider credential material or restricted renderer body.
