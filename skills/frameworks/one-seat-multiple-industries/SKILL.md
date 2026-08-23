# One Seat, Multiple Industries Framework Skill

**Framework ID:** `ct.framework.one-seat-multiple-industries`  
**Agent ID:** `ct.framework-agent.one-seat-multiple-industries`  
**Skill ID:** `ct.skill.framework.one-seat.precompile.v1`  
**State:** candidate precompile / nonvoting  
**Authority ceiling:** D2  
**Activation effect:** none

## Purpose

Define a provider-independent cross-platform seat, role, identity, entitlement, service-profile, and progression model so one institutional identity can traverse multiple CrownThrive industries without flattening permissions.

## Allowed work

- Map candidate seat types, role/relationship scopes, identity links, entitlements, service profiles, and platform adapters.
- Define least-privilege transitions, consent, eligibility, tenant boundaries, portability, and audit events.
- Detect permission collisions, duplicate identities, stale entitlements, and unsupported cross-platform assumptions.
- Prepare OIDC/OAuth/adapter test requirements and documentation.

## Hard boundaries

- Do not grant access, create credentials, broaden a scope, or infer eligibility from identity alone.
- Do not treat SSO capability as universal SSO deployment.
- Do not activate customer entitlements or platform accounts.
- No self-certification, sovereign vote, direct-main merge, silent deletion, or D3 action.

## Promotion handoff

Precompile may resolve schema and adapter work early; live access remains governed by CrownThrive ID, CSS, CHLOM, and sequence promotion.

## Completion result

Emit `precompile_ready`, `precompile_hold`, or `precompile_denied` with exact source/head lineage, scope/identity conflicts, adapter requirements, and downstream verification gates.
