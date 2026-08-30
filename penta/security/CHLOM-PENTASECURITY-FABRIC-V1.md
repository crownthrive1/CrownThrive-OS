# CHLOM + PentaCHLOM + PentaSecurity Fabric v1

Status: **source candidate / independent certification required**

## Canonical boundary

CHLOM remains CrownThrive's rights, rules, roles, revenue, records and remedies authority layer. PentaCHLOM is its governed Web2/interoperability engineering adapter; it does not manufacture CHLOM authority. PentaSecurity is the Security, Identity & Trust family orchestrator and cannot certify its own work.

Current CHLOM public baseline remains cloud/API/event-first with DAIL, Dynamic Licensing Asset objects, human approval gates, private-by-default evidence and append-only correction/version history. A public CHLOM token economy is **not** current production authority. Token semantics must remain HOLD until exact current machine/runtime evidence establishes them.

## DAIL topology correction

The verified CrownThrive runtime has three canonical DAIL systems:

1. DAIL-HUMAN — explainable, founder/approval-facing continuity.
2. DAIL-HYBRID — joint human/autonomous relay.
3. DAIL-MACHINE — machine execution and evidence lineage.

`evidence`, `decision`, and `execution` are semantic stages that may be projected across those canonical lanes. They are not replacement ledgers and must never be represented as three separate canonical DAIL systems unless a later governed migration explicitly changes the topology.

## Existing capability census

The Security, Identity & Trust family already exists. Reuse before creation. Verified current identities include PentaSecurity, PentaIAM, PentaZeroTrust, PentaSecrets, PentaPKI, PentaPolicy, PentaGuard, PentaScan, PentaThreat, PentaSIEM, PentaSOC, PentaVuln and PentaRed, plus existing related security/trust members in the family.

Requested names that are not yet proven to be distinct runtime identities are represented as alias candidates or explicit HOLD/build candidates in `penta_runtime.security_capability_bindings_v1`. A naming request is never sufficient reason to create a duplicate service.

## Security assurance state machine

The v1 kernel enforces:

```text
candidate
  -> scanned
  -> threat_modeled
  -> tested
  -> security_pass
  -> chlom_pass
  -> cie_pass (when required)
  -> certification_pending
  -> certified
  -> released
```

Every material transition requires an actor, evidence reference, a canonical DAIL lane and an Evidence/Decision/Execution semantic stage. HOLD and FAILED are explicit terminal/interruption states. Certification requires a pre-bound independent certifier and rejects originator self-certification.

The assurance event ledger is append-only. Current-state rows are projections; the event chronology is the audit history.

## Standards baseline

The machine registry version-pins the implementation baseline for NIST CSF 2.0, NIST SP 800-53 Rev. 5, NIST SP 800-207, NIST SSDF/SP 800-218, NIST SP 800-161 Rev. 1 Update 1, CISA Zero Trust Maturity Model, OWASP ASVS, OWASP API Security Top 10, CIS Controls, SLSA, ISO/IEC 27001:2022 target architecture, SOC 2 assurance target, PCI DSS payment-scope isolation and the NIST Privacy Framework.

A mapped control is not an external certification. ISO, SOC, PCI or other third-party certification/attestation claims require their actual applicable independent evidence and authority.

## Existing CSS / CHLOM integration

The existing CHLOM runtime already contains CSS service lanes, contracts, provider bindings, controls, mappings, receipts and independent-verifier assignments. This fabric must converge with those objects rather than replace them. In particular, current authorization and licensing CSS lanes already bind to CHLOM Core candidates, while provider bindings remain inactive until independently certified.

## Publisher readback

The prior report that CHLOM Continuous Publisher was failing is superseded by current runtime evidence: the workflow is active and its latest observed run is successful. Do not repair or restart it based on historical red state. Re-open only if fresh readback shows a new regression.

## Release boundary

Build -> scan -> threat model -> test -> PentaSecurity decision -> CHLOM authority/rights -> CIE when applicable -> independent PentaCertifier -> release.

D3, sovereign quorum/votes, credential creation or rotation, material money movement, final rights/legal commitments and authority expansion remain outside this D0-D2 fabric unless a separate exact current authorization says otherwise.

## Next bounded implementation work

1. Independently review and apply the v1 assurance-kernel migration only after exact-head tests/security review pass.
2. Reconcile alias candidates (PentaKeys, PentaProvenance, PentaIncident) against existing runtimes before admitting new identities.
3. Build only the verified gaps (currently SBOM, Forensics, Patch, Purple orchestration and DR identity/capability remain unresolved candidates) through existing factories.
4. Map the framework registry into existing CSS controls instead of duplicating the CSS catalog.
5. Bind production assurance events to canonical DAIL append/readback and PentaCensus/PentaContext evidence.
6. Obtain independent maturity/certification projections for PentaSecurity, PentaCHLOM and CHLOM before any production-certified claim.
