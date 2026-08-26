# Penta Security, Identity & Trust Family

**Family ID:** `security-trust`  
**Portal:** `/io/pentas/families/security-trust`

## Story

This family protects who or what is acting, which credentials and scopes exist, what data may be used, which risks/control obligations apply, and whether a system remains inside CrownThrive's approved security/trust boundary.

It also contains the defensive/adversarial assurance loop: PentaBlue validates defensive controls, PentaRed performs sandbox-only adversarial simulation, PentaHoneyPot provides isolated ranges, PentaImmune hunts bounded software/control weaknesses and PentaEVIBuilder constructs exact evidence packages for independent certification.

## Primary members

PentaBound · PentaSecure · PentaSecurity · PentaCredentials · PentaIdentity · PentaPrivacy · PentaCompliance · PentaRisk · PentaAudit · PentaOFAC · PentaVault · PentaAuth · PentaSign · PentaImmune · PentaEVIBuilder · PentaBlue · PentaRed · PentaHoneyPot

## Responsibilities

- identity and access governance;
- credential references and lifecycle;
- privacy/purpose/minimization controls;
- compliance/risk/audit evidence;
- sanctions/fail-closed screening;
- secret/reference custody;
- authentication/signature contracts;
- defensive/adversarial control testing;
- weakness/evidence/repair-loop coordination.

## Operating flow

```text
actor/capability/request
→ PentaIdentity + PentaCredentials
→ PentaSecurity/Privacy/Compliance/Risk
→ exact scope/authority/provider checks
→ execution candidate
→ PentaAudit/PentaEVIBuilder evidence
→ PentaAssure/PentaCertify independent disposition
```

## Authority boundary

Credential possession is not permission. Security success does not waive legal/rights/economic policy. PentaRed stays inside authorized isolated ranges. PentaImmune cannot execute arbitrary commands, scan unapproved targets, mark HOLD as PASS or self-promote. D3 remains human-reserved.

## Status, incidents and recovery

Security findings route through PentaTriage/PentaStatus and the resilience family. Evidence and remediation are append-only where required; incidents are closed only after corrective action and readback prove the intended control.

## Releases and roadmap

New security capabilities require threat model, data classification, least privilege, negative tests, rollback/fallback, independent certification and exact scope. Security tooling may become more capable without receiving broader institutional authority.
