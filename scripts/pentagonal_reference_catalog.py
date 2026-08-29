"""Canonical Pentagonal terminology and paper catalog."""
from __future__ import annotations

AXES = ["truth", "authority", "execution", "interoperation", "continuity"]
AXIS_DEF = {
 "truth":"Identity, architecture, contracts, schemas, semantics, provenance and verified state representations.",
 "authority":"Decision rights, policy, consent, rights, security, legal/economic/risk bounds and capability constraints.",
 "execution":"Bounded work performed by software, agents, workflows, factories, tools, models and operational services.",
 "interoperation":"Routes, protocols, bindings, transports, events, adapters, dependencies and governed handoffs.",
 "continuity":"Evidence, lineage, reconciliation, recovery, supersession, succession, history and exact-baseline inheritance.",
}
PENTA = ("A Penta is a stable, named, contract-bounded institutional capability in PentaOS. "
         "It may be a service, control, registry, agent layer, workflow, tool, adapter, factory, "
         "evidence/knowledge component or governed composite. The name identifies an institutional "
         "role; it does not by itself grant execution, provider, legal, rights, financial, release "
         "or D3 authority. A Penta is not synonymous with an LLM or autonomous agent.")
INVARIANT = ("Documentation, terminology, family, Pentagonal axis, layer, job, lifecycle, audience and routing metadata "
             "never create maturity, execution eligibility, provider permission, credentials, legal/rights/financial/"
             "release authority, certification, production status or D3/human-reserved authority.")

PORTAL_B, PORTAL_E = "<!-- BEGIN PENTAGONAL REFERENCE PORTAL v1 -->", "<!-- END PENTAGONAL REFERENCE PORTAL v1 -->"
DEV_B, DEV_E = "<!-- BEGIN PENTAGONAL DEVELOPMENT READ ORDER v1 -->", "<!-- END PENTAGONAL DEVELOPMENT READ ORDER v1 -->"
AGENT_B, AGENT_E = "<!-- BEGIN PENTAGONAL AGENT READ ORDER v1 -->", "<!-- END PENTAGONAL AGENT READ ORDER v1 -->"
BEGIN_PORTAL, BEGIN_DEV, BEGIN_AGENT = PORTAL_B, DEV_B, AGENT_B

