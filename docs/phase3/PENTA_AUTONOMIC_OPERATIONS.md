# PENTA Autonomic Operations

Status: production implementation v1.1.0

## Purpose

The PENTA Autonomic Operations family converts observed runtime faults into bounded, evidence-driven incident handling without manufacturing authority or bypassing CHLOM controls.

Operating loop:

`PentaFlagger -> PentaTagger -> PentaHarvestor -> PentaBackup -> PentaBlue remediation -> PentaRed verification -> PentaMaker -> selected authoring Penta -> PentaMail`

PentaRed and PentaBlue provide adversarial and defensive verification. PentaMaker selects the authoring Penta; PentaMail is transport only.

## Canonical systems

- **PentaReports** — after-action, incident, verification, operational and assurance reports. A report may describe evidence but may never create a PASS that the evidence does not support.
- **PentaNotifs** — dedupe-aware notifications and escalation. Production delivery is routed through PentaMail.
- **PentaFlagger** — converts observed faults, failed gates and policy conditions into durable flags.
- **PentaTagger** — assigns machine-readable ownership, priority, domain and routing tags. Tags are metadata, not authority.
- **PentaHarvestor** — captures bounded evidence and hashes each harvested payload.
- **PentaBackup** — captures control-plane snapshots and binds backup intent to the existing CHLOM backup runtime.
- **PentaRestore** — fail-closed restore planning. An authorized restore requires verified provenance, integrity and restore readiness; dry runs perform no mutation.
- **PentaFlush** — TTL-bounded cleanup for explicitly ephemeral state only. It may never delete canonical audit, governance, rights, financial, evidence or institutional records.
- **PentaMaker** — selects the registered Penta that should author an artifact. It cannot send mail, certify results, or expand authority.

## PentaGreen 23514 repair

SQLSTATE `23514` was traced to the PentaGreen hourly writer persisting a commercial package identifier into `candidate_ref`, while `thriveevergreen_packets_candidate_identity_v1` reserves non-null `candidate_ref` for `proprietary_product_candidate` records.

The repair changes the writer, not the protective constraint:

- proprietary product candidate: persist `selected_candidate_ref`;
- commercial package: persist `selected_candidate_ref = NULL` and use `selected_sku` / `selected_package_id` identity.

The protective CHECK constraint remains intact.

## Recurrence-safe incident identity

`public.penta_incident_control_tick_v1()` runs every five minutes. Version 1.1 corrects a defect in the original dedupe model: the original fingerprint used only the system and SQLSTATE, so a later occurrence of the same `23514` could collide with an already-resolved incident.

The incident identity is now scoped to the failed run occurrence:

`SHA-256(system + error_code + run_id)`

A repeated tick for the same failed run dedupes. A later failed run with the same SQLSTATE receives a different fingerprint and is eligible for a new incident/remediation cycle.

The controller also ignores historical failed runs once a later production run has completed with `error_code IS NULL`. This prevents a resolved historical failure from being reprocessed forever.

## Automated incident flow

The controller:

1. finds the newest active PentaGreen production failure that has not been superseded by a later clean production execution;
2. creates or correlates the incident by run-occurrence fingerprint;
3. assigns priority and ownership tags;
4. harvests and hashes run evidence;
5. asks PentaMaker to select the author for the incident notice;
6. enqueues the selected Penta's message through PentaMail;
7. invokes only the registered remediation handler for the fault;
8. dedupes an already-applied remediation for the same occurrence;
9. waits for a later production execution with `run_state=completed` and `error_code=NULL`;
10. generates a hashed after-action report;
11. uses PentaMaker to select PentaReports for the AAR and sends it through PentaMail.

The registered `23514` handler is idempotent. It returns `already_compliant` when the repaired writer is already present and blocks on an unrecognized function fingerprint rather than guessing.

## Status projection v1.2

The canonical hourly status projection no longer aliases `selected_sku` into a field named `candidate_ref`.

For a commercial package it now reports distinct identity fields:

- `candidate_type = commercial_package`
- `candidate_ref = NULL`
- `candidate_sku = <commercial SKU>`
- `candidate_package_id = <package UUID>`
- `error_code = <actual latest run error or NULL>`

This removes a reporting ambiguity that could make a valid commercial-package row appear to violate the candidate identity contract.

## Red / Blue contract

`public.penta_redblue_pentagreen_23514_v1()` validates both sides of the control.

**Red assertions**
- legacy bad writer pattern is absent;
- protective CHECK constraint still exists.

**Blue assertions**
- conditional writer is present;
- latest production run completed;
- `error_code IS NULL`;
- `publication_count = 0` for the held observer execution;
- no money-movement function was invoked;
- no checkout activation was invoked.

A PASS may be reported only when every assertion is actually satisfied by current evidence. A historical PASS is not substituted for a newer failing run.

## Backup / Restore / Flush boundaries

`penta_backup_control_plane_v1()` creates a hashed control-plane snapshot and also asks the existing CHLOM backup runtime for an external backup job. The snapshot receipt is not declared restore-ready until the external backup/readback chain proves restore readiness.

`penta_restore_plan_v1()` is dry-run only in this baseline. It returns `blocked` when the backup receipt has not been marked restore-ready.

`penta_flush_ephemeral_v1()` defaults to dry-run. Its first production scope is terminal PentaMail outbox rows older than an explicit TTL. Canonical records are excluded.

## Current production truth contract

Software execution state and economic activation are separate facts. A clean PentaGreen production execution does not activate commerce when acceptance, certification, policy assurance, rights, checkout, pricing/tax, fulfillment, or other required evidence remains incomplete.

Status communications must report the newest production execution directly. They must not describe a historical execution as the current state and must not manufacture a PASS from stale evidence.
