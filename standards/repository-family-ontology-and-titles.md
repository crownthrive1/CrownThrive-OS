# Repository Family Ontology and Human Titles Standard v1.1

## Scope

This standard applies only to `ct.framework.repository-child-guardian-ad-litem` and `ct.family.repository-child-guardian.v1`.

Human family titles exist to make the repository/dependency graph easier to understand. They are presentation labels over canonical machine relationships. They do not imply legal status, biological relationships, human gender, ownership, merge authority, certification authority, or any other permission.

## Root household

| Human title | Machine role | Resource |
| --- | --- | --- |
| Father | `PARENT_AUTHORITY` | `ct.repo.CrownThrive-OS` |
| Mother | `NURTURE_GUARDIAN` | `ct.agent.repository-child-guardian-ad-litem` |

The Father title reflects the existing canonical parent repository. The Mother title reflects the bounded nurture/continuity Guardian. Authority comes from the underlying repository and agent contracts, never the title.

## Direct children

Direct registered child repositories receive deterministic Son/Daughter presentation variants by stable lexical ordinal parity. This assignment has no gender semantics and no authority effect.

Current presentation assignments:

1. `ct.repo.chlom` — Son
2. `ct.repo.cie` — Daughter
3. `ct.repo.convergent-ecosystem` — Son
4. `ct.repo.corridor-architecture` — Daughter
5. `ct.repo.hybrid-incubator` — Son
6. `ct.repo.mm-suites` — Daughter
7. `ct.repo.one-seat` — Son
8. `ct.repo.thrive-flywheel` — Daughter

Sibling titles are contextual: a Son is presented as Brother to siblings; a Daughter is presented as Sister.

## Derived extended relationships

Framework packages associated with each child branch are represented as Grandchildren relative to the root household. Across separate child branches, those framework packages are Cousins. A sibling repository is presented as Aunt or Uncle relative to a sibling branch's framework package, and the framework package is presented as Niece or Nephew in the reciprocal direction.

Supported human titles include Father, Mother, Parent, Son, Daughter, Child, Brother, Sister, Sibling, Grandfather, Grandmother, Grandparent, Grandson, Granddaughter, Grandchild, Cousin, Aunt, Uncle, Niece, and Nephew.

## Machine relations

Machine-readable relations include `PARENT_OF`, `GUARDIAN_OF`, `CHILD_OF`, `GUARDED_BY`, `SIBLING_OF`, `GRANDPARENT_OF`, `GRANDGUARDIAN_OF`, `GRANDCHILD_OF`, `GRANDGUARDED_BY`, `COUSIN_OF`, `PARENT_SIBLING_OF`, and `SIBLING_CHILD_OF`.

The machine relation is authoritative. The human title is always a projection of that relation.

## Authority firewall

A family title must never satisfy an authorization check. The system must reject any request whose only authority evidence is a family title.

Guardian-allowed operations remain bounded to observation, inventory, classification, registry reconciliation, reference refresh, patch-candidate preparation, governed maintenance handoff, DAIL evidence, family graph read, and family graph reconciliation.

Guardian-forbidden operations remain merge, deletion, repository archive, transfer, visibility mutation, child self-activation, self-approval, sovereign voting, D3 action, credential or secret export, money movement, and rights grants.

## Interoperability rule

Interoperability agents consume machine relation codes and may project human titles for explanation. They must preserve `authority_inference_from_titles=false` and `human_titles_display_only=true`.

## Certification

Framework Factory compilation may test the ontology and its authority firewall, but canonical parent certification remains independently governed by `ct.relay.agent-d`. Runtime PASS does not equal sovereign or parent certification.