# term, class, definition, machine rule, source refs
FOUNDATION = [
 ("Penta","doctrine",PENTA,"Resolve stable identity and canonical registry state before treating a Penta name as a target.",["penta/registry/penta-component-registry.v1.json","PENTA-PORTAL-STANDARD.md"]),
 ("Pentagonal Architecture","architecture","The five-axis Penta architecture: truth, authority, execution, interoperation and continuity.","Use axes as architecture responsibilities, never as permission or production claims.",["penta/registry/penta-component-registry.v1.json"]),
 ("Canonical Penta","identity","A Penta identity accepted into the governed canonical namespace.","Canonical identity is required before execution can be considered, but is not sufficient authorization.",["data/penta/namespace-census.v1.json"]),
 ("Candidate Penta","identity","A preserved noncanonical reference awaiting canonicalization, aliasing, supersession, primitive/subcomponent classification or retirement.","Remain fail-closed for independent runtime/provider writes.",["data/penta/namespace-census.v1.json","PENTA-PORTAL-STANDARD.md"]),
 ("Canonicalization","governance","Governed resolution of a discovered/candidate identity into the institutional namespace without manufacturing role, maturity or authority.","Preserve the candidate until a governed disposition exists.",["PENTA-PORTAL-STANDARD.md"]),
 ("Stable identity","identity","Durable institutional identity preserved across renames, providers, routes, versions, migrations and archive transitions.","Bind software/evidence to stable IDs or machine keys, not display names.",["AGENTS.md"]),
 ("Machine key","interface","Canonical machine-resolvable identity binding a Penta to contracts and runtime/integration records.","Never derive a machine key from a display name.",["data/penta/operational-knowledge.v1.json"]),
 ("Penta family","taxonomy","The institutional home of a Penta, orthogonal to layer, job, lifecycle and audience.","Use family for institutional grouping, not task authority.",["penta/registry/penta-families.v1.json"]),
 ("Architectural layer","taxonomy","Cross-family technical/operational stack placement.","Use for architecture-first discovery; layer does not promote state.",["data/penta/operational-taxonomy.v1.json"]),
 ("Job/function","taxonomy","Normalized work class used for task-first routing.","Match intent to job IDs, then apply identity/readiness/authority/binding gates.",["data/penta/operational-taxonomy.v1.json"]),
 ("Lifecycle stage","taxonomy","When a Penta participates across discover, design, build, verify, release, operate, observe, recover, govern and evolve.","Participation is not maturity or production.",["data/penta/operational-taxonomy.v1.json"]),
 ("Audience","taxonomy","The intended machine/human consumer of a Penta contract or guide.","Audience changes presentation, not authority.",["data/penta/operational-taxonomy.v1.json"]),
 ("Execution eligibility","state","A predicate that allows a canonical identity to enter an execution decision path; necessary but never sufficient for material action.","Require eligibility plus current readiness, authority, dependencies/bindings and evidence target.",["data/penta/operational-knowledge.v1.json"]),
 ("Readiness","state","Evidence-backed current ability of a capability and dependencies to perform its bounded role.","Re-read readiness; do not treat it as permanent.",["data/penta/operational-knowledge.v1.json"]),
 ("Authority","governance","Scope-specific permission and decision-right context governing whether an actor/component may perform an action.","Ability is not permission; resolve current authority immediately before consequential execution.",["AGENTS.md"]),
 ("CHLOM","governance","CrownThrive authority, rights, consent and bounded-execution control boundary in the institutional source hierarchy.","Documentation does not override applicable CHLOM/current authority.",["AGENTS.md"]),
 ("DAIL","evidence","Append-only evidence/receipt/lineage boundary for material actions, corrections and traceability.","Preserve material readback/receipts as DAIL-compatible evidence.",["AGENTS.md"]),
 ("CIE","culture","Cultural Imprint Engine boundary for cultural meaning, narrative alignment and source-community constraints.","Cultural authority does not create ownership/license authority.",["AGENTS.md"]),
 ("Provider binding","provider","Explicit governed relationship between a stable CrownThrive capability and provider/environment/credential reference/allowed operations.","Provider capability or credentials do not independently authorize writes.",["AGENTS.md"]),
 ("Evidence","evidence","A source, receipt, readback or verified record supporting a bounded claim.","Carry subject, scope, time, source and assertion; never generalize one event into system-wide proof.",["AGENTS.md"]),
 ("Readback","evidence","Post-action observation from the target runtime/provider verifying what actually occurred.","Read back material writes before claiming convergence or retrying ambiguity.",["AGENTS.md"]),
 ("Idempotency","reliability","Contract allowing repeated delivery/retry without unintended duplicate material effects.","Retry writes only when replay safety is known; otherwise read back/reconcile first.",["data/penta/operational-knowledge.v1.json"]),
 ("Fail closed","reliability","Withhold/stop action when required authority, evidence, security, dependency, rights, recovery or rollback predicates are unresolved.","Unknown high-consequence predicates block execution.",["AGENTS.md"]),
 ("HOLD","state","Named unresolved predicate prohibiting a specific action until required conditions are satisfied.","Never turn HOLD into PASS merely because time passed or docs changed.",["AGENTS.md"]),
 ("PASS","state","Successful bounded assertion tied to exact tested scope, environment, timestamp and evidence.","PASS never silently generalizes to other state dimensions.",["AGENTS.md"]),
 ("CERTIFIED","state","Status used only with an applicable authorized certification record for the exact asserted scope.","Do not infer certification from test success or docs completeness.",["standards/pentadocs-audience-and-component-standard.mdx"]),
 ("PRODUCTION","state","Runtime/deployment state supported by applicable release/deployment/provider readback evidence.","A rendered page or merged PR does not independently prove production.",["AGENTS.md","PENTA-PORTAL-STANDARD.md"]),
 ("D3","authority","Human-reserved/sovereign consequence class unless governance explicitly changes the boundary.","Agents must not self-create or self-approve D3 authority.",["AGENTS.md"]),
 ("Source of truth","governance","Controlling institutional record for a defined state dimension under CrownThrive source precedence.","Resolve governing records before accepting projections as authority.",["AGENTS.md"]),
 ("Projection","knowledge","Downstream representation such as PentaDocs, websites, dashboards or provider UIs.","Use for presentation/discovery; projections can drift from canonical state.",["AGENTS.md"]),
 ("Supersession","continuity","Preserve-and-replace relationship linking a successor to an older record/component/version without deleting history.","Preserve predecessor identity/effective period and successor links.",["AGENTS.md"]),
 ("Lineage","continuity","Traceable history connecting identities, versions, evidence, actions, corrections, releases and supersession.","Carry lineage through transforms/handoffs.",["AGENTS.md"]),
 ("Exact-head","release","Discipline binding approval/tests/release to one exact commit or artifact, not a moving branch assumption.","If the head moves, re-evaluate the new bytes.",["data/penta/operational-knowledge.v1.json"]),
 ("Agent ingestion","agentic","Deterministic loading of Pentagonal reference metadata, Penta routing records, constraints and target contracts before routing/execution.","Load machine manifests first, then resolve live authority/readiness/bindings.",["data/penta/agent-knowledge.v1.json"]),
 ("Handoff envelope","interoperation","Task/correlation, origin/target, job, authority, dependency, idempotency, expected readback and evidence context carried between Pentas.","Never strip authority/evidence/correlation context during routing.",["pentas/integrations.mdx"]),
]

