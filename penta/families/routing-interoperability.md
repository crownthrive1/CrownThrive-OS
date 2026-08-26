# Penta Routing & Interoperability Family

**Family ID:** `routing-interoperability`  
**Portal:** `/io/pentas/families/routing-interoperability`

## Story

This family is CrownThrive's governed connection fabric. It makes registered systems mutually addressable while preserving identity, version, scope, trust and provider boundaries.

PentaRoute selects and governs routes. PentaMCP exposes bounded machine capabilities. PentaFlex provides adaptable API/MCP framework behavior. PentaFederation preserves participant and repository boundaries. PentaInterOps governs transforms and compatibility. PentaWire carries events and connections. PentaBind records exact system/provider/capability bindings.

## Primary members

PentaFederation · PentaInterOps · PentaFlex · PentaMCP · PentaRoute · PentaWire · PentaBind

## Responsibilities

- exact route resolution;
- API/MCP capability discovery and invocation contracts;
- federation identity and trust boundaries;
- interoperability transforms/version compatibility;
- event/transport fabric;
- explicit provider/system/capability bindings;
- trace, idempotency, evidence and readback propagation.

## Operating flow

```text
source Penta + typed intent
→ exact target machine key
→ Penta interoperability envelope
→ identity/scope/authority check
→ PentaRoute path resolution
→ primitive/provider adapter
→ target readback
→ trace/evidence preservation
```

## Cross-family handoffs

- **Transport Primitives:** supplies bounded low-level verbs.
- **Automation & Agentic:** supplies typed workflows/agents using the routes.
- **Security & Trust:** supplies identity, credentials, security and certification context.
- **Resilience & Continuity:** supplies readiness, retry, rollback and recovery context.

## Authority boundary

Connectivity is not permission. Tool discovery is not capability authority. A 2xx/provider response is evidence of that call, not universal provider-write certification. Every consequential route remains subject to exact authority, maturity, credentials, provider binding, human gates and readback.

## Status and evidence

The parent interoperability registry is production, while child systems retain independent maturity. Unknown source/target machine keys fail closed. The family portal does not act as an unrestricted proxy.

## Incidents and recovery

Route failures retain source/target, version, trace, idempotency and provider context. Failover may select a certified alternate path but may not broaden scopes or silently switch authority models.

## Releases and roadmap

New protocols/adapters must preserve stable CrownThrive machine identities and expose versioned compatibility/exit behavior. Vendor replacement changes bindings; it does not rename the institutional capability.
