# PENTA Institutional Layer Map

This document extends the PENTA doctrine into the human, research, automation, federation, sensing, and assurance layers needed for CrownThrive to operate as one governed institution rather than a collection of isolated agents and platforms.

PENTA remains governed by the canonical loop:

> **Discover → Govern → Execute → Verify → Preserve**

The new names below are not decorative aliases. Each owns a distinct institutional responsibility and must remain machine-addressable, human-readable, bounded by CHLOM authority, observable through ThriveBase, and evidence-producing through DAIL/PentaDocs.

## Canonical additions

| System | Institutional role | What it must not become |
|---|---|---|
| **PentaInstitute** | CrownThrive think tank, decision-science, research, foresight, scenario, policy-analysis and red-team function | A source of execution authority or an implied affiliation with any external think tank |
| **PentaAlumni** | ThriveAlumni human stewardship and governance interface: councils, committees, appointments, mentoring, succession, institutional memory, review and bounded participation | A sovereign government or an authority that exists merely because someone is an alumnus/member |
| **PentaHybrid** | Human + AI integration and handoff layer: human-in/on-the-loop controls, escalation, override, quorum, separation of duties and evidence packages | A bypass around CHLOM, human review, or accountable decision ownership |
| **PentaMation** | Governed automation/orchestration layer for schedules, events, jobs, queues, retries, dependencies, compensation and workflow convergence | A universal permission engine or a substitute for PentaTime, PentaRoute, CHLOM, or provider controls |
| **PentaSignal** | Strategic sensing and early-warning layer consuming internal and external signals and turning them into bounded alerts/hypotheses | A replacement for CrownLytics, CrownPulse, or verified evidence |
| **PentaAssure** | Independent assurance and certification layer aggregating tests, audits, policy conformance, release readiness and evidence sufficiency | A self-approval path for the system that performed the change |
| **PentaFederation** | Canonical one-word name for the existing Penta Federation cross-system binding and interoperability layer | A second identity system or an excuse to erase provider/platform boundaries |

**PentaInstitute is CrownThrive's own institutional research function.** It may use the operating patterns of major policy/strategy think tanks—long-range research, scenario analysis, multidisciplinary studies, decision analysis, red teams and evidence synthesis—but it has no implied affiliation with RAND Corporation or any other outside institution.

## Human governance reconciliation: ThriveAlumni

Historical CrownThrive material sometimes described ThriveAlumni in civic/governmental terms, while later material emphasized alumni, contributor continuity and stewardship. PentaAlumni resolves that tension by defining a bounded governance model:

- ThriveAlumni can host councils, committees, mentor/apprentice pathways, advisory reviews, stewardship assignments, institutional-memory contributions and succession participation.
- Membership alone creates no legal, economic, licensing, security or production authority.
- Every actionable authority must resolve to an approved charter, role, term, capability, quorum rule, risk ceiling and evidence requirement.
- CHLOM remains the authority/policy/rights system. PentaAlumni is the human governance participation surface.
- PentaHybrid handles human-agent handoff and review mechanics. PentaGeneration handles long-horizon succession and continuity.

This allows CrownThrive to preserve the valuable governance intent of the older ThriveAlumni doctrine without representing ThriveAlumni as a sovereign government.

## Operating topology

```text
CrownLytics / CrownPulse / providers / repositories / public signals
                          │
                          ▼
                    PentaSignal
                          │
                          ▼
                   PentaInstitute
             research · scenarios · red team
                          │
         ┌────────────────┴────────────────┐
         ▼                                 ▼
    Penta Control                    PentaAlumni
         │                           human stewardship
         └──────────────┬──────────────────┘
                        ▼
                   PentaHybrid
        human/AI handoff · quorum · override
                        │
                 CHLOM / DAIL gates
                        │
                        ▼
                    PentaMation
      events · schedules · queues · retries · workflows
            │              │              │
            ▼              ▼              ▼
       PentaTime       PentaRoute      Penta MCP
            └──────────────┬──────────────┘
                           ▼
                registered PENTA systems
                           │
                           ▼
                     PentaAssure
            tests · audit · certification
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
         PentaDocs                  PentaGeneration
      evidence/knowledge           continuity/handoff
             │                           │
             └─────────── PentaFederation ───────────┘
```

