---
title: "CHLOM Preferred Partners, Sponsors & Infrastructure Ecosystem"
description: "Governance for open-source dependencies, preferred infrastructure providers, paid partners, sponsors, and community support."
---

# CHLOM Preferred Partners, Sponsors & Infrastructure Ecosystem

## Purpose

CHLOM is provider-portable by design. This registry distinguishes technical dependencies, evaluated providers, preferred partners, sponsors, and paid placements so commercial relationships never silently rewrite technical truth.

## Relationship states

Every organization or project SHALL carry one of these states:

- `OPEN_SOURCE_DEPENDENCY` — upstream software used or evaluated under its license; not a sponsorship or endorsement.
- `EVALUATED_PROVIDER` — technically evaluated; no commercial preference implied.
- `PREFERRED_PARTNER` — approved strategic/provider relationship supported by current evidence.
- `PAID_SPONSOR` — paid promotional relationship; must be visibly disclosed.
- `COMMUNITY_SUPPORTER` — non-commercial contributor/supporter recognized under published criteria.
- `HISTORICAL` — relationship or evaluation preserved for history but not current.
- `RESTRICTED` — details exist but are not suitable for public disclosure.

## Open-first foundation

The initial CHLOM architecture evaluates Polkadot SDK/Substrate, Kubo/IPFS, PostgreSQL, OpenBao, OpenTelemetry, Prometheus, Grafana, Docker and compatible ingress/object-storage technologies. Their inclusion is technical evaluation or dependency classification, not evidence that their maintainers sponsor, endorse, certify, or partner with CrownThrive.

## Future managed-provider lane

When operational requirements justify paid services, CHLOM may evaluate managed node/RPC, compute, storage, edge, key custody, monitoring, security, backup, and support providers. Candidate examples may include OnFinality, Blockdaemon, DigitalOcean, Cloudflare, and alternatives. No candidate becomes `PREFERRED_PARTNER` until cost, capability, security, portability, license/terms, support, exit, and evidence gates pass.

## Sponsor inventory

Sponsor surfaces MAY include:

- documentation acknowledgements;
- infrastructure-lab sponsorship;
- developer documentation sponsorship;
- research/program sponsorship;
- event or educational sponsorship;
- ecosystem/tool sponsorship;
- clearly labeled partner spotlights.

Sponsor placement SHALL be subordinate to documentation integrity. A sponsor cannot buy PASS status, preferred technical ranking, security certification, architectural control, favorable benchmark manipulation, or suppression of material limitations.

## Sponsor disclosure contract

Every paid placement must include:

```yaml
sponsor_id: stable-id
organization: legal/display name
state: PAID_SPONSOR
placement: named surface
term_start: date
term_end: date
consideration_class: cash|in_kind|credits|mixed
editorial_control: false
technical_certification_implied: false
relationship_disclosure: required
approval_evidence: evidence-id
```

Exact confidential economics may remain restricted while the existence and nature of a material paid relationship is disclosed where required.

## Community support / "Buy the Lab a Coffee"

CrownThrive may provide a restrained voluntary support surface for people who value the CHLOM research, documentation, open tooling, and institutional-recovery work. The preferred language is support-oriented rather than crisis-oriented: contributions help offset infrastructure, storage, testing, documentation, security, and development costs.

Suggested public presentation:

> **Support the CHLOM Lab**  
> CHLOM is being developed open-first, with substantial research, engineering, documentation, testing, and infrastructure work. If this work is useful to you, you can help offset the cost of keeping the lab running. Support is optional and does not purchase governance influence, technical certification, licensing rights, or preferential treatment.

Suggested options: `$5`, `$10`, `$25`, and `Give what you want`.

The support CTA SHOULD appear in low-pressure locations such as the CHLOM Lab footer, project-support page, developer/research acknowledgements, or after substantial free technical resources. It SHOULD NOT interrupt critical documentation, masquerade as a required fee, or use guilt/scarcity language.

## Payment implementation gate

Stripe is the preferred initial payment rail for voluntary support because it can provide hosted checkout/payment-link flows without making CHLOM dependent on Stripe internally. Before a public support link is published, the implementation must have:

- an approved Stripe Product/Price or Payment Link;
- accurate description of the payment as voluntary support rather than a charitable donation unless legally qualified;
- receipts and refund/support contact path;
- tax/accounting classification reviewed for the operating entity;
- terms/privacy disclosures appropriate to the checkout flow;
- analytics that do not expose sensitive payment data;
- CHLOM/DAIL evidence of configuration and material changes.

Until those gates pass, documentation may specify the support program but SHALL NOT invent or publish a Stripe URL.

## Sponsor automation

A Sponsor Registry Agent may monitor relationship term dates, disclosures, placement integrity, broken links, sponsor assets, evidence freshness, and renewal windows. It may draft or mechanically update low-risk metadata. It may not create commercial commitments, alter consideration, accept money, promise exclusivity, grant certification, or classify a provider as preferred without the required approval/evidence path.

Automation outputs SHALL be inspectable as `docs_updated`, `docs_no_change`, or `docs_delta_opened` and should feed the normal CHLOM documentation/reconciliation workflow.
