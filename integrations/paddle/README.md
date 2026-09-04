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

## Runtime policy

All Paddle work must first load `skills/paddle-billing-governed-routing/SKILL.md`, then load the matching upstream `paddle-*` implementation skill.

`paddle-sandbox` is the default execution lane. Its bearer token is resolved only from `PADDLE_SANDBOX_API_KEY` in a protected runtime or operator keychain.

`paddle-live` uses provider OAuth in the eligible operator context. Live write access is not inferred from connection success. Each live mutation remains `HOLD` until the exact operation has explicit human direction, current CrownThrive authority, provider permission, bounded scope, duplicate control, rollback or compensation, and readback.

## Activation sequence

1. Accept and merge the exact source candidate after CI and required review.
2. Import or sync the CrownThrive OS marketplace from the repository.
3. Make the Paddle plugin available to the intended Codex role.
4. Bind a least-privilege Paddle sandbox key to `PADDLE_SANDBOX_API_KEY` outside Git.
5. Authenticate `paddle-docs` when prompted.
6. Run a documentation lookup through `paddle-docs`.
7. Run the governed sandbox test sequence through `paddle-sandbox`; preserve sanitized readback.
8. Authorize `paddle-live` with OAuth only for an eligible operator. Keep the connection read-only unless a separately authorized live write is required.
9. Reconcile any provider side effect into PentaGreen, CHLOM, entitlement, webhook, and DAIL surfaces only within their own authority.
10. Advance production state only after security review and independent verification.

## Validation

Run:

```bash
python3 scripts/validate_paddle_integration.py
python3 -m unittest tests.test_paddle_integration
```

The validator proves the checked source contract only. It does not contact Paddle, authenticate an account, perform a transaction, or certify production.

## Failure and rollback

On authentication, permission, schema, idempotency, webhook, reconciliation, or readback failure:

1. Stop the affected mutation lane.
2. Preserve a sanitized error receipt.
3. Revoke or reduce provider authority where exposure is possible.
4. Compensate or roll back only through an authorized provider operation.
5. Rerun the original control and broader regression checks.
6. Keep production state at `HOLD` until evidence is complete.

To remove the integration, disable or remove the plugin, remove the three root MCP entries, revoke live OAuth, and rotate or revoke the sandbox key. Preserve source and provider history.
