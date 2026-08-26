# PentaAlumni — ThriveAlumni Human Stewardship & Governance Layer

**Machine key:** `penta.alumni`

PentaAlumni is the machine-addressable governance/stewardship layer for ThriveAlumni. It reconciles two important parts of CrownThrive history: the older civic/governance intent of ThriveAlumni and the newer emphasis on alumni continuity, contributors, mentorship, institutional memory and succession.

The result is a bounded human-governance model rather than a sovereign-government model.

## Canonical institutional role

ThriveAlumni is a human continuity and stewardship network. Through PentaAlumni it may support:

- councils and committees;
- advisory boards and review panels;
- mentor/apprentice and succession pathways;
- institutional-memory and oral-history contributions;
- subject-matter peer review;
- stewardship assignments;
- ethics/culture/canon consultation where authorized;
- human review queues delegated through PentaHybrid;
- future-leader development and handoff exercises;
- governed voting/quorum processes when an approved charter explicitly provides them.

## Authority invariant

> **Membership is not authority.**

A member, alumnus, contributor, advisor, mentor, committee, or council gains binding authority only when an explicit institutional record defines the authority.

A binding governance record should identify:

```yaml
charter_id: chlom.charter.<name>
body_id: penta.alumni.<body>
purpose: "..."
authority_class: advisory | delegated | binding
scope: []
risk_ceiling: D0 | D1 | D2 | D3
member_roles: []
eligibility_rules: []
appointment_method: "..."
term_rules: "..."
quorum: "..."
vote_rule: "..."
recusal_rules: []
conflict_rules: []
appeal_or_review: "..."
revocation_authority: "..."
evidence_targets:
  - DAIL
  - PentaDocs
```

If the record does not exist or is expired/revoked, the body remains advisory.

## Relationship to CHLOM

CHLOM remains the authority, rights, policy, capability, evidence and remedies layer. PentaAlumni does not replace CHLOM.

PentaAlumni gives CHLOM a structured human participation surface: named people, roles, terms, eligibility, conflicts, quorums, dispositions and handoff evidence. This makes human governance executable and auditable without pretending that software or alumni status creates institutional power.

## Relationship to PentaHybrid

PentaHybrid is the transaction layer between autonomous systems and accountable humans. PentaAlumni is one source of eligible human reviewers/stewards.

Example:

```text
PentaFactory proposes D2 release
        ↓
PentaAssure finds human approval required
        ↓
PentaHybrid resolves eligible reviewer role
        ↓
PentaAlumni resolves current charter/member/term/conflict state
        ↓
approval / rejection / recusal / hold
        ↓
DAIL evidence
        ↓
PentaMation resumes or remains fail-closed
```

## Relationship to PentaGeneration

PentaGeneration owns seven-generation continuity and long-horizon succession. PentaAlumni provides the living human network through which mentoring, apprenticeship, stewardship transfer, institutional-memory contribution, and successor development can occur.

Neither layer manufactures legal inheritance, ownership, equity, rights, or fiduciary authority. Those matters require the appropriate legal and CHLOM records.

## Governance object families

PentaAlumni should progressively maintain machine-readable objects for:

- `alumni_member`
- `stewardship_role`
- `council`
- `committee`
- `charter`
- `appointment`
- `term`
- `mentor_apprentice_link`
- `conflict_disclosure`
- `recusal`
- `meeting`
- `agenda_item`
- `quorum_record`
- `vote_or_disposition`
- `minority_or_dissent_record`
- `succession_assignment`
- `institutional_memory_contribution`
- `revocation_or_sunset`

Each object needs stable identity, version, source authority, current/historical state, and evidence lineage.

## PENTA five-stage mapping

- **Discover:** resolve the governing body, current charter, eligible participants, terms, conflicts, prior decisions and required evidence.
- **Govern:** enforce eligibility, role, scope, risk ceiling, quorum, vote, recusal, conflict, privacy and authority rules.
- **Execute:** convene/review/record the human governance action and produce an exact disposition.
- **Verify:** verify identities, current terms, quorum, conflicts, authority scope, decision integrity and signatures/receipts where applicable.
- **Preserve:** retain minutes, decisions, dissent, appointments, handoffs, conflicts, revocations and institutional memory in DAIL/PentaDocs.

## Public-language boundary

Public and partner-facing material should describe ThriveAlumni as CrownThrive's alumni, contributor continuity, stewardship, mentorship and human-governance network. Historical civic/governmental metaphors may be preserved in archives, but current language should not imply state sovereignty, governmental powers, public office, or authority beyond CrownThrive's own institutional charters.
