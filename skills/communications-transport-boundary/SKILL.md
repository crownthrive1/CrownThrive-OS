# CrownThrive Communications Transport Boundary Skill

**Skill ID:** `ct.skill.communications.transport-boundary.v1`

Use this skill for any CrownThrive email/business communication workflow involving Gmail, Outlook, PentaMarketer, personas, PentaMail/PentaMailer, Mailgun, support, sales, partnerships, licensing, member success, customer success, provider/vendor communication, or campaign delivery.

## Required execution order

1. **Acquire, do not send:** Gmail/Outlook may be used to read the relevant message/thread and recover authoritative reply recipients, thread identity, source message ID, and context.
2. **Normalize work:** create/reuse the canonical PentaMarketer work item, preserve source provider/message/thread identity, classify lane/risk/D-level, and deduplicate by stable idempotency key.
3. **Resolve persona:** use the canonical persona and sender-identity registries. Never invent a sender or bypass a held/timed-out sender by using Gmail/Outlook directly.
4. **Check recipient policy:** enforce external-recipient eligibility, suppression, opt-out, complaint, wrong-person, bounce, risk, and compliance rules.
5. **Enqueue through PentaMarketer:** business intent and lifecycle state belong to PentaMarketer; transport does not originate intent.
6. **Dispatch only through PentaMail/PentaMailer:** apply the canonical universal-copy policy centrally. Do not manually reconstruct copy recipients when the policy is available.
7. **Read back provider state:** require provider message identity/status and exact outbox/work state. Provider acceptance alone does not create broader authority.
8. **Bind material outcome:** append/read back applicable CHLOM/DAIL evidence and preserve thread/work/provider lineage.

## Absolute prohibition

Never use Gmail/Outlook direct send/reply as a fallback for a CrownThrive business/persona message.

If PentaMail cannot send, return/persist:

- `HOLD_PENTAMAIL_TRANSPORT_UNAVAILABLE`, or
- `HOLD_DIRECT_MAILBOX_SEND_PROHIBITED` when a direct-mailbox attempt is detected.

Do not weaken the gate to complete the communication.

## Traffic classes

Priority is:

1. `system_internal`
2. `support_transactional`
3. `marketing_locticians`
4. `marketing_other`

Support/member-success/customer-success traffic must not be stranded behind marketing caps or newsletter fair-share logic.

## Universal-copy rule

Use `ct.pentamailer.policy.universal-copy.v1`. Exact operational copy recipients are resolved by the governed runtime. The persona should not memorize or independently maintain the copy list.

## Authority boundary

The mailbox connector, PentaMarketer, persona, PentaMail/PentaMailer, provider acceptance, or scheduler timing does not create D3, legal/rights acceptance, money movement, credential authority, governance approval, or independent certification.

## Acceptance evidence

A successful outbound communication requires at minimum:

- canonical work/message ID,
- canonical persona/sender identity,
- recipient-policy PASS,
- stable idempotency key,
- PentaMail/PentaMailer transport ownership,
- provider acceptance/readback,
- universal-copy policy application where required,
- persisted work/outbox state,
- applicable CHLOM/DAIL closeout for material state changes.
