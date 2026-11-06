# Runbook — CrownThrive Convergence Gap Closure Skills Suite v2

## Scope

This runbook operates the public-safe, dry-run planning runtime for `ct.skill-suite.convergence-gap-closure.v2`. It does not invoke providers or perform live side effects.

## Validate

```bash
python3 runtime/skills_fleet_gap_closure.py validate-registry
python3 -m unittest tests.test_skills_fleet_gap_closure -v
```

## List and inspect

```bash
python3 runtime/skills_fleet_gap_closure.py list
python3 runtime/skills_fleet_gap_closure.py inspect skill-fleet-gap-analyzer
```

## Plan a task

Create a JSON task conforming to `schemas/skill-gap-task.schema.json`.

```bash
python3 runtime/skills_fleet_gap_closure.py plan \
  --task artifacts/example-task.json \
  --output artifacts/example-receipt.json
```

Exit codes:

- `0`: deterministic plan produced;
- `2`: plan produced with explicit HOLD because effect evidence is incomplete;
- `1`: task denied or invalid.

## Live execution handoff

A skill receipt is a plan/evidence contract, not a provider mutation. Any live execution must bind to:

1. an accepted exact source revision;
2. an adopted operation-level contract;
3. authorized non-secret Vault references;
4. a registered provider adapter;
5. idempotency/duplicate controls;
6. rollback or compensation;
7. provider read-after-write evidence;
8. DAIL/PentaAudit custody;
9. required human/independent review;
10. affected canonical-ledger projection.

## Rollback and correction

Before merge, delete the feature branch or close the PR. After merge, use a normal corrective PR that preserves the original commit and records the supersession. Do not rewrite main or accepted history.
