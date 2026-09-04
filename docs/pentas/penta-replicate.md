# PentaReplicate

**Contract:** `ct.penta.replicate.v1`  
**Agent:** `ct.agent.penta-replicate`  
**Service:** `penta_replicate`  
**Version:** `1.0.0`  
**State:** `OPERATIONAL_BOUNDED`

PentaReplicate is CrownThrive's governed MCP/API/site integration propagation fabric. It keeps registered public-safe integration contracts synchronized across production website surfaces without duplicating provider credentials or granting itself provider-write authority.

## Production runtime

- Runtime: `https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1`
- Health: `?action=health`
- Manifest: `?action=manifest&surface_id=<surface_id>`
- Bootstrap: `?action=bootstrap&surface_id=<surface_id>`
- MCP: `?action=mcp`
- Scheduler: `ct-penta-replicate-v1` at minutes 14, 29, 44, and 59 of every hour

## Source of truth

PentaReplicate compiles from `integration_control.api_mcp_reconciled_inventory_v1`, not from hand-maintained website copies. Source changes to MCP tools/exposures, endpoint contracts, public API projections, website surfaces, site bindings, and PentaWire read adapters enqueue reconciliation events.

## Public manifest boundary

The public manifest is `PUBLIC_SAFE`. It exposes only explicitly public MCP servers, live public APIs, HTTPS public read adapters, and the surface's own PentaReplicate bindings.

It does **not** expose:

- provider credentials;
- service-role keys or vault references;
- internal SQL adapter topology;
- non-public MCP servers;
- money-movement authority; or
- provider-write authority.

## Website propagation model

Every production website surface has active PentaReplicate service, MCP, and integration bindings. A surface therefore receives current public-safe MCP/API discovery through the dynamic manifest immediately.

Native browser bootstrap insertion is a separate D2 provider-source mutation. PentaReplicate queues this work but executes it only through a provider adapter that has the exact script/template write scope plus read-after-write and rollback certification. A provider credential or unrelated write canary is not sufficient.

Current provider-source states are represented explicitly as either:

- `APPROVED_PENDING_CERTIFIED_PROVIDER_SCRIPT_ADAPTER`; or
- `PLANNED_PENDING_PROVIDER_SCRIPT_ADAPTER`.

## Authority

- Automatic replication ceiling: D1.
- Native provider-source bootstrap: D2 and separately certified.
- D3 remains human-reserved.
- `no_self_approval=true`.
- `fail_closed=true`.
- Read-after-write and rollback are mandatory for native provider mutation.

## MCP tools

- `penta.replicate.status`
- `penta.replicate.manifest`
- `penta.replicate.targets`
- `penta.replicate.drift`

These tools are read-only.

## Security

The production Edge runtime is the public access boundary. PentaReplicate's THRIVEBASE tables and SECURITY DEFINER functions are not executable/readable by `anon` or `authenticated`; the server-side runtime retains bounded service-role access.

## Evidence baseline — 2026-09-04

- Production Edge function: `penta-replicate-v1`, version 1.
- Provider source SHA-256: `dd2caee364dd33e65a3889053fe6f7e9f196423aa2dde1bf357280739e8ca4e5`.
- Health readback: HTTP 200 / PASS.
- MCP initialize: HTTP 200.
- MCP tools/list: 4 tools.
- Hardened sample manifest: HTTP 200 / `PUBLIC_SAFE`.
- Public manifest inventory at verification: 48 public MCP tools, 15 public APIs, 10 public HTTPS read adapters, 3 PentaReplicate site bindings.
- Production website targets: 35.
- Active PentaReplicate mesh bindings: 105.

Counts are live inventory observations and may increase as new public-safe contracts are registered. The authority boundary does not expand automatically with inventory growth.
