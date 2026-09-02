# CrownThrive Skills Production Factory v1.0.1

**Stable contract:** `ct.factory.skills.v1`  
**Registry:** `CT-SKILLS-REGISTRY-001`  
**PentaGreen handoff:** `ct.pentagreen.skills.handoff.v1`

This factory converts CrownThrive operating capabilities into versioned, testable skill packages and routes each completed package to PentaGreen for commercial processing. It extends the installed CrownThrive software-factory spine rather than creating a competing orchestrator.

## Production loop

`Discover -> Specify -> Generate -> Validate -> Package -> Evidence -> Master Ledger -> PentaGreen -> Provider Readback`

The hourly clock runs at minute 17, processes ten skills per tick, preserves an idempotency key per UTC hour, and covers all 59 skills in six ticks. Existing fast continuity and dispatch clocks remain the health and work-dispatch supervisors.

## Fast-track boundary

Reversible preparation proceeds automatically. The factory does not bypass rights ownership, jurisdiction-specific tax treatment, money movement, customer entitlement, credential boundaries, provider-write certification, or provider readback. Those controls are required for commercially stable delivery.

## Durable state repair in v1.0.1

Each hourly run now hydrates the prior `automation/skills-factory-state` projection before production, processes the batch through the PentaGreen gate, and republishes the complete append-only runtime state. This prevents tranche replay after runner restart.
