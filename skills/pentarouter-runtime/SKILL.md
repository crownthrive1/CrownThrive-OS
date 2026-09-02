# PentaRouter Runtime Skill

## Ownership

Bounded **PentaRouter™** capability for deterministic CrownThrive OS route selection. It coordinates existing planes, fabrics, bridges, meshes, and nodes; it does not create provider, financial, legal, rights, or D3 human authority.

## Purpose

Resolve secret-free work requests across standardized hot, warm, and cold lanes while preserving exact subject identity, idempotency, evidence, and fail-closed behavior.

## Deterministic sequence

1. Read the canonical PentaRouter topology manifest and exact source SHA.
2. Reject secret-bearing fields and structurally invalid requests.
3. Resolve risk, effect, authority state, requested lane, and registered operation route.
4. Select the healthiest eligible node by health, priority, capacity, and node ID.
5. Fail over only toward colder lanes: hot → warm → cold → HOLD.
6. Preserve the same subject, source SHA, principal, idempotency key, and evidence requirements through failover.
7. Emit a PentaAudit/PentaProof-compatible receipt without calling a provider.
8. Require provider readback before any downstream side effect can be declared complete.

## Hard boundaries

- No plaintext secrets or credentials.
- No hot-lane side effects.
- No automatic D3, rights, publishing, wallet, settlement, or provider authority.
- No cold-to-warm or warm-to-hot automatic escalation.
- No PASS based only on dispatch, queueing, or intent.
- No production claim without exact-head CI, independent certification, and required provider readback.

## Output

Return the exact subject, request fingerprint, attempted lanes, selected lane and node, controls, failover state, hold reasons, receipt identity, provider-execution flag, and readback requirement.
