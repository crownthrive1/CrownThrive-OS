# Architecture Self-Awareness Runtime Contract

Runtime owner: `ct.agent.architecture-refactor-optimizer`  
Framework: `ct.framework.architecture-self-awareness`  
Version: `1.0.0`  
State: `CONTROLLED_TEST`

## Existing scheduler binding

No new top-level scheduler is created. The architecture subroute runs inside `chlom_runtime.run_css_hourly_control_cycle_v2` through `chlom_runtime.run_architecture_self_awareness_subroute_v1`.

## Per-cycle sequence

1. Build a canonical snapshot from agent, privilege, guardian, kill-state, framework, repository, interoperability, CSS service, suite, skill and architecture-layer registries.
2. Hash every component and derive one architecture root SHA-256.
3. Compare with the prior snapshot.
4. Emit macro/micro change observations.
5. Create reconciliation actions with rollback references.
6. Synchronize all registered agent self-models.
7. Apply only safe reversible micro awareness/metadata actions.
8. Leave macro actions in HOLD for governed D2/independent review.
9. Update agent health and append restricted DAIL evidence.

## Macro rules

Add/remove operations, authority changes, parent changes, autonomy changes, vote-state changes, lifecycle authority changes, privilege changes, guardian changes, kill-state changes, framework state changes and repository governance changes are macro.

## Micro rules

Compatible label, descriptive metadata, compatible schema/contract detail and other bounded non-authority changes may be micro.

## Failure semantics

Missing evidence, kill-switch state, unsafe change classification, non-reversible action, D3 implication, secret export, destructive operation, money movement, rights grant, direct-main mutation or provider-authority inheritance fail closed.

Awareness never creates authority.
