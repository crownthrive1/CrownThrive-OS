# PentaMail Production Skill

**Skill ID:** `ct.skill.penta-mail.production.v1`

Use this skill whenever CrownThrive sends, retries, reconciles, or evidences a business/persona email.

## Procedure

1. Resolve the canonical work item and business owner in PentaMarketer.
2. Resolve the approved persona/sender and exact recipient policy.
3. Enforce suppression, opt-out, complaint, bounce, wrong-person, risk, timing and campaign controls.
4. Assign a stable idempotency key and traffic class.
5. Enqueue through PentaMail; PentaMailer owns transport execution.
6. Never use Gmail/Outlook direct send as fallback.
7. Require provider message identity and exact outbox/work readback.
8. Reconcile ambiguous outcomes before retry.
9. Append/read back applicable CHLOM/DAIL evidence.
10. Preserve D3, legal, money, rights, credential and certification boundaries.

## Typed holds

`HOLD_PENTAMAIL_TRANSPORT_UNAVAILABLE`, `HOLD_DIRECT_MAILBOX_SEND_PROHIBITED`, `HOLD_RECIPIENT_POLICY`, `HOLD_SUPPRESSION_OR_OPT_OUT`, `HOLD_PROVIDER_READBACK`, `HOLD_DAIL_UNBOUND`.
