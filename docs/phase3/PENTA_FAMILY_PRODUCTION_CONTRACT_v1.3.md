# Penta Family™ Production Contract v1.3

**Owner:** CrownThrive LLC  
**Phase:** Phase 3 — Production + Convergence  
**Family status:** production / institutional control plane  
**Interoperability fabric:** production when exact-head certification passes  
**Child maturity:** independent and evidence-gated  
**Doctrine:** Discover → Govern → Execute → Verify → Preserve

## Purpose

Penta Family v1.3 institutionalizes a single interoperable machine fabric across the registered Penta estate. It does not flatten the estate into one omnipotent agent. Each Penta keeps its own responsibility, maturity, authority boundary, provider bindings, human gates, evidence, and lifecycle.

The v1.3 protocol closes the gap between registration and actual cross-Penta operability by introducing a canonical interoperability registry, envelope schema, runtime evaluator, coverage/certification report, and production CI gate.

## Production topology

The interoperability spine is:

- **PentaControl** — bounded coordination and dispatch.
- **PentaMCP** — API/MCP/tool contract interoperability.
- **PentaRoute** — exact route selection.
- **PentaFederation** — cross-system, repository, and provider boundaries.
- **PentaDocs** — institutional source/evidence projection.
- **PentaAssure** — independent assurance and certification.
- **PentaError** — typed failure envelopes.
- **PentaLogger** — structured evidence.
- **PentaTrace** — trace/correlation lineage.
- **PentaMetric** — runtime measurements.

The existing observability catalog is now a required family catalog, making PentaError, PentaLogger, PentaTrace, and PentaMetric part of the same family census and portal topology as every other Penta.

## Machine envelope

Every interoperable handoff is represented by `ct.penta.interoperability-envelope.v1` and includes:

- exact source and target `penta.*` machine keys;
- operation and requested effect;
- D0-D3 risk class;
- trace and correlation identifiers;
- idempotency key;
- evidence references;
- CHLOM/DAIL authority trace and accountable owner;
- PentaHybrid human-gate state;
- provider-effect flag and certified binding reference;
- verification/readback strategy;
- bounded metadata;
- SHA-256 envelope receipt.

Unknown identities and malformed envelopes fail closed.

## Execution rule

Family-wide addressability does not promote child maturity.

`specified` and `implemented` systems can exchange bounded non-execution work where their domain contracts permit it. `execute` requires both source and target to be `certified` or `production`, an authority trace, required human gates, exact provider binding for provider effects, readback, and preserved evidence.

The nine institutional controls added in v1.2 remain `implemented`. v1.3 makes them interoperable; it does not falsely certify their consequential execution.

## Certification rule

The production fabric is certified only when the exact source head proves all of the following:

- all machine JSON contracts parse;
- runtime surfaces compile;
- Penta Family regression tests pass;
- Penta runtime-suite tests pass;
- institutional service/control tests pass;
- observability tests and self-test pass;
- provider-control-plane contracts pass;
- runtime Penta inventory equals the Penta Family census;
- every Penta dependency resolves to a registered Penta;
- the required interoperability spine exists;
- the required observability spine exists;
- there are zero protocol blockers.

The certification runtime emits `PASS / production` only after those checks. Otherwise the fabric reports `HOLD / hold_fail_closed`.

## Provider and external execution boundary

Repository certification is not a provider write. External/provider operations remain capability-specific.

PentaCredentials owns credential readiness. PentaCertify owns provider-adapter and exact-operation certification. PentaRoute selects only certified paths. PentaHybrid applies human requirements. PentaAssure verifies evidence. PentaStatus reports readback. PentaLogger/PentaTrace/PentaMetric/PentaError preserve operational truth.

No protocol success can substitute for those controls.

## Canonical assets

- `data/penta/family.registry.json`
- `data/penta/interoperability.registry.json`
- `schemas/penta/family-registry.schema.json`
- `schemas/penta/interoperability-envelope.schema.json`
- `runtime/penta_family.py`
- `runtime/penta_runtime_suite.py`
- `runtime/penta_interop.py`
- `tests/test_penta_interop.py`
- `.github/workflows/penta-interoperability-production.yml`
- `.github/workflows/penta-runtime-suite.yml`
- `.github/workflows/penta-institutional-services.yml`
- `.github/workflows/penta-observability-production.yml`
- `developers/manifests/penta-runtime-suite.v1.json`
- `automation/penta-interoperability-fabric.mdx`

## Constitutional invariant

**No PENTA system manufactures authority.**

Interoperability proves that the institution can exchange governed work coherently. It does not convert technical reachability into legal, economic, security, provider, governance, human, or fiduciary power.
