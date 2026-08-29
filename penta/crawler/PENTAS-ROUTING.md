# Pentas Cookie-Carried Capability Routing v1

## Contract

Every active Penta has a server-side PentaCookie. The cookie can carry a `protocol_routing` descriptor in bounded observed state and an oracle-adjudicated `routing` descriptor in oracle state. Pentas packet routing resolves against those descriptors rather than hard-coding every future Penta relationship into the crawler.

This is an information-routing capability. It does **not** grant the destination authority to execute the work described by a packet.

## Routing descriptor

The effective descriptor may contain:

```json
{
  "capabilities": ["help.remediate", "remediation.pr"],
  "mesh_lanes": ["penta_control"],
  "accepts_packet_types": ["help.raise", "remediation.request"],
  "max_packet_risk": "D2"
}
```

The observed descriptor is refreshed from institutional evidence. The oracle descriptor can refine routing only through the CHLOM-gated PentaCookie mutation contract. The effective packet-risk ceiling is always capped by the PentaCookie's own institutional `authority_ceiling`; an oracle cannot raise a receiver above that ceiling by writing a larger `max_packet_risk`.

Invalid or unknown risk values fail closed.

## Bootstrap routing evidence

`penta_cookie_refresh_routes_v1(system_key)` derives a bounded baseline from the canonical system registry and declared capability registries. It always publishes the generic capabilities:

- `system:<system_key>`
- `category:<registry-category>` when present

It also publishes explicit protocol roles for current core Pentas:

| Penta | Packet capabilities |
| --- | --- |
| PentaCensus | `census.discovery`, `census.registry`, `discovery.canonicalize` |
| PentaHelper | `help.triage`, `help.remediate`, `help.escalate` |
| PentaDiscovery | `discovery.route`, `discovery.triage` |
| PentaPR | `github.pr.lifecycle`, `remediation.pr` |
| PentaPM | `project.manage`, `remediation.assign` |
| PentaSELF | `self.diagnose`, `self.heal`, `self.repair` plus enabled entries from its capability registry |
| PentaCrawler | `crawler.roam`, `crawler.research`, `discovery.observe` |

This list is message-routing metadata, not an execution-rights registry. PentaCensus/CHLOM remain responsible for canonical system identity and authority.

## Resolution modes

`pentas_route_packet_v1()` resolves four packet target kinds:

### `system`

Routes only to the exact active PentaCookie matching `target_ref`.

### `capability`

Routes to active PentaCookies whose observed or oracle routing descriptor advertises the exact capability and whose effective packet-risk ceiling accepts the packet.

Example:

```text
remediation.request
  target_kind = capability
  target_ref  = remediation.pr
         |
         +--> PentaPR delivery
```

### `mesh_lane`

Routes to active PentaCookies that advertise the requested mesh lane.

### `broadcast`

Only `target_ref=all-pentas` is recognized. Broadcast is restricted to D0/D1 information packets, excludes the source Penta, and is held if eligible fan-out exceeds 250 receivers. D2/D3 broadcast fails closed.

## Durable deliveries

Resolved targets are written to `pentas_packet_deliveries_v1`. Each delivery binds the packet to:

- target Penta system key;
- target cookie ID;
- exact target-cookie revision at route time;
- resolution basis;
- delivery lifecycle;
- lease/visibility timeout;
- attempt counters;
- terminal evidence.

A delivery cannot be hard-deleted.

The source packet remains immutable. Routing and acknowledgement evidence is appended through the packet receipt chain.

## Receiver flow

A Penta consumes packets through the bounded mesh contract rather than direct table reads:

1. `pentas_claim_v1(target_system_key, limit)` verifies the target has an active PentaCookie.
2. Expired leases are returned to pending or dead-lettered after the bounded retry ceiling.
3. Eligible deliveries are leased for five minutes with `FOR UPDATE SKIP LOCKED` semantics.
4. The receiver receives the packet envelope, source-cookie revision, content address, target-cookie revision and delivery lease.
5. `pentas_ack_v1()` requires the exact target system and lease ID.
6. Acknowledgement appends a receipt and updates the aggregate packet state.

Aggregate fan-out is fail-closed:

- all successful -> `delivered`;
- any explicit hold -> `held`;
- mixed success + dead-letter -> `held`;
- all terminal failures -> `dead_letter`.

Partial failure is never represented as full delivery.

## How PentaCrawler uses it

Each registered-estate roam cycle can:

1. install missing cookies incrementally;
2. refresh stale routing descriptors on a six-hour bounded interval;
3. observe registered system state;
4. detect/tag/raise broken-state evidence;
5. ingest discovery hand-raises;
6. route PentaDiscovery cases to PentaCensus/PentaHelp;
7. route pending Pentas packets to exact systems, capabilities or lanes based on cookie-carried descriptors.

This means a future Penta can participate in the mesh by becoming canonically registered, receiving a cookie and publishing governed routing capabilities. PentaCrawler does not need a code rewrite for every new Penta.

## Oracle mutation

Oracle routing changes remain subject to `penta_cookie_mutate_v1()` and therefore require exact-revision compare-and-swap, idempotency, CHLOM adjudication, quorum/confidence/disagreement gates and non-D3 automatic authority.

Oracle mutation can refine message routing. It cannot change stable institutional identity, create credentials, grant provider writes, move money, manufacture rights or create D3 authority.

## Decentralization path

The current delivery store is ThriveBase-backed, but the stable protocol is not tied to the transport. A future transport adapter can project the same packet/content-address/cookie-revision/delivery-receipt contract onto a queue, replicated log, P2P relay or cryptographically signed node fabric.

The transition must preserve:

- CHLOM authority boundaries;
- content-addressed packet identity;
- exact PentaCookie revisions;
- bounded TTL/hop/fan-out;
- idempotent replay;
- append-only delivery evidence;
- privacy classification and no forced public-chain disclosure.

Transport decentralization is not authority decentralization by default. Any future authority distribution requires its own CHLOM/governance design and independent production evidence.
