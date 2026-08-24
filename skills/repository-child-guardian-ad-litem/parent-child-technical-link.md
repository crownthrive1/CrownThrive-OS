# Repository Parent-Child Technical Link Skill v1

Owner: `ct.agent.repository-child-guardian-ad-litem`  
Verifier: `ct.relay.agent-d`  
Authority: A2 / D2 maximum; automatic authority effect: none.

## Objective

Convert a registered physical child from "parent link missing" to `TECHNICALLY_LINKED_PENDING_GOVERNANCE` only when exact current evidence is available.

## Inputs

- registered parent and child repository IDs;
- immutable child GitHub repository ID;
- exact parent and child canonical Git SHAs;
- fresh provider observations for both repositories;
- active fail-closed Guardian binding;
- authority-safe family relationships;
- controlled-test parent-child interoperability contract;
- source/evidence reference.

## Execution

1. Verify both repository registry rows and their parent-child relationship.
2. Verify exact current GitHub observations and reject stale heads.
3. Verify the Guardian can observe/nurture/open handoffs but cannot merge, delete, archive, change visibility or self-activate the child.
4. Verify family Parent/Child and Guardian relationships with `authority_inference_prohibited=true`.
5. Verify `ct.interop.contract.repository-parent-child-link.v1`.
6. Append an exact link receipt and DAIL event.
7. Reconcile parent/child exact-head metadata.
8. Resolve `NURTURE_PARENT_LINK_REQUIRED`.
9. Run the Guardian again; expect `NURTURE_GOVERNANCE_PENDING` until independent governance succeeds.
10. Feed the new repository-system/contract state to interoperability and architecture reconciliation.

## Prohibitions

This skill cannot set `linked_governed`, enable operations, create/cast votes, change quorum, grant D3, certify its own work, activate protected runtime, mutate rights/economic state, or invoke Founder Override.

A technically green but governance-deadlocked source packet must route through `ct.control.founder-override-ask-first-deadlock.v1` and stop at `AWAITING_FOUNDER_CONFIRMATION` until the Founder explicitly confirms.
