# PENTA Institutional Operating Fabric v1.2

**Owner:** CrownThrive LLC  
**Phase:** Phase 3 — execution/institutionalization  
**Status:** Implemented source layer; provider/runtime certification remains evidence-gated  
**Doctrine:** Discover → Govern → Execute → Verify → Preserve

## 1. Purpose

The PENTA Institutional Operating Fabric is CrownThrive's shared institutional-services plane. It gives the Convergent Ecosystem a bounded nervous system for sensing, research, analytics, policy, risk, capital, impact, legal operations, ethics, human governance, automation, assurance, audit, security, knowledge, continuity and federation.

It is not a second corporate hierarchy and it does not erase the accountability of CrownThrive LLC, CrownThrive Holdings, ThriveFund, the CrownThrive Impact Institute, CHLOM, DAIL, ThriveAlumni, CrownLytics, CrownPulse, provider controls, or authorized human officers/counsel. PENTA makes those responsibilities machine-addressable, interoperable, testable and governable.

The constitutional rule is absolute:

> No PENTA system may manufacture legal, economic, security, licensing, policy, governance, fiduciary or provider authority.

A workflow may optimize inside authority already granted. It may prepare evidence, proposals, drafts, models, alerts, decisions and execution packets. It may not infer permission merely because an action is technically possible.

## 2. Four operating planes

### Intelligence plane

**PentaSignal** senses weak signals, anomalies and early-warning conditions. **PentaAnalytics** reconciles metric semantics, lineage, evidence and analytical models. **PentaInstitute** converts signals and evidence into studies, scenarios, forecasts, red teams and decision science. PentaInstitute may employ methods associated with major policy/research institutions—systems analysis, scenario planning, operations research, program evaluation and red teaming—without implying affiliation with RAND or any other external organization.

### Governance and allocation plane

**PentaPolicy** manages policy lifecycle and obligations-to-controls mappings. **PentaRisk** owns enterprise-risk representation and escalation. **PentaCapital** builds capital-allocation and treasury decision packets. **PentaImpact** evaluates social, cultural, community and program outcomes. **PentaLegal** operates legal workflows and counsel-routing. **PentaEthics** performs integrity, fairness, conflict and cultural-alignment review. **PentaAlumni** exposes ThriveAlumni councils, committees, stewardship and succession as governed human structures. **PentaHybrid** is the human-machine integration gate that resolves review, approval, quorum, separation of duties, override and accountable handoff. CHLOM/DAIL remain the authoritative source for capabilities, role authority, policy provenance and bounded delegation.

### Execution plane

**PentaMation** owns durable automation/workflow orchestration. **PentaTime** owns temporal semantics. **PentaRoute** owns exact routing. **Penta MCP** owns machine capability invocation. **PentaFactory** builds and promotes software/configuration artifacts through certified lanes. Execution must use explicit provider bindings and cannot bypass human, security, rights, commercial or governance controls.

### Assurance and continuity plane

**PentaAssure** performs pre-release/readiness evidence aggregation and bounded capability certification. **PentaAudit** independently tests executed controls, findings and remediation after or outside the release gate. **PentaSecurity** coordinates security posture, incident-governance and protective actions without self-expanding privilege. **PentaDocs** preserves institutional knowledge and current-versus-historical truth. **PentaGeneration** owns long-horizon succession and seven-generation continuity. **PentaFederation** manages trust and interoperability across repositories, systems and providers.

## 3. New institutional services

### PentaCapital

PentaCapital is the capital-governance intelligence layer aligned to CrownThrive Holdings and ThriveFund. It models capital allocation, treasury posture, liquidity/runway, concentration, funding envelopes, capital-stack alternatives and portfolio tradeoffs. Its output is an approval-ready decision packet—not money movement. Transfers, trades, borrowing, asset pledges, account changes and other binding financial actions require separately authorized provider rails plus a traceable accountable owner and governance disposition.

### PentaImpact

PentaImpact is the measurement substrate aligned to the CrownThrive Impact Institute. It formalizes logic models, outputs, outcomes, attribution, counterfactual reasoning, evidence quality, community benefit, cultural benefit and SROI-style analysis. It cannot award grants/funding or certify impact claims by itself.

### PentaAnalytics

PentaAnalytics is the cross-ecosystem analytics layer. CrownLytics and CrownPulse remain products/sources; PentaAnalytics consumes their governed outputs and adds a shared metric registry, semantic definitions, lineage, freshness, grain, transformations, sensitivity classification, comparative analysis and forecast/causal modeling. No transformation may silently change a metric's meaning or source-of-truth status.

