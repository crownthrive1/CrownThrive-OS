# PentaBound Runtime Skill

## Ownership

Bounded **PentaBound™** capability for enforcing provider, consumer, credential, route, and risk boundaries.

## Purpose

Prevent a valid credential or route from being used outside its authorized consumer, provider, runtime, or governance envelope.

## Deterministic sequence

1. Read binding, consumer, provider, risk ceiling, and route class.
2. Compare observed use against the canonical binding manifest.
3. Reject cross-consumer, cross-provider, unregistered, or D3-escalating use.
4. Permit only registered hot/cold route classes.
5. Hand transient failures to PentaRetry/PentaQueue; hand policy violations to governance HOLD.
6. Require provider readback before releasing a boundary HOLD.
7. Emit reason-coded evidence through PentaAudit.

## Hard boundaries

- No secret material handling beyond references.
- No authority escalation.
- No implicit alias expansion.
- No provider denial suppression.
- No PASS on incomplete evidence.

## Output

Return binding ID, observed consumer/provider, expected consumer/provider, route class, boundary state, reason code, and receipt identity.
