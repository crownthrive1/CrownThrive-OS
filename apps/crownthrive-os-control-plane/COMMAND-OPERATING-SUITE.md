# CrownThrive Command — Operating Suite v1.0

Contract: `ct.command.operating-suite.v1`  
Route: `/estate#operating-suite`  
API: `/api/command-suite`  
Owner: CrownThrive, LLC; founder-delegated operating authority.  
Source and acceptance date: 2026-09-16. Production state requires a separate release receipt; a source commit is not deployment proof.

## Daily use

Open **Operating suite** in Command navigation. Public visitors see source coverage, never private records. Sign in with the existing ThriveBase account; the server verifies the PentaBrain operator grant. No account, permission, or credential is created. The registered operator account has a password configured; this configuration check is not a completed user sign-in.

Choose a workspace, then a source. Search source names to find a registry; search the selected source to find records. **Inspect** opens the allowed metadata fields, including state, ownership, timestamps, gates, and safe evidence links. Pagination is primary-key based except the explicitly marked MCP view. Catalog discovery uses unique object identifiers. The flagged-row checkbox only filters the current page; it does not prove other pages are clear. JSON export contains the current page, not a complete inventory export.

**Request inspection** and **Reconcile source metadata** enqueue real bounded requests in the existing CHLOM action worker. The executor validates the selected source schema and reads one metadata row, persists a hash/readback receipt, and reports its actual terminal state. It does not reconcile every row, compare an entire provider account, repair a website, send mail, publish, grant rights, move money, change credentials, or override holds. These boundaries are displayed beside the controls. Request acceptance is not execution success.

## Workspaces

| Workspace | Source adapters |
| --- | --- |
| Estate | Canonical created/registered identities |
| Websites | All rows in registered website surfaces |
| Pentas | Penta identities, operating registry, runtime agents, factories |
| Personas | Communication personas and storefront profiles |
| Products | Governed catalog and factory-built product/publication gates |
| PentaBrain | Model registry and knowledge/rights records |
| PentaMailer | Provider route holds and readback states |
| Integrations | Services, adapters, endpoints, API/MCP inventory, plugins and bindings |
| Fabrics | Fabrics, layers, storage controls |
| DAIL / Cursor | Registered systems, cursor controls, rails, Wasabi archive cursor |
| Activity | Canonical DAIL event metadata, excluding payloads and actor identities |
| Drive / Docs | Packages, folders, artifacts, uploads, reconciliation ledger and deltas |
| Operations | Existing jobs, job outcomes, remediation, commercial repairs, mesh requests |
| Coverage / Discovery | Non-secret database relation and routine metadata |

Forty explicit adapters were bound and each passed a live bounded source read. Drive artifact and upload registries returned zero rows during acceptance. This is an empty selected registry, not a claim that Drive has no files. Discovery observed 2,926 eligible relations and 4,670 routines at 2026-09-16T23:23:59Z: database-object counts, not unique websites, products, callable APIs, or active agents. Source estimates overlap and must not be added together.

Every new row in a mapped source becomes visible without regenerating a snapshot. New database objects appear in catalog discovery. A new provider or row-level adapter requires its existing owner to verify schema, identity, visibility and execution contracts; discovery never grants permissions or makes endpoints callable.

Drive consumes existing PentaDocs/Factory metadata and provider-readback states and links to original records. It is not a full-account Google Drive crawl and does not expose document bodies. Records outside these indexes remain a coverage gap.

## API

`GET ?op=overview`: source bindings, estimates, coverage and controls.  
`GET ?op=session`: existing operator session.  
`GET ?op=records&source=<key>&limit=50&q=<literal>&cursor=<JSON>`: protected pages.  
`POST {op:login,email,password}`: existing Supabase account and operator authorization.  
`POST {op:logout}`: clear this host's session cookie.  
`POST {op:request,source,action,request_id}`: inspect/reconcile only.  
`GET ?op=request&id=<UUID>`: persisted request state.

Page limits are 1–100; query length 120 characters; cursor 4 KB; request body 16 KB; response 2 MB. DAIL text searches are bounded to the latest 10,000 actual events; unfiltered DAIL pagination continues by sequence key. The MCP inventory view explicitly uses offset pagination because unique-key evidence is absent.

