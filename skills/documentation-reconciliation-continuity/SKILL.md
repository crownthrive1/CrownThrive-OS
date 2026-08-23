# Documentation Reconciliation & Continuity Skill

## Identity

- Framework: `ct.framework.documentation-reconciliation-continuity`
- Skill: `ct.skill.documentation-reconciliation-continuity.v1`
- Authority ceiling: D2
- Default execution: D0/D1 only
- Parent certification: `ct.relay.agent-d`
- Security lane: `ct.relay.agent-s`
- Documentation owner: `ct.chlom.agent.docs`

## Objective

Keep CrownThrive institutional documentation current, complete, internally connected, recoverable, source-grounded, and machine-addressable while preserving historical truth and fail-closed Phase 3 gates.

## Mandatory two-pass sprint

### Pass A — stale-state reconciliation

1. Freeze sprint scope and baseline commit.
2. Inspect each scoped page against current canonical names, phase namespaces, lifecycle states, source authority, provider/API state, legal/rights/economic state, and known founder adjudications.
3. Apply only evidence-backed corrections.
4. Preserve literal external/provider identifiers and historical quotations.
5. Version material corrections; never silently overwrite accepted history.
6. Emit `docs_updated`, `docs_no_change`, or `docs_delta_opened` per page.

### Pass B — gap closure and continuity

1. Identify missing definitions, evidence qualifiers, relationships, phase impacts, machine seeds, runbooks, legal/support/API boundaries, and article-rebuild dependencies.
2. Close gaps supported by accepted evidence.
3. Add internal links to canonical sources, registries, standards, phase gates, successor/predecessor records, and operational runbooks.
4. Never invent missing source facts, phase definitions, provider capability, legal status, rights, prices, or production state.
5. Open explicit unresolved records when evidence is insufficient.
6. Update article-rebuild and Phase 3 seed queues.

## Article rebuild rule

The 795-title recovered Help Center estate is a forensic baseline. Every recovered title must end in exactly one governed terminal disposition:

- substantive canonical article;
- merged successor;
- permanent redirect;
- restricted/private record;
- superseded historical record; or
- explicit unresolved-source record.

A title, placeholder, or navigation label is not a completed article.

## Internal-link continuity rule

A substantive public-safe article should ordinarily include at least two meaningful internal continuity links. Prefer:

- source authority / evidence standard;
- canonical platform or framework registry;
- applicable legal / rights / security standard;
- phase readiness or roadmap gate;
- operational workflow / runbook;
- alias, predecessor, successor, or historical lineage record.

Do not add decorative links. Links must help a future operator reconstruct meaning, authority, state, or execution.

## Phase impact rule

Every material sprint records impacts across the current named Phase 1–10 roadmap and keeps explicit impact slots for Phase 11–20. Until authoritative definitions for 11–20 are recovered or adopted, those slots remain `reserved_horizon` / `definition_required`; they are not assigned invented objectives.

## RMCT rule

The founder shorthand `RMCT` is preserved as a literal institutional token because current recovered evidence does not establish its expansion. Do not fabricate an acronym expansion. Bind the token to this framework packet with `definition_state = needs_owner_validation` until stronger authority resolves it.

## Output contract

Each sprint emits:

- sprint ID and baseline commit;
- scoped page list;
- Pass A stale findings and corrections;
- Pass B gap findings, closures, and unresolved deltas;
- internal-link edges added or verified;
- article-rebuild queue changes;
- Phase 3 readiness contributions and remaining blockers;
- Phase 1–20 impact vector;
- validation results;
- rollback reference;
- DAIL / Factory references when available;
- exact next-state handoff.

## Prohibited

- exposing secrets or restricted source bodies;
- promoting unknown to current/production;
- treating provider evidence as institutional authority;
- deleting historical records to reduce clutter;
- inventing Phase 11–20 definitions;
- self-certifying D2/D3 conclusions;
- weakening merge, rights, security, legal, economic, or Phase 3 gates to make a sprint pass.
