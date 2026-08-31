# CrownThrive Communications Transport Boundary v1

**Contract ID:** `ct.communications.transport-boundary.v1`

## Purpose

This contract defines the non-negotiable transport boundary for CrownThrive business and persona communications.

## Canonical topology

`Mailbox provider -> Communications Watch -> normalized work/evidence -> PentaMarketer/persona -> PentaMail/PentaMailer -> governed provider transport -> provider readback -> CHLOM/DAIL closeout`

## Invariants

1. **Gmail and Outlook are mailbox connector boundaries, not CrownThrive business-send interfaces.** Their CrownThrive role is acquisition, reading, normalization, thread/source identity, and handoff.
2. **All CrownThrive business/persona outbound uses PentaMail/PentaMailer.** PentaMarketer owns business intent, work identity, persona selection, lifecycle/risk classification, and due state. PentaMail/PentaMailer owns transport.
3. **No direct-mailbox fallback.** If PentaMail/PentaMailer or its provider route is unavailable, held, timed out, or unverifiable, the work remains `HOLD_PENTAMAIL_TRANSPORT_UNAVAILABLE`. It must never fall back to a Gmail/Outlook direct send.
4. **Direct mailbox business/persona sends are policy violations.** They must be classified `HOLD_DIRECT_MAILBOX_SEND_PROHIBITED` and routed back through PentaMarketer/PentaMail.
5. **Sender identity is governed.** A persona sender must resolve from the canonical sender-identity registry. A stale/held/timed-out sender identity cannot be bypassed by changing transport.
6. **Universal copy policy is centralized.** `ct.pentamailer.policy.universal-copy.v1` owns required operational copies. Personas and agents must not hand-maintain copy recipients when the runtime can apply the policy.
7. **Support is first-class traffic.** `support_transactional` is claimable and is prioritized ahead of marketing traffic. Marketing fairness rules must not strand support/member-success messages.
8. **External recipient policy is mandatory.** Recipient eligibility, suppression, compliance, risk, work identity, and idempotency must pass before dispatch.
9. **Provider acceptance is evidence, not institutional completion.** Material outbound requires provider readback plus applicable CHLOM/DAIL evidence before completion is represented institutionally.
10. **One mailbox failure domain.** The canonical Communications Watch is the single external Gmail/Outlook connector clock. Other Pentas consume its handoff; they do not create duplicate mailbox pollers or business-send clocks.
11. **Scheduler timing creates no authority.** A scheduled run cannot create sender, provider-write, money, rights, D3, or certification authority.
12. **No self-approval.** Originator/persona/transport cannot manufacture governance, rights, D3, or independent certification.

## Required machine-readable runtime projection

`public.penta_mail_transport_boundary_v1()` returns the public-safe current invariant and hold codes.

## Traffic priority

`system_internal -> support_transactional -> marketing_locticians -> marketing_other`

A reserved newsletter slot may operate only when no eligible `system_internal` or `support_transactional` work is waiting.

## Failure behavior

Fail closed on missing sender identity, recipient eligibility, provider authority, transport health, required evidence, or readback. Preserve the work item and exact blocker; do not bypass the control plane.