### PentaLegal

PentaLegal is legal operations, not legal counsel. It tracks obligations, rights, jurisdictions, effective periods, contracts, licensing, legal holds, review status, deadlines and counsel escalation. It can build counsel-ready packets and monitor obligations. It cannot provide legal representation, sign agreements, waive rights, settle claims, make admissions or bind CrownThrive.

### PentaRisk

PentaRisk provides the enterprise risk model: taxonomy, likelihood, impact, velocity, exposure, tolerance, control mapping, residual risk, ownership and escalation. Risk acceptance remains an accountable human/governance act where policy requires it.

### PentaAudit

PentaAudit is the independent control-verification lane. It records control objective, test method, sample/evidence, severity, finding, owner, remediation due date, re-test and closure state. PentaAudit does not replace PentaAssure: PentaAssure answers whether an artifact/capability is sufficiently evidenced for certification or release; PentaAudit answers whether executed institutional controls actually remained effective and whether remediation is real.

### PentaPolicy

PentaPolicy manages policy draft, provenance, version, scope, effective dates, obligations, mapped controls, exceptions, supersession and interpretation routing. Binding policy authority must point back to an adopted CHLOM/DAIL-recognized source and required governance disposition.

### PentaEthics

PentaEthics provides structured ethics and integrity review across conflicts of interest, fairness, cultural alignment, community impact, institutional values and decision externalities. It can escalate or recommend holds where adopted policy allows. It does not create an unchartered veto or replace legal/compliance review.

### PentaSecurity

PentaSecurity coordinates security posture, threats, controls, incident-governance, protective-action proposals and verification. Disruptive actions—credential rotation, access revocation, service disablement, quarantine, key deletion, privilege change—require explicit pre-authorized incident authority or a separately approved capability and certified provider route. Evidence suppression and self-expansion of privilege are prohibited.

## 4. Common decision packet

All institutional services exchange consequential recommendations through `schemas/penta/decision-packet.schema.json`. The packet records:

- packet ID and issuing system;
- action class and decision summary;
- evidence references;
- risk and impact scores;
- required capability;
- PentaHybrid human-gate roles/quorum;
- approvals and timestamps;
- expiration, override and rollback policy;
- audit correlation identifier;
- authority trace to CHLOM/DAIL, accountable owner and, where necessary, provider binding;
- lifecycle state: proposed, approved, rejected, expired, executed or held.

A syntactically valid packet is not authorization. The runtime evaluates whether it is advisory-ready, requires governance, is represented as authorized-ready for a separately certified execution path, or must hold fail-closed.

## 5. Cross-system operating loop

```text
PentaSignal
    ↓
PentaAnalytics
    ↓
PentaInstitute
    ↓
PentaPolicy / PentaRisk / PentaCapital / PentaImpact / PentaLegal / PentaEthics
    ↓
PentaAlumni ↔ PentaHybrid ↔ CHLOM / DAIL
    ↓
PentaMation
    ↓
PentaTime + PentaRoute + Penta MCP
    ↓
PentaFactory / CrownThrive platforms / certified providers
    ↓
PentaAssure + PentaSecurity
    ↓
PentaAudit
    ↓
PentaDocs + PentaGeneration
    ↓
PentaFederation
    ↺
```

This closes the institutional loop as: **sense → quantify → study → govern → allocate → human-check → automate → execute → assure → audit → preserve → learn.**

## 6. Promotion doctrine

The registry may say `implemented` when source artifacts, machine contracts and deterministic runtime logic exist. `certified` requires defined evidence and independent checks. `production` additionally requires verified provider/runtime bindings and current production readback. Documentation, intent, a PR merge, or a technically callable API is never enough on its own to promote maturity.

No subsystem may promote itself merely because it generated its own evidence. Consequential certification must preserve independence and separation of duties.

## 7. Runtime artifacts

- `data/penta/institutional-services.registry.json` — bounded institutional-services registry and plane map.
- `schemas/penta/decision-packet.schema.json` — portable decision-envelope contract.
- `runtime/penta_institutional_services.py` — fail-closed deterministic policy/evaluation runtime.
- `tests/test_penta_institutional_services.py` — regression tests for authority boundaries.
- `.github/workflows/penta-institutional-services.yml` — CI verification lane.

These artifacts are additive. They do not erase existing canonical PENTA registry material and should be folded into the master registry only after this source layer passes repository governance and any required promotion checks.
