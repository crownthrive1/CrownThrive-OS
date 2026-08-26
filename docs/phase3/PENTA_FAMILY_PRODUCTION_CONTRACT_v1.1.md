# Penta Family™ Production Contract v1.1

**Owner:** CrownThrive LLC  
**Status:** Production control-plane contract  
**Effective:** 2026-08-26  
**Supersedes:** `PENTA_FAMILY_PRODUCTION_CONTRACT_v1.0.md` for current-state family composition and portal requirements  
**Canonical registry:** `data/penta/family.registry.json`

## 1. Institutional definition

Penta Family™ is the canonical umbrella for CrownThrive's PENTA systems. It is not a naming convention and it is not a mechanism for silently promoting unfinished software. It is a machine-readable institutional control plane that composes registered PENTA catalogs, validates family invariants and family census references, exposes member maturity, renders per-member portal contracts, and applies a fail-closed eligibility gate before downstream execution.

The family follows the CrownThrive PENTA doctrine:

**Discover -> Govern -> Execute -> Verify -> Preserve**

Penta Family may coordinate capabilities that already exist. It never manufactures legal, economic, security, licensing, provider, fiduciary, governance, money-movement, credential-use or human authority.

## 2. Meaning of production

`Penta Family.status = production` means the umbrella registry, composition/census runtime, portal payload contract, family snapshot, CI validation, status semantics and dispatch guard are operational control-plane infrastructure.

It does **not** mean every child system is production-ready. Every child retains one canonical maturity state:

- `specified` — institutional identity/contract exists; no execution eligibility.
- `implemented` — source/runtime exists; still not execution eligible.
- `certified` — required bounded certification has passed; family eligibility gate may pass.
- `production` — production evidence exists for the defined scope; family eligibility gate may pass.
- `hold` — explicitly ineligible.
- `retired` — historical/non-executable.

A production umbrella can safely contain members at different maturity levels. Portal presence, documentation, naming, implementation, a credential reference or a successful historical provider call does not promote a member.

## 3. Canonical family composition

The family registry composes four required catalogs:

1. `data/penta/systems.registry.json` — canonical core PENTA catalog.
2. `data/penta/systems.extensions.pentascribe-marketer.json` — PentaScribe/PentaMarketer extension and evidence linkage.
3. `data/penta/institutional-services.registry.json` — PENTA Institutional Operating Fabric services.
4. `data/penta/systems.extensions.operations-workforce.json` — software-delivery, certification, credentials, maintenance, communications/concierge/status, economic, workforce, board/compliance and agent-suite systems.

Each required catalog must exist, parse as JSON, expose a `systems` array, and use unique `penta.*` machine keys with an allowed maturity state. Missing required catalogs or duplicate machine keys fail the family closed.

The operations/workforce extension institutionalizes, among others: PentaBuild, PentaCertify, PentaRelease, PentaMerge, PentaCloser, PentaCredentials, PentaNurture, PentaGreen, PentaCredits, PentaMail, PentaConcierge, PentaStatus, PentaManagers, PentaDirectors, PentaCohorts, PentaAccelerator, PentaNotes, PentaTriage, PentaHealth, PentaHR, PentaBenefits, PentaPay, PentaCost, PentaBoard, PentaOFAC, PentaSuite, PentaRFA and PentaPR.

These identities are registered conservatively at evidence-backed maturity. Registration is not certification or production promotion.

## 4. Control-plane census integrity

Penta Family v1.1 makes the family topology executable as a validated census rather than a list of aspirational names.

Every Penta reference inside `control_planes` must resolve unambiguously to a registered family member. Display-name variations such as `Penta Control` and `PentaControl` normalize to the same identity. Explicit non-member authority references are allowlisted separately; currently CHLOM and DAIL are external authority-plane references.

An unresolved or ambiguous Penta reference produces `hold_fail_closed`. Therefore a control-plane declaration cannot name a Penta that the family itself cannot resolve.

## 5. Family control planes

Penta Family groups interoperable responsibilities without erasing ownership boundaries:

- **Authority:** CHLOM and DAIL remain external authority sources.
- **Human governance:** PentaHybrid, PentaAlumni and PentaBoard support human review, stewardship, directives, quorum and handoffs.
- **Routing/execution:** PentaControl, PentaMCP, PentaRoute, PentaMation and PentaTime coordinate registered work.
- **Build/release/convergence:** PentaFactory, PentaBuild, PentaCertify, PentaAssure, PentaRelease, PentaMerge, PentaCloser, PentaPR, PentaSuite, PentaRFA and PentaNurture govern software/agent delivery and lifecycle convergence.
- **Credentials/security/compliance:** PentaCredentials, PentaSecurity, PentaRisk, PentaAudit and PentaOFAC preserve credential, security, risk, evidence and sanctions-screening boundaries.
- **Knowledge/continuity:** PentaDocs, PentaScribe, PentaGeneration, PentaFederation, PentaNotes and PentaStatus preserve institutional truth, semantics, continuity, feedback and self-observability.
- **Market/media/economy:** PentaMarketer, PentaMedia, PentaStudios, PentaBooks, PentaGreen, PentaCredits, PentaPay and PentaCost coordinate governed market, media and economic pathways.
- **Institutional intelligence:** PentaSignal, PentaAnalytics, PentaInstitute and PentaImpact provide sensing, analysis, research and impact intelligence.
- **Institutional governance:** PentaPolicy, PentaLegal, PentaEthics, PentaCapital, PentaBoard and PentaDirectors package policy, legal operations, ethics, capital and supervisory directives without self-authorizing consequential action.
- **Workforce/people:** PentaManagers, PentaDirectors, PentaCohorts, PentaAccelerator, PentaTriage, PentaHealth, PentaHR and PentaBenefits create the governed living-workforce environment.
- **Communications/service:** PentaMail, PentaConcierge and PentaStatus provide governed messaging, service fulfillment and owner-facing self-reporting.

