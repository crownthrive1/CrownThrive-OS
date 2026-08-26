# Penta Communications & Service Family

**Family ID:** `communications-service`  
**Portal:** `/io/pentas/families/communications-service`

## Story

This family owns governed institutional messaging and service-delivery coordination. It separates what CrownThrive knows or decides from how a message is packaged, delivered, followed up and reconciled.

PentaMail owns email composition/routing/provider delivery state. PentaConcierge owns bounded service intake, calls/bookings/research/fulfillment and handoffs. PentaMarketer packages governed campaigns, messaging and marketing evidence for approved audiences/offers.

## Primary members

PentaMail · PentaConcierge · PentaMarketer

## Responsibilities

- authorized sender/recipient and message purpose;
- templates, queues, retries, bounces/complaints;
- consent-aware outreach/service communication;
- concierge intake/confirmation/fulfillment;
- campaign/message packaging and measurement handoff;
- communication/service evidence and history.

## Operating flow

```text
approved communication/service need
→ identity + audience/consent check
→ Mail/Concierge/Marketer preparation
→ PentaRoute certified delivery/provider path
→ delivery/fulfillment readback
→ PentaStatus/CrownLytics evidence
→ follow-up or closure
```

## Cross-family handoffs

Routing supplies delivery paths; Security/Trust supplies identity/credential/consent controls; Commerce supplies only approved offers/economic actions; Observability supplies delivery/incident signals.

## Authority boundary

A mail provider, marketing tool or concierge capability does not authorize sending, purchasing, booking, speaking for CrownThrive or changing commercial terms. PentaMail is a delivery rail and may not redefine institutional status truth.

## Incidents and recovery

Delivery failures, rate limits, complaints, bounced addresses, failed bookings and provider outages must preserve message/request identity, retry state and customer/operator impact. Retry never bypasses consent, rate or authority controls.

## Releases and roadmap

Communication systems should converge on shared templates, consent/purpose metadata, provider failover, durable delivery receipts and owner reporting while keeping cold outreach, nurturing and transactional/service lanes distinct.
