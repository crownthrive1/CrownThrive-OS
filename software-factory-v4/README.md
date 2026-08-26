# CrownThrive Autonomous Software Factory v4

Status: **production runtime active in ThriveBase; breadth certification in progress.**

Factory v4 expands one existing governed software factory rather than creating another orchestration layer. A build request is decomposed into a structured blueprint, compiled into bounded source artifacts, validated, packaged as one production release, routed across the provider mesh, and promoted only when every required deployment has write/readback evidence.

## Pipeline

`Discover -> Architect -> Generate -> Security -> Test -> Package -> Deploy -> Assurance`

## Generate v4

`ct-factory-blueprint-planner` converts structured product/service requirements into compiler components. `ct-factory-compiler.v4` emits deterministic artifacts from registered component families. `ct-factory-generator.v4` seals the source set into the production manifest.

Registered families include TypeScript modules, Edge APIs, static sites, bounded PostgreSQL DDL/views, Deno tests, JSON documents, OpenAPI contracts, MCP tool manifests, allowlisted GitHub workflows, MDX documentation, service workers, environment contracts, event contracts, governance policies, route manifests, and asset manifests.

The compiler remains fail-closed: no arbitrary shell, no arbitrary SQL, no secret values, safe relative paths only, bounded artifact sizes, SHA-256 on emitted source, and only enabled component families may compile.

## Provider breadth

Every production website surface in `integration_control.website_surfaces` is bound into `ct_factory_surface_bindings` and receives a deployment target. The binding policy is explicit:

- `auto`: certified bounded-auto target; required for release.
- `manual`: registered and visible; not mutated without the existing human authority.
- `observe`: registered/read posture only.
- `hold_unbound`: the property is known, but provider mutation is not certified and remains fail-closed.

`ct-factory-surface-binding-sync-v4` refreshes this registry every 15 minutes.

## Current certified write paths

- ThriveBase native service registry
- GitHub Actions/OIDC provider publisher
- cPanel UAPI write + readback
- CrownThrive Sites governed per-surface projection + readback

Vercel remains fail-closed because the connected Vercel team currently exposes no project to bind. Other external providers remain registered but do not receive manufactured write authority.

## Production proof run

Build request: `factory-v4-breadth-production-001`

Build run: `42982e51-08cb-482e-a629-7e019e9845cb`

Candidate package: `2.1.1`

Candidate SHA-256: `897ae1fa9f66a6fa52b1001f973d643061302fad4a3c868829111b55ff750655`

The proof compiles sixteen artifacts across fourteen component kinds and binds twenty production surfaces. Five verified bounded-auto Sites surfaces are release-required; optional/manual/unbound surfaces are represented without blocking unrelated certified production work.
