# Executable Agent Contract & Version Convergence Standard v1

## Purpose

A CrownThrive agent is not executable merely because an agent row, skill name, schedule, prompt, or documentation page exists. Controlled-test executability requires a complete machine-checkable chain: registered agent identity, installed skill contract, explicit privilege profile, callable capability with a materialized handler, bounded authority, a real successful invocation receipt, and health evidence derived from that execution.

## Executability chain

The minimum chain is:

`agent template -> skill package -> privilege profile -> executable capability -> materialized handler -> invocation receipt -> independent verifier boundary -> health/readback`

Missing links fail closed. A descriptive-only or disabled capability is not silently treated as runnable.

## Authority

This convergence layer is D0-D2 only. D3 remains human-reserved. Provider writes, money movement, rights grants, checkout activation, direct-main writes, self-approval, self-certification, sovereign voting and secret-body return are prohibited unless a different exact governed contract explicitly authorizes them.

A capability can be executable while still being controlled-test and read-only or plan-only. Executability does not imply production activation.

## Current suite versions

- Architecture Self-Awareness: `1.1.0`
- CHLOM Wallet Independent Review: `2.0.0`
- Commercial Release Factory: `2.1.0`
- CrownThrive Services Stack: `1.1.0`
- Execution Builder: `1.1.0`
- Framework Factory Precompile: `1.1.0`
- Sites Fleet Orchestration: `1.1.0`

Version advancement records current contract truth. Historical versions remain evidence and are not rewritten.

## CHLOM Wallet reviewers

The five independent-review schedules already bind exact v2 work IDs, Git head, evidence digest and runtime functions. The executable contract exposes bounded status and heartbeat operations only. Its canary does not cast a review decision, satisfy a vote, release a wallet, advance a phase, deploy code or move money.

## Commercial Release Factory

The 18 workers now have an executable controlled-test worker planning contract. It validates worker identity, skill installation, assigned sealed-algorithm contracts and Vault custody where applicable, then emits a sanitized plan pending independent verification.

The eight proprietary release algorithms remain `non_executable` and `disabled` because their sealed private methods do not yet have a separately materialized executor. A Vault JSON/prose/formula bundle must never be treated as executable code merely because it exists. The worker-plan contract explicitly returns `private_method_executed=false` and grants no provider, publication, checkout, financial or rights authority.

## CrownThrive Services Stack

Each CSS agent has a bounded self-test capability over the current service-contract registry. The self-test observes the contract estate and agent role lens but does not execute write-effect contracts or provider mutations. Service-write contracts remain governed separately by their idempotency, rollback, readback and verifier requirements.

## Framework Factory Precompile

Each framework precompile agent has an executable inspection capability and a public-safe skill contract. It may inspect its package state and assigned construction work. It remains precompile-only: no automatic materialization, activation, certification, vote, provider write or D3 effect is created.

## Sites Fleet

The Sites Fleet Orchestrator has a read-only executable contract for inventory and bootstrap verification. It may read current site surfaces and run the existing bootstrap verifier. It may not enqueue publication, mutate a provider, create publication authority or interpret an existing provider authorization as permission to publish.

## Architecture Self-Awareness

The Architecture Refactor & Optimization Agent now exposes its existing bounded self-model rebuild through an exact executable capability. The wrapper records a controlled-test invocation and keeps macro auto-apply, destructive actions, provider writes and D3 disabled. No competing scheduler was added.

## Execution Builder

The Execution Builder's previously certified materialization capability is now paired with an explicit privilege profile. Its health remains grounded in real build receipts, not synthetic probes. Build success still ends at `BUILT_PENDING_INDEPENDENT_VERIFICATION`; it cannot self-certify or self-merge.

## Source and version integrity

When a current manifest path is stale, correct the current projection and retain the old path as historical metadata. Do not reuse Git blob SHA-1 values as SHA-256 manifest digests. Exact-main source digests are populated only after the merged source is independently read back.

## Health rule

`healthy` in this layer means controlled-test operational presence for the exact capability that produced the receipt. It does not mean production readiness, economic approval, provider mutation authority or D3 authority.
