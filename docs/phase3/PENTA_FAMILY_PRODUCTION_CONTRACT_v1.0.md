# Penta Family™ Production Contract v1.0

**Owner:** CrownThrive LLC  
**Status:** Production control-plane contract  
**Effective:** 2026-08-26  
**Canonical registry:** `data/penta/family.registry.json`

## 1. Institutional definition

Penta Family™ is the canonical umbrella for CrownThrive's PENTA systems. It is not a naming convention and it is not a mechanism for silently promoting unfinished software. It is a machine-readable institutional control plane that composes registered PENTA catalogs, validates family invariants, exposes member maturity, and applies a fail-closed eligibility gate before downstream execution.

The family follows the CrownThrive PENTA doctrine:

**Discover -> Govern -> Execute -> Verify -> Preserve**

Penta Family may coordinate capabilities that already exist. It never manufactures legal, economic, security, licensing, provider, fiduciary, governance, or human authority.

## 2. Meaning of production

`Penta Family.status = production` means the umbrella registry, composition runtime, family snapshot, CI validation, status semantics, and dispatch guard are operational control-plane infrastructure.

It does **not** mean every child system is production-ready. Every child retains one of the canonical maturity states:

- `specified` — contract/architecture exists; no execution eligibility.
- `implemented` — source/runtime exists; still not execution eligible.
- `certified` — required bounded certification has passed; family eligibility gate may pass.
- `production` — production evidence exists for the defined scope; family eligibility gate may pass.
- `hold` — explicitly ineligible.
- `retired` — historical/non-executable.

A production umbrella therefore can safely contain members at different maturity levels. This is intentional and prevents documentation or naming from becoming execution authority.

## 3. Canonical family composition

The family registry composes the following required catalogs:

1. `data/penta/systems.registry.json` — canonical core PENTA catalog.
2. `data/penta/systems.extensions.pentascribe-marketer.json` — production PentaScribe/PentaMarketer extension and evidence linkage.
3. `data/penta/institutional-services.registry.json` — PENTA Institutional Operating Fabric services.

Each catalog must exist, parse as JSON, expose a systems array, and use unique `penta.*` machine keys with an allowed maturity state. Duplicate machine keys fail the family closed.

## 4. Family control planes

Penta Family groups interoperable responsibilities without erasing ownership boundaries:

- **Authority:** CHLOM and DAIL remain authority sources; PENTA consumes and enforces authority traces.
- **Human governance:** PentaHybrid and PentaAlumni handle bounded human review, stewardship, escalation, quorum, and handoff.
- **Routing/execution:** PentaControl, PentaMCP, PentaRoute, PentaMation, and PentaTime coordinate registered work.
- **Build/release:** PentaFactory, PentaBuild, PentaCertify, PentaAssure, PentaRelease, PentaMerge, and PentaCloser govern software delivery and convergence.
- **Credentials/security:** PentaCredentials, PentaSecurity, PentaRisk, and PentaAudit preserve credential, control, risk, and evidence boundaries.
- **Knowledge/continuity:** PentaDocs, PentaScribe, PentaGeneration, and PentaFederation preserve institutional truth, semantics, continuity, and interoperable bindings.
- **Market/media/economy:** PentaMarketer, PentaMedia, and PentaGreen coordinate governed market, media, and economic activation paths.
- **Institutional intelligence:** PentaSignal, PentaAnalytics, PentaInstitute, and PentaImpact provide sensing, analysis, research, and impact intelligence.
- **Institutional governance:** PentaPolicy, PentaLegal, PentaEthics, and PentaCapital package policy, legal-operations, ethics, and capital decisions without self-authorizing consequential action.

These groupings are topology and responsibility declarations. They do not change a child's maturity or create provider permissions.

## 5. Dispatch contract

The family dispatch guard is deliberately fail-closed. A member can pass the **family eligibility gate** only when:

1. its `machine_key` is registered;
2. its maturity is `certified` or `production`; and
3. the family catalogs compose without missing required catalogs or duplicate keys.

Passing the family gate is still not final authorization. Consequential downstream work must additionally satisfy the relevant CHLOM/DAIL authority trace, accountable owner, PentaHybrid/human gate, provider binding, credential, rights, spend, legal, security, release, and readback requirements.

Unknown, `specified`, `implemented`, `hold`, and `retired` members remain non-executable through the family gate.

## 6. Runtime and observability

`runtime/penta_family.py` is the dependency-free family verifier and snapshot runtime. It:

- validates non-negotiable production invariants;
- loads all required family catalogs;
- rejects missing catalogs and malformed system records;
- rejects duplicate machine keys;
- counts members by maturity;
- lists execution-eligible members;
- lists held/retired members;
- returns a member dispatch-gate disposition; and
- exits non-zero with `hold_fail_closed` when the family cannot be trusted.

Operators and automation can run:

```bash
python runtime/penta_family.py --root .
python runtime/penta_family.py --root . --member penta.scribe
```

The runtime executes no provider action. It establishes whether a member is eligible to proceed to its downstream authority and provider gates.

## 7. Verification lane

`.github/workflows/penta-institutional-services.yml` validates both the Institutional Operating Fabric and the Penta Family contract. It validates JSON, compiles both runtimes, emits a family snapshot, runs institutional authority-boundary tests, and runs family production-contract regression tests.

The family tests specifically prove that:

- the umbrella declares production;
- a production child such as PentaScribe may pass the family eligibility gate;
- a merely specified child such as PentaControl remains held;
- a merely implemented institutional child such as PentaCapital remains held;
- unknown members remain held;
- disabling fail-closed behavior is rejected;
- missing required catalogs are rejected; and
- duplicate machine keys are rejected.

## 8. Production invariant

The canonical invariant is:

> **Penta Family can be production while a child is not. No child inherits production, certification, credentials, authority, or provider access from the family name.**

This is the mechanism that allows CrownThrive to institutionalize the full PENTA topology now while continuing to certify and promote individual systems based on evidence rather than assumption.

## 9. Change control

Changes to family status semantics, execution-eligible maturity, authority invariants, required catalogs, or fail-closed behavior are production control-plane changes. They require code review, CI evidence, and the applicable CrownThrive governance/release gates.

Historical or archived documentation may explain prior PENTA architecture but cannot independently alter this production contract.
