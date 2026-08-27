# PentaRoute Runtime Skill

## Ownership

Bounded **PentaRoute™** capability for governed hot/cold runtime dispatch.

## Purpose

Separate latency-sensitive live reconciliation from deferred audit, backfill, and recovery work while preserving the same governance envelope.

## Route model

- **Hot**: event-driven live reconciliation for push, pull request, issue, workflow dispatch, and binding-change events.
- **Cold**: scheduled, repository-dispatch, credential-audit, drift-recovery, and bounded backfill work.

## Deterministic sequence

1. Read registered route definitions from the production runtime control plane.
2. Match the incoming trigger to exactly one authorized route class.
3. Validate target Penta activation and PentaBound policy.
4. Dispatch hot work immediately when provider authority is available.
5. Place recoverable cold work behind PentaQueue/PentaRetry.
6. Fail closed on unknown routes, disabled targets, or provider denial.
7. Emit a non-secret route receipt through PentaAudit.

## Hard boundaries

- No arbitrary target execution.
- No unregistered route creation at runtime.
- No secret values in route payloads.
- No governance bypass for speed.

## Output

Return route ID, class, source, target, trigger, activation state, disposition, and receipt identity.
