# PentaMation — Governed Automation & Orchestration Layer

**Machine key:** `penta.mation`

PentaMation is CrownThrive's canonical automation/orchestration layer. Its job is to turn already-authorized institutional intent into repeatable event-driven or scheduled workflows while preserving authority, evidence, retries, compensation, human gates, and terminal verification.

PentaMation is deliberately separated from three neighboring responsibilities:

- **PentaTime** owns clocks, recurrence, windows, expirations and temporal truth.
- **PentaRoute** owns exact route/provider/runtime resolution and certified execution paths.
- **PentaMation** owns the multi-step workflow state machine that coordinates triggers, dependencies, jobs, retries, handoffs and convergence.

It does not create authority. If CHLOM, a provider binding, a human quorum, a credential, an entitlement, or a certification is missing, PentaMation must fail closed or route the matter through PentaHybrid.

## Runtime state model

A workflow instance uses the following terminal and non-terminal states:

```text
registered
  → discovered
  → governance_pending
  → ready
  → running
  → human_gate
  → verifying
  → succeeded

Failure branches:
  governance_blocked
  dependency_blocked
  retry_wait
  compensating
  failed
  held
  cancelled
```

`succeeded` is valid only after the declared verification contract passes. An HTTP 2xx, queue acknowledgment, provider "accepted" response, or process exit code is not automatically terminal proof.

## Required workflow fields

Every workflow definition must declare:

- stable workflow ID and version;
- trigger type and source;
- accountable owner;
- CHLOM authority/policy reference;
- risk class D0–D3;
- exact dependencies;
- idempotency strategy;
- human-gate rule or explicit `none`;
- retry/backoff policy;
- compensation/rollback/remedy behavior;
- provider/route capability references;
- terminal verification requirements;
- DAIL/PentaDocs preservation targets.

## Authority and human gates

PentaMation evaluates the workflow before each consequential mutation. The result is one of:

```text
ALLOW_BOUNDED_EXECUTION
REQUIRE_HUMAN_REVIEW
REQUIRE_HUMAN_APPROVAL
HOLD_MISSING_AUTHORITY
HOLD_MISSING_EVIDENCE
HOLD_PROVIDER_UNCERTIFIED
HOLD_CONFLICT_OF_DUTY
```

PentaHybrid owns the human-review/approval transaction, including identity, quorum, recusal, override reason and response evidence. PentaMation resumes only when the human-gate record is valid for the exact workflow version and risk context.

## Reliability contract

PentaMation workflows must prefer deterministic, replay-safe behavior:

- idempotency keys for mutating steps;
- bounded retries with backoff and maximum attempts;
- dead-letter/hold state instead of infinite retry loops;
- dependency timeouts;
- explicit compensation for partially applied changes where possible;
- read-after-write for provider mutations;
- state reconciliation after network/process interruption;
- exact workflow/version receipts;
- no silent success when verification is incomplete.

## Scheduler convergence

External schedulers are treated as scarce failure-domain clocks. PentaMation should move recurring institutional work behind PentaTime and internal registered queues/workflows whenever feasible. A new external clock requires explicit justification, ownership, health evidence and scheduler-topology registration.

## PENTA five-stage mapping

### Discover
Resolve the trigger, current instance state, dependencies, bound credentials/capabilities, target provider state and the exact workflow/version contract.

### Govern
Resolve CHLOM authority, risk class, human-gate policy, separation of duties, time window, retries, compensation, privacy/security constraints and provider certification.

### Execute
Run the bounded state machine through PentaRoute, Penta MCP, provider adapters, queues, PentaFactory or registered leaf systems.

### Verify
Require declared readback, canaries, tests, hashes, receipts, provider reads or reconciliation before terminal success.

### Preserve
Write the workflow definition/version, attempt graph, step outcomes, human decisions, evidence hashes, compensation, terminal status and continuity context to DAIL/PentaDocs/ThriveBase as applicable.

## Initial orchestration families

PentaMation is intended to absorb repeated multi-system coordination such as:

- documentation/articleization and source reconciliation;
- PentaFactory build/test/release/deploy pipelines;
- media ingest/scheduling/publication maintenance;
- provider heartbeat and certification maintenance;
- commerce/entitlement reconciliation where payment authority is already defined;
- backup/continuity exercises;
- registry drift detection and repair proposals;
- human governance queues and committee handoffs;
- research watch → study → decision-review workflows.

Each family requires its own bounded contracts; the PentaMation name does not certify every possible mutation.

## Machine-readable representation

PentaMation is registered in `data/penta/systems.registry.json`. Workflow-schema and runtime expansion should remain backwards compatible through explicit versioning rather than hidden mutation of active contracts.
