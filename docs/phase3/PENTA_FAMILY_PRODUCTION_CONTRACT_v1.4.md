# Penta Family™ Production Contract v1.4

**Owner:** CrownThrive LLC  
**Phase:** Phase 3 — Execute  
**Family state:** production institutional control plane  
**Contract change:** production PentaCompliance/PentaLicense decisioning plus governed self-build coverage  
**Doctrine:** Discover → Govern → Execute → Verify → Preserve

## Executed capability

v1.4 adds production-scoped software for two exact internal control-plane capabilities:

- **PentaCompliance** evaluates applicability and evidence sufficiency against adopted obligation records. It returns evidence-satisfied or explicit hold states and never represents the result as a universal legal opinion.
- **PentaLicense** evaluates an exact asset/version/hash, rights profile, requested rights, territory, media, term, identity, terms, acceptance, risk, authority, human and provider gates. An eligible internal request can produce a hash-bound immutable grant. Amendments, renewals, suspensions and revocations append events; they never overwrite the signed grant.

The production scope is the deterministic repository/Command Center control plane. Legal attestations, signatures, provider sends, financial settlement, D3 authority and rights not already owned or controlled remain outside autonomous execution.

## Mandatory license invariants

PentaLicense must fail closed when any of the following is absent or contradictory:

1. exact asset identity, version and SHA-256;
2. adopted ownership/control or delegated sublicensing evidence;
3. requested rights within the allowed rights profile and outside prohibited rights;
4. allowed territory, media, use, term and party identity;
5. exact adopted terms and attributable acceptance;
6. evidence-satisfied PentaCompliance receipt;
7. CHLOM rights authority and accountable owner;
8. PentaHybrid approval for D2/D3 or reviewed lanes;
9. certified provider binding and readback strategy for provider effects.

Provider-ready means eligible for an independently authorized provider adapter. It does not mean the provider action already occurred.

## Compliance enforcement

PentaCompliance accepts versioned obligation records with authoritative source references and source hashes. It evaluates only adopted obligations in the supplied jurisdiction/scope and effective-date window. Unknown, malformed or unsupported source data yields `HOLD_SOURCE_INVALID`; missing control evidence yields `HOLD_EVIDENCE_GAP`.

This is how compliance is forced operationally: downstream PentaLicense issuance requires a valid hash-bound `PASS_EVIDENCE_SATISFIED` receipt. Tampering with the receipt, rights profile or request invalidates the gate.

## Governed self-build coverage

Every registered Penta member now receives the same self-build profile:

`typed gap → PentaRFA → PentaFactory candidate → acceptance/negative/stress tests → independent PentaCertify/PentaAssure evidence → PentaRelease/PentaPR/PentaMerge → provider readback → preserve`

The contract gives every member a machine route for requesting software. It does not give a member permission to write arbitrary code, self-certify, self-promote, bypass security/licensing provenance, or exercise D3 authority. The builder and certifier must be independent for certification/release.

## Exact software and evidence surfaces

- `runtime/penta_compliance_license.py`
- `runtime/penta_self_build.py`
- `data/penta/compliance-license.catalog.json`
- `data/penta/self-build.contract.json`
- `schemas/penta/compliance-license.schema.json`
- `schemas/penta/self-build-candidate.schema.json`
- `tests/test_penta_compliance_license.py`
- `tests/test_penta_self_build.py`
- `scripts/stress_penta_compliance_license.py`
- `.github/workflows/penta-institutional-services.yml`

## Certification rule

The internal software scope is production only when the exact source head passes unit, negative-control, family-census, interoperability, static-integrity and stress gates. Provider-specific or legal execution stays held until its own write/readback and authority evidence exists.

## Constitutional invariant

**No PENTA system manufactures authority.** A green software receipt proves bounded software behavior; it does not prove ownership, legal advice, signatory power, provider mutation or sovereign approval.
