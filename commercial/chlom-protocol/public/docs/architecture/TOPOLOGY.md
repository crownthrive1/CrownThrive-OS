# CHLOM Repository, Runtime & Website-Mesh Topology

This page defines the public-safe topology for CHLOM as a CrownThrive OS metaprotocol surface. It distinguishes authority, documentation, implementation, machine access, public discovery, and economic activation so that no provider or repository is mistaken for the whole system.

## Repository family

```text
CrownThrive institutional sources / governed vaults
                  │
                  ▼
crownthrive1/CrownThrive-OS
canonical public-safe governance parent
                  │
                  ├─ documentation and standards
                  ├─ public-safe contracts and manifests
                  ├─ factory definitions and validators
                  ├─ protected-state references only
                  └─ deterministic CHLOM projection package
                             │
                             ▼
                  governed child candidate PR
                             │
                             ▼
               crownthrive/chlom-protocol
               public commercial child
                  ├─ registries and schemas
                  ├─ architecture and research
                  ├─ public machine contracts
                  ├─ licensing and support funnel
                  └─ verification/provenance artifacts
```

Both GitHub repositories are public. Restricted institutional truth is not stored in either public repository merely because the parent is authoritative for the managed projection.

## Operating topology

```text
CIE / CrownThrive identity context
          │
          ▼
CHLOM Pentafabric layers 1–3
Identity → Rights/Conditions → DAIL/Assurance
          │
          ▼
Layer 4 execution fabric
Agents • Framework Factory • Plugins • Skills • APIs • MCPs • Portals • Docs
          │
          ▼
Layer 5 economic fabric
ThriveEvergreen • ECAC • SKUs • Access • Entitlements • Payments • Distribution
          │
          ▼
Provider and ecosystem surfaces
Websites • apps • stores • media • partners • databases • optional chains
          │
          └──────── evidence, outcomes, corrections ────────► DAIL
```

## Public discovery mesh

The intended public routing hierarchy is:

1. **Corporate / partnership:** https://crownthrive.com
2. **Institutional documentation / support:** https://crownthrivesupport.com
3. **Developer ecosystem:** https://crownthrive.io
4. **CHLOM public commercial source:** https://github.com/crownthrive/chlom-protocol
5. **Canonical public-safe governance parent:** https://github.com/crownthrive1/CrownThrive-OS

A route being listed here does not assert that every planned CHLOM page, API, MCP endpoint, checkout, or portal is live on that domain.

## Failover model

Public discovery should degrade gracefully rather than fail as a single monolith.

- If the corporate site is unavailable, public documentation and GitHub remain discoverable.
- If the documentation site is unavailable, the child repository remains the public CHLOM technical and licensing reference.
- If the developer site is unavailable, machine contracts and integration documentation remain available through the child repository.
- If a runtime API or MCP surface is unavailable, clients must fail closed for rights, economic, or high-consequence actions rather than infer authorization from cached provider state.
- Provider outages must not erase DAIL evidence or silently rewrite institutional truth.

True DNS, CDN, application, database, and provider failover require deployment-specific infrastructure and are not created merely by documenting fallback routes.

## Continuous projection

The parent CHLOM commercial projection factory is designed to run on governed changes and scheduled continuity checks. When the bounded child-repository credential is available, a changed managed projection is pushed to a child candidate branch and opened as a pull request. Unmanaged child content is preserved.

## Trust boundary

A repository, website, provider, agent, API, MCP tool, model, or payment rail may supply evidence or execute a bounded action. None is permitted to independently manufacture CrownThrive authority, ownership, licensing, certification, entitlement, or settlement state.
