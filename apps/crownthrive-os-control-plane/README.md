# CrownThrive OS Control Plane

A buildless Vercel control plane for PentaRG, PentaFabric, release gates, topology, DAIL projections, provider evidence, and governed CHLOM chain evidence.

## Vercel project contract

- Project ID: `prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN`
- Project: `crownthrive-os`
- Root Directory: `apps/crownthrive-os-control-plane`
- Framework Preset: `Other`
- Node: `24.x`
- Canonical domain: `https://crown-thrive-os.vercel.app`

## Production interfaces

- `/api/health` — public deployment and integration binding state.
- `/api/fabric` — CrownThrive Vercel execution-fabric readback.
- `/api/penta` — PentaFabric event and receipt endpoint.
- `/api/mcp` — stateless MCP 2026-07-28 gateway with constrained legacy fallbacks.
- `/api/chlom` — public CHLOM health readback on GET/HEAD and protected bridge operations on POST.

## CHLOM bridge

The bridge is fixed to `https://chlom-protocol.vercel.app`. Requests cannot supply an alternate URL. Protected POST and MCP operations require an inbound `CROWNTHRIVE_CONTROL_TOKEN`; the server then uses a separate `CHLOM_API_TOKEN` for the upstream call.

Allowlisted actions:

- `rpc_read` — read-only JSON-RPC methods only.
- `analytics` — bounded Google Blockchain Analytics templates only.
- `attest` — deterministic non-broadcast evidence-anchor intent.

The bridge does not accept private keys, arbitrary SQL, arbitrary RPC endpoints, or transaction-broadcast methods. It preserves the upstream CHLOM evidence digest and emits a separate PentaFabric bridge receipt without claiming DAIL persistence or onchain publication.

## Configuration

Copy the variable names from `.env.example` into the Vercel project. Store actual values only in Vercel/Google provider controls; never commit them.

`/api/health` and `/api/chlom` distinguish provider liveness from configuration readiness, so an operational deployment cannot manufacture a data-plane pass.
