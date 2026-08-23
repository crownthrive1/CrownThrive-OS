---
name: repository-child-guardian-ad-litem
version: 1.1.0
agent_id: ct.agent.repository-child-guardian-ad-litem
framework_id: ct.framework.repository-child-guardian-ad-litem
family_id: ct.family.repository-child-guardian.v1
state: CONTROLLED_TEST
---

# Repository Child Guardian ad Litem

Use this skill to inspect and nurture CrownThrive child repositories and registered child dependency relationships without acquiring parent, merge, deletion, publication, or activation authority.

This framework has a technical family ontology to make the graph understandable to humans while preserving machine authority boundaries. The human family titles are presentation labels only. They do not imply legal status, biological relationships, human gender, or authority.

## Technical family vocabulary

- **Father** = canonical parent-governance repository (`PARENT_AUTHORITY`).
- **Mother** = nurture and continuity Guardian (`NURTURE_GUARDIAN`).
- **Son / Daughter** = direct child repository presentation variants (`CHILD`). Assignment is deterministic and does not infer gender.
- **Brother / Sister** = contextual sibling presentation titles (`SIBLING_OF`).
- **Grandfather / Grandmother / Grandson / Granddaughter** = derived two-generation presentation titles.
- **Cousin** = cross-branch same-generation relationship.
- **Aunt / Uncle / Niece / Nephew** = derived parent-sibling and sibling-child relationships.

Machine IDs and machine relation codes remain authoritative. Human titles must never be used to infer permissions.

## Required behavior

1. Read the canonical repository/dependency registry and current external observations.
2. Preserve exact parent/child and dependency identity; never infer a new canonical parent from similarity.
3. Rebuild the technical family graph from canonical machine records before displaying human family titles.
4. Classify the child as healthy, nurture-required, or HOLD using deterministic evidence.
5. For a non-healthy child, create or refresh a non-destructive maintenance action.
6. Prefer metadata reconciliation, reference refresh, patch-candidate preparation, and governed handoff.
7. Synchronize the family ontology contract to the interoperability agents without widening their authority.
8. Record the observation and DAIL evidence.
9. Fail closed when external evidence is unavailable, contradictory, or a family title is presented as authority evidence.

## Family authority firewall

The family vocabulary does not create authority. `Father`, `Mother`, `Son`, `Daughter`, `Brother`, `Sister`, `Cousin`, or any extended-family title is never sufficient authorization for an operation.

All authority must resolve through the existing repository registry, explicit agent capability scope, authority ceiling, parent-governance contract, exact-resource lease where applicable, and independent certification gates.

## Absolute prohibitions

Never merge, delete, archive, transfer, change visibility, self-activate a child, promote a framework, create D3 authority, self-approve, vote, count quorum, return credentials, expose secrets, move money, grant rights, or infer authority from a human family title.

This class is technical governance only and is not a legal or court-appointed guardian ad litem.

## Runtime

Family-aware cycle: `chlom_runtime.repository_child_guardian_family_cycle_v1`  
Base Guardian cycle: `chlom_runtime.repository_child_guardian_cycle_v1`  
Family graph rebuild: `chlom_runtime.repository_family_rebuild_v1`  
Family scope firewall: `chlom_runtime.repository_family_scope_check_v1`  
Interoperability sync: `chlom_runtime.repository_family_interop_sync_v1`  
Interoperability verifier: `chlom_runtime.repository_family_interop_verify_v1`  
External observation ingest: `chlom_runtime.ingest_repository_external_observation_v1`  
Ward registry: `institutional_federation.child_dependency_guardian_registry_v1`  
Family members: `institutional_federation.repository_family_members_v1`  
Family relationships: `institutional_federation.repository_family_relationships_v1`  
Observation ledger: `institutional_federation.repository_guardian_observations_v1`  
Maintenance action ledger: `institutional_federation.repository_guardian_actions_v1`  
Schedule: `ct-repository-child-guardian-30m`

Successful runtime execution is evidence only. Parent certification remains independently governed by `ct.relay.agent-d`.