These groupings are topology/responsibility declarations. They do not change member maturity or create provider permissions.

## 6. Portal contract

Every registered family member has a canonical portal contract independent of maturity.

Route pattern:

```text
/penta/{machine_key_suffix}
```

Examples include `/penta/mail`, `/penta/concierge`, `/penta/status`, `/penta/credentials`, `/penta/build`, `/penta/hr` and `/penta/ofac`.

Every portal must expose these sections:

1. overview;
2. status;
3. responsibilities;
4. inputs/outputs;
5. authority boundary;
6. dependencies;
7. SOPs/SLAs;
8. runbooks;
9. guides;
10. evidence;
11. API/MCP;
12. changelog; and
13. support.

`portal_state = contracted` means the family runtime can render the canonical portal payload. It does **not** independently prove that a public frontend route is deployed or reachable. Public/UI deployment requires separate deployment/readback evidence.

The complete human-readable portal/census guide is `automation/penta-family-portals.mdx`.

## 7. Dispatch contract

The family dispatch guard is deliberately fail-closed. A member can pass the **family eligibility gate** only when:

1. its `machine_key` is registered;
2. all required family catalogs exist and compose;
3. no duplicate machine key exists;
4. every Penta control-plane reference resolves unambiguously;
5. its maturity is `certified` or `production`; and
6. the family production invariants remain valid.

Passing the family gate is still not final authorization. Consequential downstream work must additionally satisfy the relevant CHLOM/DAIL authority trace, accountable owner, PentaHybrid/human gate, provider binding, credential, rights, spend, legal, security, release and readback requirements.

Unknown, `specified`, `implemented`, `hold` and `retired` members remain non-executable through the family gate.

## 8. Runtime and observability

`runtime/penta_family.py` is the dependency-free family verifier, census runtime and portal renderer. It:

- validates non-negotiable production invariants;
- loads all required family catalogs;
- rejects missing catalogs and malformed system records;
- rejects duplicate machine keys;
- resolves/validates control-plane references;
- counts members by maturity;
- lists execution-eligible and held/retired members;
- emits a control-plane resolution map;
- generates a portal index for every registered member;
- renders a complete portal payload for a selected member;
- returns a member dispatch-gate disposition; and
- exits non-zero with `hold_fail_closed` when the family cannot be trusted.

Operators and automation can run:

```bash
python runtime/penta_family.py --root .
python runtime/penta_family.py --root . --portal
python runtime/penta_family.py --root . --member penta.mail --portal
```

The runtime executes no provider action. It establishes census truth, portal contract state and whether a member may proceed to downstream authority/provider gates.

## 9. Verification lane

`.github/workflows/penta-institutional-services.yml` validates the Institutional Operating Fabric and Penta Family contract. It validates all four catalogs and schemas, compiles both runtimes, emits a family census snapshot, verifies the portal index and a representative PentaMail portal, runs institutional authority-boundary tests, and runs family production-contract regression tests.

The family tests specifically prove that:

- the umbrella declares production;
- production children such as PentaScribe may pass the family eligibility gate;
- specified children remain held;
- implemented institutional children remain held;
- newly institutionalized PentaMail/Concierge/Status/Build/Credentials/workforce/economic systems remain held at `specified`;
- every control-plane Penta reference resolves to a registered member;
- every member gets a portal route/payload;
- required portal sections cannot silently disappear;
- unknown members remain held;
- disabling fail-closed behavior is rejected;
- missing required catalogs are rejected;
- duplicate machine keys are rejected; and
- unresolved control-plane names are rejected.

## 10. Production invariants

The canonical invariants are:

> **Penta Family can be production while a child is not. No child inherits production, certification, credentials, authority or provider access from the family name.**

> **Every Penta named by the production control plane must resolve to a registered family member or the family fails closed.**

> **Every registered member has a portal contract, but a contracted portal is not proof of deployed frontend infrastructure or execution eligibility.**

This enables CrownThrive to institutionalize the complete PENTA environment while promoting individual systems only from evidence.

## 11. Change control

Changes to family membership, portal requirements, status semantics, execution-eligible maturity, authority invariants, required catalogs, control-plane references or fail-closed behavior are production control-plane changes. They require code review, CI evidence and the applicable CrownThrive governance/release gates.

Historical or archived documentation may explain prior PENTA architecture but cannot independently alter this production contract. v1.0 remains historical lineage for the first production family contract; v1.1 governs current census/portal behavior after acceptance.
