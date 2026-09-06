# Paddle Billing MCP and Agent Skills Integration

Stable ID: `ct.integration.paddle-billing`

This integration adds Paddle Billing to the CrownThrive OS agent and MCP fabric without treating provider connectivity as commerce authority.

## Source binding

The CrownThrive marketplace manifest references the official `PaddleHQ/paddle-agent-skills` Codex plugin by `git-subdir` and pins the full upstream commit recorded in `paddle-billing.registry.json`. The pin prevents an upstream change from silently entering the OS. Updating Paddle requires a new reviewed source change, a new exact commit, and a rerun of the integration validator.

The upstream plugin supplies ten Paddle Billing skills plus three MCP servers:

- `paddle-docs`
- `paddle-sandbox`
- `paddle-live`

Paddle Classic is excluded.

## CrownThrive OS MCP control surface

`api/mcp.js` supplies the previously missing `/api/mcp` handler referenced by the root `.mcp.json`. It is dependency-free, stateless, and serves both MCP eras:

- modern `2026-07-28` through `server/discover`, per-request metadata, `Mcp-Method`/`Mcp-Name` validation, cache hints, and no protocol session;
- legacy `2025-11-25`, `2025-06-18`, `2025-03-26`, and `2024-11-05` through `initialize` compatibility.

Every request is independently protected by `CROWNTHRIVE_CONTROL_TOKEN`. Missing or invalid control-token binding fails closed before MCP dispatch.

The OS MCP exposes three read-only orchestration tools:

- `crownthrive_paddle_route` selects the exact Paddle skill and direct upstream MCP lane;
- `crownthrive_paddle_preflight` reports local credential and authority blockers without contacting Paddle;
- `crownthrive_paddle_integration_status` returns public-safe source and gate state without exposing secret values.

It also exposes three resources and one governed-operation prompt. The OS endpoint does not proxy or execute Paddle mutations. Provider operations continue through the pinned direct `paddle-docs`, `paddle-sandbox`, or `paddle-live` server after routing, skill loading, authorization, and preflight.

## Runtime policy

All Paddle work must first call `crownthrive_paddle_route`, load `skills/paddle-billing-governed-routing/SKILL.md`, and then load the matching upstream `paddle-*` implementation skill. This sequence makes the upstream Paddle skills operationally mandatory rather than merely installed.

`paddle-sandbox` is the default execution lane. Its bearer token is resolved only from `PADDLE_SANDBOX_API_KEY` in a protected runtime or operator keychain.

`paddle-live` uses provider OAuth in the eligible operator context. Live write access is not inferred from connection success. Each live mutation remains `HOLD` until the exact operation has explicit human direction, current CrownThrive authority, provider permission, bounded scope, duplicate control, rollback or compensation, and readback.

## Activation sequence

1. Accept and merge the exact source candidate after CI and required review.
2. Confirm the Vercel deployment contains the new `/api/mcp` function.
3. Bind `CROWNTHRIVE_CONTROL_TOKEN` to both the eligible MCP client and the protected Vercel runtime; never write it to Git.
4. Perform an authenticated `/api/mcp` handler readback and modern `server/discover` canary.
5. Import or sync the CrownThrive OS marketplace from the repository.
6. Make the Paddle plugin available to the intended Codex role.
7. Bind a least-privilege Paddle sandbox key to `PADDLE_SANDBOX_API_KEY` outside Git.
8. Call `crownthrive_paddle_route` and `crownthrive_paddle_preflight` for the bounded task.
9. Load the exact returned upstream `paddle-*` skill.
10. Authenticate `paddle-docs` when prompted and resolve current provider semantics.
11. Run the governed sandbox test sequence through `paddle-sandbox`; preserve sanitized provider readback.
12. Authorize `paddle-live` with OAuth only for an eligible operator. Keep the connection read-only unless a separately authorized live write is required.
13. Reconcile any provider side effect into PentaGreen, CHLOM, entitlement, webhook, and DAIL surfaces only within their own authority.
14. Advance production state only after security review and independent verification.

## Validation

Run:

```bash
python3 scripts/validate_paddle_integration.py
python3 -m unittest tests.test_paddle_integration
node --experimental-default-type=module --check api/mcp.js
node --experimental-default-type=module --test tests/test_mcp_handler.mjs
```

The deterministic local MCP suite exercises authentication, modern discovery, legacy initialization, tool listing, exact catalog-skill routing, live fail-closed behavior, header mismatch rejection, unsupported-version negotiation, and credential redaction. It does not contact Paddle or prove a provider account connection.

## Failure and rollback

On authentication, permission, schema, idempotency, webhook, reconciliation, or readback failure:

1. Stop the affected mutation lane.
2. Preserve a sanitized error receipt.
3. Revoke or reduce provider authority where exposure is possible.
4. Compensate or roll back only through an authorized provider operation.
5. Rerun the original control and broader regression checks.
6. Keep production state at `HOLD` until evidence is complete.

To remove the integration, disable or remove the plugin, remove the three direct Paddle MCP entries, remove the Paddle orchestration tools from `/api/mcp`, revoke live OAuth, and rotate or revoke the sandbox key. Preserve source and provider history.
