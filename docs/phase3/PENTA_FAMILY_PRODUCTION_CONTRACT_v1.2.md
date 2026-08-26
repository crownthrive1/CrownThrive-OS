# Penta Family™ Production Contract v1.2

**Owner:** CrownThrive LLC  
**Phase:** Phase 3 — Production + Convergence  
**Family status:** production / institutional control plane  
**Member maturity:** independent and evidence-gated  
**Doctrine:** Discover → Govern → Execute → Verify → Preserve

## Purpose

Penta Family v1.2 expands CrownThrive's institutional control surface beyond automation, software delivery, governance, workforce, communications, commerce, intelligence and assurance into the missing operational domains required for durable institutional administration: compliance, privacy, identity, data governance, records management, procurement, vendor governance, contract lifecycle management and quality management.

The Penta Family umbrella remains a production control plane. Registration of a child system does not promote that child to production. Every child remains independently classified as `specified`, `implemented`, `certified`, `production`, `hold` or `retired`. Only `certified` and `production` members may pass the family execution-eligibility gate, and all consequential work remains subject to CHLOM/DAIL authority, accountable ownership, PentaHybrid human gates where required, certified provider bindings, readback and preserved receipts.

## Added institutional controls

### PentaCompliance

PentaCompliance is the compliance-operations layer. It maintains obligation inventories, applicability matrices, controls, evidence requirements, compliance calendars, attestations, exceptions and remediation routing. It complements PentaPolicy, PentaLegal, PentaRisk, PentaAudit, PentaAssure and PentaOFAC. It cannot fabricate a regulatory obligation, declare legal compliance without evidence, waive an obligation or make a binding attestation without authorized human authority.

### PentaPrivacy

PentaPrivacy governs privacy inventories, consent/purpose boundaries, minimization, retention, data-subject rights, privacy-impact reviews and privacy incident routing. It cannot fabricate consent, broaden a processing purpose, waive rights or disclose restricted data. Legal interpretation remains routed through PentaLegal and accountable human authority.

### PentaIdentity

PentaIdentity governs human, agent, service and organizational identities, role bindings, lifecycle state, authentication context, access reviews and separation of duties. It is distinct from PentaCredentials: identity establishes *who/what the subject is and what role bindings exist*; PentaCredentials manages protected secret/provider credential references. Authentication or credential possession never creates role authority.

### PentaData

PentaData is the institutional data-governance layer for classifications, stewardship, schemas, data products, lineage, quality contracts, lifecycle and sharing boundaries. PentaAnalytics consumes governed data for analysis; PentaData owns the rules describing what the data is, where it came from, who stewards it and how it may be handled.

### PentaRecords

PentaRecords owns records-management semantics: authoritative copies, record classes, retention schedules, administrative/legal holds, disposition eligibility and evidence-chain integrity. It complements PentaDocs and PentaGeneration rather than replacing them. Historical evidence cannot be rewritten merely because a current record-management rule changes.

### PentaProcure

PentaProcure manages procurement intake, sourcing, comparisons, requisitions, approval packets, purchasing workflows, receiving and procurement evidence. Procurement capability never creates spend authority. Money movement remains bounded through PentaCost, PentaPay, PentaCapital, applicable approval authority and certified provider paths.

### PentaVendor

PentaVendor owns vendor/provider relationship governance: onboarding, due diligence, ownership, concentration, security/risk posture, SLAs, performance, renewals and offboarding. It does not accept vendor terms, sign agreements, approve spend, create credentials or certify technical provider adapters.

### PentaContracts

PentaContracts manages contract lifecycle mechanics: intake, templates, clause matrices, reviews, approval routing, signatures, obligations, milestones, renewals, amendments and terminations. It is not legal counsel and cannot bind CrownThrive. PentaLegal and authorized human/signatory authority remain mandatory for binding legal effects.

### PentaQuality

PentaQuality owns quality plans, acceptance criteria, nonconformances, root-cause analysis, corrective/preventive actions and continuous-improvement evidence. It cannot lower acceptance criteria after a failure, erase a nonconformance or self-certify a consequential release. PentaAssure and PentaAudit preserve independent verification.

## Expanded control planes

v1.2 adds three explicit cross-functional control planes to the existing Penta Family topology:

- **data_identity_privacy** — PentaData, PentaPrivacy, PentaIdentity, PentaRecords, PentaSecurity and PentaAudit.
- **procurement_vendor_contracts** — PentaProcure, PentaVendor, PentaContracts, PentaCapital, PentaCost, PentaPay, PentaLegal and PentaRisk.
- **quality_compliance_assurance** — PentaQuality, PentaCompliance, PentaAssure, PentaAudit, PentaRisk, PentaPolicy and PentaSecurity.

These are composition planes, not new sovereign authorities. Each participating member retains its own responsibility and boundary.

## Portal and API/MCP contract

Every newly registered member inherits the Penta Family portal contract at `/penta/{machine_key_suffix}` with overview, status, responsibilities, inputs/outputs, authority boundary, dependencies, SOP/SLA, runbooks, guides, evidence, API/MCP, changelog and support sections. `portal_state=contracted` or a generated portal payload is not evidence that a public frontend route has been deployed.

The family runtime must resolve every control-plane member to exactly one registered machine key. Unknown, duplicate or ambiguous members fail closed. API/MCP tools for these systems must be read-only until the specific write capability has an authority trace, eligible member maturity, certified provider binding and required human gate.

## Database continuity

The repository now source-controls the two production migration versions used to establish the original PentaMation/PentaHybrid/PentaAlumni/PentaInstitute/PentaSignal/PentaAssure institutional persistence layer and its explicit authenticated fail-closed policies:

- `20260826062657_penta_institutional_layers_v1.sql`
- `20260826063331_penta_institutional_sensitive_fail_closed.sql`

These files preserve reproducible migration lineage. They do not imply the nine v1.2 systems have been promoted to provider-bound database execution. Their present registry maturity remains conservative until implementation/certification evidence exists.

## Constitutional invariant

**No PENTA system manufactures authority.**

A Penta may discover facts, model conditions, prepare a packet, route an approval, execute within an already-granted capability, verify state and preserve evidence. It may not convert technical capability, access, data possession, provider credentials, membership, urgency, automation or a successful test into legal, financial, policy, privacy, security, governance, contracting or provider authority.