## Authority model

The new layers do not change CrownThrive's core authority boundaries:

- **CIE** governs cultural meaning, canon, representation, narrative continuity and cultural imprint.
- **CHLOM** governs authority, rights, policy, capability, credentials, certification requirements, evidence obligations and remedies.
- **ThriveBase** stores/coordinates operational state and evidence where bound.
- **DAIL** preserves durable evidence and audit lineage.
- **Penta Control** coordinates portfolio-level intent and bounded execution.
- **PentaMation** automates already-authorized work; it cannot manufacture authority.
- **PentaHybrid** determines when a human must enter, review, approve, override, or accept handoff.
- **PentaAlumni** provides structured human stewardship where a charter assigns it.
- **PentaAssure** independently evaluates whether the evidence is sufficient to promote a capability/release.

## PentaMation execution contract

A PentaMation workflow must carry at minimum:

```yaml
workflow_id: penta.mation.<domain>.<name>
version: 1
trigger:
  type: event | schedule | manual | dependency
risk_class: D0 | D1 | D2 | D3
authority_ref: <CHLOM capability/charter/policy reference>
owner: <accountable system or human role>
dependencies: []
human_gate:
  required: true | false
  policy_ref: <PentaHybrid rule>
idempotency_key: <deterministic key strategy>
retry_policy: <PentaRetry contract>
compensation: <rollback/remedy contract or none>
verify:
  - <readback/test/receipt requirement>
preserve:
  - <DAIL/PentaDocs evidence targets>
```

PentaTime owns temporal semantics. PentaRoute owns exact route/execution binding. PentaMation owns orchestration across them.

## PentaHybrid decision contract

PentaHybrid classifies every consequential handoff into one of five states:

1. **machine_allowed** — execution may continue inside certified bounded authority;
2. **human_review_required** — a named accountable human role must inspect evidence;
3. **human_approval_required** — execution is blocked until explicit approval/quorum is recorded;
4. **human_override_recorded** — a permitted human override changes a machine recommendation and must preserve rationale/evidence;
5. **hold_fail_closed** — authority, evidence, identity, confidence, or separation-of-duties requirements are unresolved.

This layer is the institution's answer to autonomous-system drift: automation can be broad, but accountability remains explicit.

## PentaInstitute research lifecycle

PentaInstitute converts weak signals and strategic questions into governed institutional knowledge:

```text
question / signal
  → research brief
  → source/evidence register
  → competing hypotheses
  → scenario or model
  → red-team challenge
  → findings + confidence
  → recommendation
  → CHLOM/leadership disposition
  → implementation candidate or archive
  → measured outcome
  → retrospective
```

Research outputs are recommendations and evidence, not execution permissions. PentaDocs preserves the papers, methods, models and revisions; PentaSignal continues monitoring assumptions after publication.

## PentaAlumni governance objects

PentaAlumni should eventually expose machine-readable records for:

- council and committee charters;
- appointments, terms, role classes and eligibility;
- mentor/apprentice relationships;
- meeting/decision records and recusals;
- quorum and voting rules where applicable;
- advisory versus binding dispositions;
- succession/stewardship assignments;
- institutional-memory contributions;
- conflicts of interest;
- human review queues and response SLAs;
- sunset/revocation of authority.

All records should be resolvable through CrownThrive ID and preserved through PentaDocs/DAIL.

## Systems deliberately not created

The PENTA namespace should not duplicate systems that already have an institutional owner. Therefore this pass does **not** create PentaLegal, PentaCapital, PentaImpact, PentaAnalytics, or PentaOps as top-level systems: CHLOM/Legal Depot, Holdings/ThriveFund, CII, CrownLytics/CrownPulse, and OpsOasis/Penta Control already own those responsibilities.

## Machine-readable registry

Canonical machine definitions are stored at:

`data/penta/systems.registry.json`

The registry is validated by:

`tools/penta_registry.py`

and by the GitHub workflow:

`.github/workflows/penta-registry-governance.yml`

A system may not be promoted merely because its name exists in documentation. Registry state must distinguish **specified**, **implemented**, **certified**, and **production** truth.
