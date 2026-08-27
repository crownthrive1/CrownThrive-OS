# CIE post-activation parent/child link assurance

## Scope

This control exists for the **Cultural Imprint Engine (CIE)** after CIE has already entered bounded governed production. It solves one narrow problem: CrownThrive-OS `main` may continue to advance after the exact Founder-authorized production snapshot while CIE `main` remains unchanged. The current technical parent/child evidence must be refreshable without pretending that the original Founder authorization covered the newer parent Git SHA.

## What this control does

`chlom_runtime.refresh_cie_parent_child_production_assurance_v1` may append a current `linked_governed` repository-link receipt only when all of the following are true:

- CIE repository is already `linked_governed`, operational and non-voting.
- CIE package is `maintained`, operational, non-voting and D3-human-reserved.
- public activation remains false.
- commercial state remains `hold`; pricing, checkout and entitlement remain inactive.
- CIE algorithm remains `production_limited` at D2 with the accepted public contract digest.
- the latest production activation receipt is `founder_direct`, has a protected canary `PASS`, and has rollback state `ready`.
- the original production authority snapshot is internally consistent.
- GitHub comparison evidence shows the new Support head is a descendant of the original activation parent head, with zero commits behind.
- fresh exact GitHub observations exist for both Support and CIE.
- Guardian, family and interoperability evidence remain valid.

## What this control does not do

It does **not** reactivate CIE. It does not rewrite or extend the Founder authorization. In particular it may not change:

- the production authority request ID;
- the original production exact-version reference;
- the production content SHA-256;
- the production activation receipt;
- public activation;
- API/MCP exposure boundaries;
- commerce, pricing, checkout or entitlement;
- provider-write, economic or rights authority;
- voting eligibility;
- D3 reservation.

The new link receipt is assurance evidence for the current descendant Git head only. Its `operational_activation`, `authority_effect`, `vote_effect` and `child_self_activation` fields are all false.

## Why the pre-production function cannot be reused

`establish_repository_parent_child_technical_link_v1` correctly requires a child to be non-operational and non-voting. Once CIE is live, forcing it through that function would either fail or require an unacceptable temporary production regression. The post-activation assurance function is therefore additive and intentionally does not share the pre-production mutation semantics.

## Status contract

`chlom_runtime.cie_post_activation_link_assurance_status_v1` returns one of:

- `HOLD_NO_LIVE_PRODUCTION_RECEIPT`
- `HOLD_PRODUCTION_BOUNDARY_DRIFT`
- `HOLD_CURRENT_LINK_ASSURANCE_STALE`
- `PRODUCTION_ACTIVE_CURRENT_LINK_ASSURED`

This status is observational. It creates no activation or authority.

## Security

Both functions are `SECURITY DEFINER`, use a pinned `search_path`, revoke execution from `public`, `anon` and `authenticated`, and grant execution only to `service_role`.

## Authority rule

A newer Support Git SHA is **not** a new Founder production authorization. Current-head assurance may prove continuity of the parent/child relationship while the original immutable production authority receipt remains the authority source.
