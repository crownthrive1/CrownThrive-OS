# PentaInstitute — Institutional Research, Foresight & Decision Science

**Machine key:** `penta.institute`

PentaInstitute is CrownThrive's internal think tank and decision-science function. It exists to improve institutional decisions before money, authority, engineering effort, public claims, rights, or strategic commitments are spent.

Its operating model may borrow from mature multidisciplinary research institutions: long-horizon studies, scenario analysis, systems analysis, evidence synthesis, policy research, war-gaming/tabletops, red-team challenge, decision matrices, forecasting, program evaluation and retrospective learning. This is a CrownThrive system and implies **no affiliation with RAND Corporation or any other outside think tank**.

## Core mandates

PentaInstitute owns:

- strategic and market research;
- scenario planning and foresight;
- technical/economic/legal-policy research briefs for decision support;
- competitive/ecosystem studies;
- independent red-team and assumption challenge;
- institutional experiments and program evaluation;
- cross-corridor systems analysis;
- research-method and model versioning;
- decision memos with confidence/evidence scoring;
- retrospective comparison of forecast/recommendation versus observed outcome.

It does **not** own final governance, legal advice, capital allocation, rights grants, production deployment, public policy on behalf of government, or executive authority. Recommendations flow to the accountable CrownThrive owner and CHLOM governance process.

## Research classes

PentaInstitute may classify work as:

1. **Rapid brief** — bounded question, short evidence window, decision support.
2. **Strategic study** — multi-source analysis with alternatives and explicit methods.
3. **Scenario set** — plausible futures, triggers, signposts and contingency responses.
4. **Red-team review** — adversarial challenge to a proposal, system, forecast or institutional assumption.
5. **Program evaluation** — measure whether an operating initiative produced intended outcomes.
6. **Research paper** — durable institutional intellectual property with sources, methods, versioning and publication controls.
7. **Research watch** — continuing question fed by PentaSignal with threshold-based escalation.

## Evidence standard

Every substantive output must distinguish:

- verified fact/evidence;
- management-reported information;
- external-source claim;
- model assumption;
- inference;
- scenario;
- recommendation;
- unresolved uncertainty.

The recommendation layer may be forceful, but the evidence layer must remain inspectable. Confidence must never be manufactured by writing style.

## Standard research record

```yaml
research_id: penta.institute.<corridor>.<slug>
version: 1
research_class: strategic_study
question: "..."
sponsor_role: "..."
decision_due: "..."
sources: []
assumptions: []
competing_hypotheses: []
methods: []
scenarios: []
red_team_required: true
findings: []
confidence: low | medium | high
recommendations: []
known_unknowns: []
chlom_disposition: pending | accepted | rejected | modified | hold
outcome_review_due: "..."
preservation_targets:
  - PentaDocs
  - DAIL
```

## Relationship to PentaSignal

PentaSignal watches. PentaInstitute studies.

A weak signal should not immediately become a strategic conclusion. PentaSignal preserves source/provenance/confidence and emits a research candidate. PentaInstitute then determines whether the signal merits corroboration, modeling, scenarios, a red-team exercise, or no further action.

## Relationship to ThriveAlumni

PentaInstitute should deliberately include qualified human experience from ThriveAlumni through PentaAlumni/PentaHybrid. Alumni, advisors, operators, creators, technical contributors and future stewards can participate in research panels, red teams, peer review and oral-history/institutional-memory programs without acquiring automatic binding governance authority.

## PENTA five-stage mapping

- **Discover:** frame the question; collect sources, state, assumptions, comparable cases and unknowns.
- **Govern:** apply source authority, research ethics, conflicts, confidentiality, cultural/IP constraints, publication class and human-review requirements.
- **Execute:** conduct analysis, modeling, interviews, scenarios, experiments or red-team activity.
- **Verify:** reproduce key methods where feasible, challenge assumptions, triangulate evidence and assign confidence.
- **Preserve:** archive source register, methods, models, paper versions, decisions, dissent, outcomes and retrospectives through PentaDocs/DAIL.

## Success criterion

PentaInstitute succeeds when CrownThrive can answer not only **what decision was made**, but also **what evidence existed, what alternatives were considered, what assumptions were challenged, who reviewed it, what confidence was warranted, and whether the eventual outcome supported the original reasoning**.
