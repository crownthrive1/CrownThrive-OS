# PentaGreen Skills Processor

**Contract:** `ct.pentagreen.skills.processor.v1`

The processor consumes the current factory handoff batch, applies only explicit exact-subject provider bindings, and recalculates every activation gate. It never infers provider identifiers.

## ECAC conditions

A handoff reaches `ECAC` only when rights authority, provider price, tax code, fulfillment destination, entitlement contract, sales destination, provider readback receipt, and an accepted observed provider state are all present. Missing or partial bindings remain `HOLD` with exact reasons.

Bindings may be supplied through a protected runtime file or `PENTAGREEN_BINDINGS_JSON`. No secrets belong in source control.
