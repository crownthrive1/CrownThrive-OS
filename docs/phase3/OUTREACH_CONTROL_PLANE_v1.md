# CrownThrive Outreach Control Plane v1

Status: production control-plane baseline

This control plane is a subroute of `ct.scheduler-topology.production.v1`, bound to `ct.ops.agent.email-attention`. It does not create a new external communications clock and does not expand D3 authority.

## Cold outreach

- Hard ceiling: 20 cold outreach emails per calendar month.
- Every candidate must be researched and verified before scheduling.
- Minimum legitimacy score: 70/100.
- Minimum CrownThrive fit score: 60/100.
- A claimable Locticians profile is required for the Locticians claim campaign.
- A valid CrownThrive physical postal address must be configured.
- One cold attempt per contact. Additional automated contact is not treated as nurture unless the relationship becomes nurture-eligible.
- Offer reference is `locticians.claimmonth50.v1`.
- Until exact checkout evidence resolves plan scope, only the safe offer language in the machine contract may be used.

## Nurture

Nurture has no ecosystem-wide monthly volume cap, but it remains relationship-gated. Eligible states are engaged, consented, subscriber, customer, partner, and former customer. The default minimum interval is 72 hours. Nurture is automatically blocked for opt-out, wrong-person, hard bounce, complaint, risk hold, or conversion states.

## Scheduling

The live ThriveBase control plane uses internal pg_cron subroutes:

- `ct-outreach-daily-planner-v1` evaluates researched eligible cold candidates and schedules no more than one cold candidate per business day while respecting the 20/month hard ceiling.
- `ct-outreach-scheduler-tick-v1` evaluates due scheduled messages every 15 minutes and enqueues only eligible messages to PentaMail/PentaMailer.

Targeted maintenance forces the scheduler into read-only commercial behavior. Scheduler time never confers authority, quorum, approval, or provider eligibility.

## Evidence and archive policy

Operational evidence stores schedule/contact/event identifiers and provider message/thread IDs. Gmail remains canonical for Gmail content; the outreach control plane must not create duplicate long-term full-body or attachment archives merely for retention. Message bodies may exist transiently in the operational PentaMail outbox as required for delivery and are subject to the existing bounded cleanup/retention controls.

## Security

Outreach contact, schedule, and event tables use RLS and are restricted to the service role. Secret material is never stored in outreach records. Provider credentials remain under PentaCredentials/ThriveBase Vault and provider-specific secret injection.