# id, title, audience, page type, thesis, five section pairs
PAPERS = [
 ("penta-doctrine","Penta Doctrine","operator","doctrine","What a Penta is, is not, and the minimum anatomy separating identity, capability, authority, state and evidence",[
  ("Definition",PENTA),("Minimum anatomy","Stable identity, role, family, architecture coordinates, jobs/lifecycle/audiences, contracts, authority boundaries, dependencies, status, evidence, ownership and supersession form the minimum institutional anatomy."),
  ("Not an automatic agent","Some Pentas are agentic; others are deterministic controls, registries, workflows, integrations, factories, knowledge/evidence components or composites."),
  ("State invariant","`DOCUMENTED ≠ ROUTABLE ≠ EXECUTION-ELIGIBLE ≠ AUTHORIZED ≠ CERTIFIED ≠ PRODUCTION`. Each dimension needs its own evidence."),
  ("Creation/evolution","New names enter candidate/canonicalization unless governed. Stable identity survives provider/route/version change and history is preserved through supersession.")]),
 ("pentagonal-architecture","Pentagonal Architecture","developer","doctrine","The canonical five-axis architecture and how it complements family/layer/job/lifecycle/audience taxonomies",[
  ("Five axes","Truth defines meaning; authority defines permission/bounds; execution performs work; interoperation connects bounded capabilities; continuity preserves evidence/history/recovery."),
  ("Separation","No single component silently becomes truth, permission, execution, transport and proof merely because it can technically touch multiple domains."),
  ("Operating coordinates","Family=home, layer=placement, job=work, lifecycle=when, audience=consumer. These coordinates complement the five axes."),
  ("Design test","Ask: What is true? Who/what may act? What executes? How do parts interoperate? How is continuity preserved? Missing high-consequence answers are HOLDs/gaps."),
  ("Durability","Providers and mechanisms may change while stable identities, contracts and five-axis separation preserve institutional coherence.")]),
 ("penta-identity-namespace","Penta Identity & Namespace","developer","reference","Canonical identity, candidate preservation, machine keys, aliases and supersession for a growing namespace",[
  ("Identity before implementation","Institutional roles and machine keys outlive provider/UI implementations."),("Canonical/candidate lanes","Canonical identities may enter normal gates; candidates remain fail-closed until governed disposition."),
  ("Aliases","Aliases preserve compatibility without multiplying authority or creating duplicate systems."),("Machine resolution","Use namespace census plus operational/agent manifests to resolve exact identities and provenance."),
  ("History","Retired/deprecated/superseded names remain traceable so old evidence stays interpretable.")]),
 ("penta-authority-evidence-state","Penta Authority, Evidence & State","operator","doctrine","Separate authority, readiness, evidence, certification, release and production so confidence never substitutes for proof",[
  ("Independent dimensions","Phase, version, lifecycle, maturity, readiness, evidence, write scope, rights/legal/economic, deployment and docs state stay independent."),
  ("Authority path","Consequential action requires current scope-specific authority, risk-compatible bounds and applicable security/rights/economic predicates."),
  ("Evidence","A provider response, workflow, payment or page proves only its exact observed event."),("Readback","After material writes, re-read target state and reconcile ambiguity before retry."),
  ("Claims","Documentation can explain evidence/HOLDs but cannot itself manufacture production, rights, settlement, entitlement or provider-wide authority.")]),
 ("penta-development-contract","Penta Development Contract","developer","developer","Minimum engineering contract for building/extending a Penta without undocumented coupling or authority",[
  ("Read order","Resolve Pentagonal architecture, target identity, operational classifications, machine record, source contracts, authority and dependencies before code changes."),
  ("Contracts","Version inputs/outputs/errors/events/state/auth/idempotency/retries/timeouts/providers/observability/evidence/compatibility/migration."),
  ("Tests","Cover authorization denial, dependency outage, provider refusal, timeout, duplicates, partial writes, stale evidence, reconciliation and rollback."),
  ("Interoperation","Prefer governed PentaRoute/MCP/Event/Hook/Stream/Bind contracts over point-to-point coupling."),
  ("Release","Validate/release exact tested head and read back provider/runtime state before production claims.")]),
 ("penta-agent-ingestion-routing","Penta Agent Ingestion & Routing","developer","developer","How agents ingest Penta knowledge, choose targets and remain fail-closed",[
  ("Boot","Load Pentagonal reference → agent knowledge → target contracts → current status/authority/dependencies/bindings."),
  ("Routing","Normalize intent to jobs, filter by layers/family, prefer canonical identities and narrowest capable target."),
  ("Execution gate","Verify canonical identity, eligibility, readiness, authority, dependency health, applicable binding, idempotency and expected readback."),
  ("Handoffs","Carry correlation, authority, dependency, retry/idempotency and evidence context."),
  ("Failure","Ambiguity routes to docs/search/govern/observe/recover. Never invent endpoints, permissions, PASS, PRODUCTION or D3.")]),
 ("penta-interoperation-handoffs","Penta Interoperation & Handoffs","developer","developer","How Pentas connect through explicit routes, events and dependency contracts while preserving authority/evidence context",[
  ("Boundary","Declare exact source/target identities, versions, environments, data class, authority and dependencies."),("Transport is not authority","Reachability, credentials, API/MCP/queue/webhook access do not independently authorize material mutation."),
  ("Envelope","Carry correlation, authority, idempotency, expected result/readback and evidence destination."),("Failure semantics","Define timeout, retry, duplicate, partial delivery, provider refusal, schema drift and compensation/reconciliation."),
  ("Providers","Keep provider adapters behind stable institutional identities so vendor change does not fragment the Penta model.")]),
 ("penta-lifecycle-reliability","Penta Lifecycle, Reliability & Recovery","operator","runbook","Connect lifecycle participation to observability, incident response, recovery and continuity",[
  ("Lifecycle","Participation in discover/design/build/verify/release/operate/observe/recover/govern/evolve is timing, not permission/production."),
  ("Observable minimum","Resolve readiness, version/release, dependencies, last readback, incidents/errors, evidence freshness and owner."),
  ("Recovery taxonomy","Classify retry, reconcile, restore, rollback, forward-fix, dependency HOLD or external/provider HOLD; stop unsafe retries."),
  ("Closure","Read back recovered state, preserve incident/recovery evidence, update status and own follow-up defects."),
  ("Continuity","Backups/history/supersession/succession must leave the next operator/agent an exact inheritable baseline.")]),
 ("penta-documentation-semantics","Penta Documentation & Semantic Continuity","operator","doctrine","PentaScribe/PentaDocs responsibilities for terminology, corrections and machine-readable knowledge continuity",[
  ("Semantics","PentaScribe governs canonical language, aliases, terminology discovery and glossary/dictionary/index/FAQ compilation."),
  ("Projection","PentaDocs is governed knowledge projection; rendering providers are replaceable and do not become institutional authority."),
  ("One source","Human guides and agent manifests derive from shared identity/taxonomy records to prevent separate documentation universes."),
  ("Corrections","Preserve + supersede + reconcile; do not rewrite historical material to sound current."),
  ("Freshness","Docs/manifest drift from production versions, providers, access model or contracts is an institutional-health defect.")]),
 ("penta-operating-model","Penta Operating Model","operator","workflow","End-to-end operating cycle from discovery/routing through bounded execution, evidence, recovery and evolution",[
  ("Discover/classify","Resolve task → job/layer/family → canonical target rather than choosing by name similarity."),
  ("Prepare","Resolve status, dependencies, authority, contracts, providers, evidence target and recovery path."),
  ("Execute","Invoke the narrowest bounded interface with correlation/idempotency inside explicit authority/risk ceilings."),
  ("Verify","Read back actual result, emit evidence, update status and route downstream work; request success is not full convergence."),
  ("Recover/evolve","Failures route observe/recover/govern; changes preserve version/release/docs/status/supersession lineage.")]),
]
