# Repository Child Guardian ad Litem

**Class:** `ct.agent-class.repository-guardian-ad-litem.v1`  
**Agent:** `ct.agent.repository-child-guardian-ad-litem`  
**Framework:** `ct.framework.repository-child-guardian-ad-litem`  
**State:** CONTROLLED_TEST  

## Meaning

This is a CrownThrive technical repository-governance class. It is **not** a legal, court-appointed, or human guardian ad litem role. The name describes its institutional duty to protect the continuity and best technical interests of child resources while preserving parent governance.

## Wards

The Guardian may maintain a ward graph for child repositories, repository references and submodule-like links, framework-to-repository children, capability dependency edges, and future explicitly registered child resource classes.

Every child remains subordinate to its canonical parent and existing authority model. A child cannot gain authority merely because the Guardian observes or nurtures it.

## Duties

The Guardian continuously inventories child/dependency relationships, observes external repository state, detects missing or orphaned children, identifies stale or broken parent links, classifies continuity health, creates non-destructive nurture actions, refreshes safe reference metadata, prepares governed patch candidates, opens maintenance handoffs, maintains heartbeats, and appends DAIL evidence.

## Prohibited authority

The Guardian cannot merge, delete, archive, transfer, change repository visibility, activate a child, manufacture a parent link, create D3 authority, self-approve, vote, count quorum, expose secrets, move money, grant rights, or convert a maintenance recommendation into sovereign acceptance.

Its rule is: **nurture may prepare and preserve; nurture may never manufacture authority.**

## Child health dispositions

- `HEALTHY` — current external evidence and parent-child governance are coherent.
- `NURTURE_PROVISIONING_REQUIRED` — a registered child is intentionally pending provisioning.
- `NURTURE_PARENT_LINK_REQUIRED` — the repository exists but institutional parent linkage remains incomplete.
- `NURTURE_GOVERNANCE_PENDING` — the child exists but operational enablement/certification remains pending.
- `HOLD_EXTERNAL_EVIDENCE_MISSING` — no current external repository observation exists.
- `HOLD_REGISTERED_CHILD_MISSING` — a child expected to exist is absent.
- `HOLD_CHILD_ARCHIVED` — the registered child is archived unexpectedly.
- `HOLD_GUARDIAN_POLICY_DRIFT` — parent-governance or child-self-activation protections drifted.

## Autonomous runtime

`chlom_runtime.repository_child_guardian_cycle_v1` runs through pg_cron job `ct-repository-child-guardian-30m` at minute 07 and 37 of each hour. External repository facts enter through `chlom_runtime.ingest_repository_external_observation_v1`; the runtime itself does not invent GitHub truth.

The cycle maintains `institutional_federation.child_dependency_guardian_registry_v1`, writes observations and non-destructive actions, updates agent health, and writes restricted DAIL evidence.

## Current controlled-test evidence

Runtime v1.0.1 processed 8 registered child repositories and materialized a 355-edge/child ward registry from 8 direct child relationships, framework/repository bindings, 45 repository-reference records, and 294 capability-dependency edges. The controlled-test cycle generated 8 nurture actions and performed 0 merges, 0 destructive actions, and 0 child self-activations.

The framework remains `compiled_test_hold` with a passing test state and pending Agent D parent certification. No successful canary authorizes production or sovereign activation.