The access token is placed only in an HttpOnly, Secure, SameSite=Strict host cookie. No access/refresh token is returned to JavaScript or stored in localStorage. Existing bearer tokens are validated through the provider user endpoint. Caller-supplied operator UUIDs are rejected. No new user grants are created. Session expiry or grant revocation requires fresh authorization.

POSTs require an allowed same-origin Origin and `X-Command-Suite: 1`. The database verifies the existing management capability, deduplicates by user/request ID, coalesces pending source/action work, and limits new work to ten requests per minute per operator. Existing worker job 1947 remains the executor. No second scheduler was created.

The four public-schema suite RPCs grant execution only to service_role. The API validates the real user before supplying their UUID to protected wrappers. Private implementation tables/views revoke public/anon/authenticated access. Secrets, configuration payloads, private mail/document bodies and raw DAIL payloads are excluded. Source values use textContent, not HTML injection. Links reject non-HTTPS schemes and credential-bearing URL parameters.

## Freshness and reliability

The UI observes existing Command `#fresh` updates and its manual Refresh button, coalesces work, pauses when hidden, aborts on page exit and labels snapshots stale after 90 seconds. It adds no polling interval. This is near-real-time refresh, not instantaneous streaming. Source timestamps, stored provider-readback timestamps and retrieval timestamps are separate.

Missing tables, schema drift, transport failure, denial, empty sources and stale data are distinct. Registration, enabled flags, deployment previews, enqueued work or metadata readback never constitute provider health or complete fulfillment. Paid-storage, source-pruning, sale-readiness and authority gates are unchanged.

## Acceptance before release

24 Node tests passed locally: auth, grant denial, origin/CSRF, identity injection, literal query parameters, bounds, projection, secure cookie, sanitized failures, methods and request/readback separation. `tests/command-suite.test.mjs` includes these cases in the existing canonical app validator.

11 local browser checks passed in Chromium 144 using mocked APIs: DOM-ready mount, source navigation, signed-out restrictions, mocked sign-in, dialog, paging/search, request/readback, desktop layout, 390px mobile overflow and stale failure handling. These are not live browser/operator-authentication tests.

All forty live DB sources passed bounded reads. Website keyset pagination returned two rows per page with zero overlap. Anonymous and ordinary authenticated execution of all four public RPCs was denied by privileges; service-role execution remained allowed.

Live service-side request `e55fe77c-106f-4769-af71-c4b11e901f9a` completed through the existing worker on its first attempt at 2026-09-16T23:20:03Z. Persisted metadata SHA256: `82a68b99a2adc30c3ebcc4c7f258e135e3331ac06a51aeeff967981615d9986d`. This is backend executor acceptance, not a browser login test or provider reconciliation.

## Installation, preservation and rollback

Core migration: `supabase/migrations/20260916231518_command_operating_suite_core_v1.sql`.
Companion seed: **`supabase/command_operating_suite_sources_v1.sql`**; apply after the core DDL. The migration's companion note refers to this file one directory above the migrations folder.

Migration name `command_operating_suite_core_v1` was applied on ThriveBase, then the finite source seed was applied. Before wrapping the original worker, its exact definition was stored in `command_suite_change_snapshots_v1` and copied to `chlom_mesh_action_execute_one_before_suite_v1`. Original SHA256: `48b6523e2e0c792f5bff0dc2d0becd4f9dc3070d34802524fa21f09e1c17c034`. Only new `command-source:` requests take the new path; all other target classes delegate to the original implementation.

UI rollback removes only suite injection constants and lines from command-loader.js through the reviewed release path. Preserve other Command extensions. Backend rollback first checks no suite request is active, then restores the saved original function through the existing migration owner while retaining requests/evidence. Do not delete providers, source data, grants, jobs, objects or cursors. The original worker's existing callability is not broadened for non-command targets.

## Remaining integration work

Native editing/retry/send/publish controls require exact authenticated owner adapters and their current approval, entitlement, suppression and readback gates; they are not implemented by this metadata suite. Independent recovery, Wasabi backfill, native media cutovers, paid-storage activation and full Drive-account coverage remain separate unfinished work. The registry also contains an older Institutional Command site; its identity must not be overwritten or silently equated with the Vercel Command app. A deployed dashboard does not prove those separate migrations complete.
