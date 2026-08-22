# CrownThrive Interoperability Fabric Plugin

**Plugin ID:** `ct.plugin.crownthrive-interoperability-fabric`  
**Version:** `1.0.0`  
**State:** controlled test / governed HOLD  
**Archetype:** tool-only MCP plugin  
**Public submission:** not submitted

This package is the public-safe repository scaffold for CrownThrive's interoperability plugin. The protected implementation, service-role runtime, exact private schema maps, private identity mappings, credentials, algorithm weights, negative-test corpus, and private routing topology are not stored here.

## Purpose

The plugin exposes focused, read-only tools that help an authorized CrownThrive operator or agent:

- locate plugins, contracts, routes, and services;
- fetch one stable resource by exact ID;
- inspect sanitized interoperability status;
- check contract compatibility;
- plan a non-executing route;
- inspect plugin packages;
- prepare a non-executing installation plan;
- validate package governance and test state.

It does not install software, mutate providers, create credentials, move money, activate commerce, submit itself publicly, merge code, create sovereign votes, or perform D3 decisions.

## Server

- MCP server ID: `ct.mcp.crownthrive-interoperability`
- Supabase Edge Function: `crownthrive-interoperability-plugin`
- Authentication: Supabase JWT/admin or restricted service role
- Stable server version: `1.0.0`
- UI: none in v1; optional decoupled widget is future work

## Root tools

| Tool | Read only | Idempotent | Risk |
| --- | --- | --- | --- |
| `search` | yes | yes | D0 |
| `fetch` | yes | yes | D0 |
| `interop.status` | yes | yes | D0 |
| `interop.compatibility.check` | yes | yes | D1 |
| `interop.route.plan` | yes | yes | D1 |
| `plugins.list` | yes | yes | D0 |
| `plugins.get` | yes | yes | D0 |
| `plugins.install.plan` | yes | yes | D1 |
| `plugins.package.validate` | yes | yes | D1 |

## Public/private boundary

Public-safe package materials may include:

- stable IDs;
- semantic versions;
- tool purposes;
- input/output schemas;
- annotations and invariants;
- lifecycle states;
- public contract and package digests;
- sanitized scores and blocker classes;
- non-live pricing candidates;
- test status.

Restricted materials include:

- raw credentials and keys;
- service-role configuration;
- private identity mappings;
- exact algorithm weights and thresholds;
- private field transformations;
- provider account topology;
- protected source code;
- private evidence bodies;
- commercial calibration.

## Validation

The internal package validator has passed nine tests covering schema, compatibility, rollback/reliability, negative fail-closed behavior, privacy, idempotency, deployment security, installation planning, and package invariants.

The authenticated external/ChatGPT connector canary remains pending. The plugin must not be labeled publicly available or production connected until that readback passes.

## Development rules

1. Prefer focused tools over one broad command surface.
2. Separate read, plan, verify, and write tools.
3. Keep write operations out of the root plugin until each exact operation has its own certified canary, rollback, and readback.
4. Use stable identifiers rather than display names for machine references.
5. Keep result payloads small and structured.
6. Require owner and different independent verifier for material changes.
7. Do not expose secrets, private identity, protected scoring, or private evidence.
8. Provider throttles, billing, quotas, and terms remain authoritative.
9. Preserve all versions and corrections; never silently delete.
10. Keep UI and public submission separate from MCP server correctness.

## Files

- `plugin.manifest.json` — machine-readable public-safe package manifest
- `tool-contracts.json` — root tool schemas and annotations
- `README.md` — package boundary and developer guidance

## Commercial state

Candidate pricing is in review only. Checkout, Stripe objects, entitlements, operative licenses, public submission, and customer distribution are disabled.

## Governance

A/B/C/D/S remain the only sovereign voters. Interoperability agents are non-voting D2-or-lower subroutes. Technical green or package validation does not equal canonical/public acceptance.