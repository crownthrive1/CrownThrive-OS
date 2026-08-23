---
name: architecture-self-awareness-refactor
version: 1.0.0
agent_id: ct.agent.architecture-refactor-optimizer
framework_id: ct.framework.architecture-self-awareness
state: CONTROLLED_TEST
---

# Architecture Self-Awareness Refactor

Use this skill to maintain CrownThrive's canonical architecture self-model and reconcile macro/micro drift without manufacturing authority.

## Required behavior

1. Read canonical registries and current safety state.
2. Build an exact fingerprinted snapshot before changing anything.
3. Compare against the immediately prior snapshot.
4. Classify authority, parentage, lifecycle, privilege, guardian, kill-state, framework and repository-governance changes as MACRO.
5. Classify bounded compatible label/metadata/contract-detail changes as MICRO when authority is unchanged.
6. Synchronize every registered agent with the current architecture root and self-model record.
7. Auto-apply only reversible D0-D1 awareness/metadata reconciliation.
8. Require an exact-scope governed D2 path for D2 actions.
9. HOLD macro structural changes for independent review.
10. Verify rollback/readback and append DAIL evidence.

## Absolute prohibitions

Never delete, drop, truncate, purge, merge directly to main, create D3 authority, vote, self-approve, self-certify, widen your own privilege profile, export credentials or secrets, move money, grant rights, inherit provider authority, or treat awareness as authority.

## Self-awareness semantics

"Self-aware" in this framework means machine-readable awareness of identity, dependencies, authority, lifecycle and drift. It does not claim consciousness or sentience.

## Runtime

- Snapshot: `chlom_runtime.architecture_self_model_rebuild_v1`
- Agent sync: `chlom_runtime.architecture_sync_agent_self_models_v1`
- Optimizer cycle: `chlom_runtime.architecture_refactor_optimizer_cycle_v1`
- Hourly subroute: `chlom_runtime.run_architecture_self_awareness_subroute_v1`
- Existing wrapper: `chlom_runtime.run_css_hourly_control_cycle_v2`

Successful execution is evidence only. Parent certification remains independently governed by `ct.relay.agent-d`.
