# Penta Families Portal & Operating Guide

**Machine registry:** `penta/registry/penta-families.v1.json`  
**Runtime:** `runtime/penta_families.py`  
**Human index:** `PENTA-FAMILIES.md`  
**Portal index:** `/io/pentas/families`

## Purpose

This directory defines the institutional implementation model for Penta family portals. The family portal layer sits between the Penta Family umbrella and individual `/io/pentas/{slug}` system portals.

It solves three problems:

1. **Discovery completeness:** every Penta discovered in machine, technical or institutional registries must have a primary family.
2. **Operational navigation:** operators can enter through a mission/family surface before drilling into individual systems.
3. **Story continuity:** each family explains why its members exist together, how they hand off work and where authority stops.

## Portal model

```text
/io/pentas
  ├── /families
  │    ├── /system-architecture
  │    ├── /routing-interoperability
  │    ├── /transport-primitives
  │    ├── /automation-agentic
  │    ├── /build-release
  │    ├── /security-trust
  │    ├── /resilience-continuity
  │    ├── /observability-organic
  │    ├── /knowledge-semantics-data
  │    ├── /governance-legal
  │    ├── /workforce-people
  │    ├── /intelligence-research
  │    ├── /communications-service
  │    ├── /media-creative
  │    └── /commerce-economy
  └── /{penta-system-slug}
```

A family portal is a topology and operating surface. It does not replace child portals or PentaDocs.

## Required family portal sections

Every family portal payload is generated against the registry's required section contract:

- **Story** — institutional narrative and why the family exists.
- **Mission** — concise operating purpose.
- **Member census** — all current primary members discovered at runtime.
- **Member status** — evidence-backed machine maturity/component state without promotion.
- **Responsibilities** — derived responsibility/category/axis context.
- **Inputs/Outputs** — handoff envelope expectations.
- **Authority boundary** — explicit non-authority and reserved decisions.
- **Cross-family handoffs** — expected family-to-family flows.
- **Operations** — entry points and execution/readback model.
- **SOPs/SLAs** — governing procedure/service commitments.
- **Evidence** — source registries and runtime census evidence.
- **API/MCP** — exact-machine-key interoperability contract.
- **Incidents/Recovery** — status, triage, security and resilience paths.
- **Releases/Changelog** — topology versioning and child release separation.
- **Roadmap** — family completeness and pending member gaps.
- **Support** — PentaDocs/CrownThrive IO and accountable ownership routes.

## Discovery contract

The runtime consumes three independent registry classes.

### Machine family

`data/penta/family.registry.json` declares the executable Penta Family catalogs. The family runtime loads every declared catalog and also scans `data/penta/systems*.json` for system extension catalogs so a newly-added extension cannot remain invisible merely because the parent catalog list has not yet been updated.

Machine state remains authoritative for machine maturity where present.

### Technical components

`penta/registry/penta-component-registry.v1.json` carries PentaOS technical components, stable component keys/contracts, axes, state and the full PentaRoute primitive census.

Technical `active` is a component-registry state; it is not automatically equivalent to machine-family `production` maturity.

### Institutional census

`PENTA-FAMILY-REGISTRY.md` is the broader institutional identity and CrownThrive IO portal standard. It captures Pentas that may be institutionalized before they have an independently executable machine implementation.

Institutional presence does not manufacture runtime maturity.

## Identity normalization

Names are normalized by removing marks/punctuation/spacing and case folding. Therefore:

```text
Penta Federation == PentaFederation
PentaWorkforce OS == PentaWorkforceOS
Penta Scribe == PentaScribe
```

Normalization is for identity reconciliation only. It never collapses genuinely distinct names such as PentaSecure and PentaSecurity.

## Primary and secondary families

Every discovered Penta has exactly one primary family. The primary family establishes the canonical portal/story ownership.

Cross-family participation is explicitly modeled separately. Example: PentaStatus belongs primarily to Resilience & Continuity but also participates in Observability and Communications.

If one identity is explicitly assigned to two primary families, verification fails closed.

## Future-growth gate

Adding a new Penta to any canonical source creates an obligation to classify it. The expected change sequence is:

1. add or recover the stable Penta identity;
2. define its child contract/maturity in the applicable source;
3. assign one primary family in `penta-families.v1.json`;
4. add secondary families only when needed;
5. verify portal/story coverage;
6. run family topology CI;
7. preserve changes through PentaSerialized/PentaGeneration and normal release governance.

If the name is not classified, `runtime/penta_families.py` exits non-zero with `hold_fail_closed`.

## Runtime commands

Verify the complete estate:

```bash
python runtime/penta_families.py --root .
```

Render the family portal index:

```bash
python runtime/penta_families.py --root . --portal-index
```

Render one family portal:

```bash
python runtime/penta_families.py --root . --family security-trust
```

Run regression tests:

```bash
python tests/test_penta_families.py
```

## Authority boundary

Family topology may classify, display, route and preserve member context. It may not:

- promote `specified` or `implemented` children;
- create a credential or provider binding;
- create CHLOM/DAIL authority;
- grant rights/licenses/entitlements;
- move money or credits;
- waive legal/security/privacy/compliance requirements;
- create D3 or sovereign authority;
- self-certify child production;
- treat a portal route as deployment evidence.

## Operating handoff

The ordinary family-level flow is:

```text
family mission / operator intent
→ resolve child machine key
→ Penta interoperability envelope
→ child maturity + PentaOD/readiness
→ authority / human / credential / provider gates
→ bounded execution if eligible
→ exact readback
→ PentaStatus + evidence
→ PentaSerialized / PentaGeneration preservation
```

The family portal is therefore a map and control surface—not a privilege escalation layer.
