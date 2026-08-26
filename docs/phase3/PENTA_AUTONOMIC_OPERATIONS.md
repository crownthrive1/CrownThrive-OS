# PENTA Autonomic Operations

Status: production implementation baseline v1.0.0

## Purpose

The PENTA Autonomic Operations family converts observed runtime faults into bounded, evidence-driven incident handling without manufacturing authority or bypassing CHLOM governance.

Operating loop:

`PentaNotifs -> PentaFlagger -> PentaTagger -> PentaHarvestor -> PentaBackup -> PentaHybrid/CHLOM -> registered remediation -> PentaAssure/PentaCertify -> PentaReports -> PentaMail`

PentaRed and PentaBlue provide adversarial and defensive verification around this loop.

## Canonical systems

- **PentaReports** — after-action, incident, verification, operational and assurance reports. A report may describe evidence but may never create a PASS that the evidence does not support.
- **PentaNotifs** — dedupe-aware notifications and escalation. Production delivery is routed through PentaMail.
- **PentaFlagger** — converts observed faults, failed gates and policy conditions into durable flags.
- **PentaTagger** — assigns machine-readable ownership, priority, domain and routing tags. Tags are metadata, not authority.
- **PentaHarvestor** — captures bounded evidence and hashes each harvested payload.
- **PentaBackup** — captures control-plane snapshots and binds backup intent to the existing CHLOM backup runtime.
- **PentaRestore** — fail-closed restore planning. An authorized restore requires verified provenance, integrity and restore readiness; dry runs perform no mutation.
- **PentaFlush** — TTL-bounded cleanup for explicitly ephemeral state only. It may never delete canonical audit, governance, rights, financial, evidence or institutional records.

## PentaGreen P0 incident contract

SQLSTATE `23514` was traced to the PentaGreen hourly writer persisting a commercial package identifier into `candidate_ref`, while `thriveevergreen_packets_candidate_identity_v1` reserves non-null `candidate_ref` for `proprietary_product_candidate` records.

The repair changes the writer, not the protective constraint:

- proprietary product candidate: persist `candidate_ref`;
- commercial package: persist `candidate_ref = NULL` and use `sku`/`package_id` identity.

The protective CHECK constraint remains intact.

## Automated incident flow

`public.penta_incident_control_tick_v1()` runs every five minutes and:

1. finds the latest failed PentaGreen governed hourly execution;
2. creates or correlates the incident by error fingerprint;
3. assigns priority and ownership tags;
4. harvests and hashes run evidence;
5. enqueues a PentaMail incident notification;
6. invokes only a registered, exact-fingerprint remediation handler;
7. waits for a subsequent governed successful execution;
8. generates a hashed after-action report;
9. enqueues the resolved AAR through PentaMail.

The registered `23514` handler is idempotent. It returns `already_compliant` when the repaired writer is already present and blocks on an unrecognized function fingerprint rather than guessing.

## Red / Blue contract

`public.penta_redblue_pentagreen_23514_v1()` validates both sides of the control:

**Red assertions**
- legacy bad writer pattern is absent;
- protective CHECK constraint still exists.

**Blue assertions**
- conditional writer is present;
- latest governed run completed;
- `error_code IS NULL`;
- `publication_count = 0` for the held observer execution;
- no money-movement function was invoked;
- no checkout activation was invoked.

A PASS requires every assertion.

## Backup / Restore / Flush boundaries

`penta_backup_control_plane_v1()` creates a hashed control-plane snapshot and also asks the existing CHLOM backup runtime for an external backup job. The snapshot receipt is not declared restore-ready until the external backup/readback chain proves restore readiness.

`penta_restore_plan_v1()` is dry-run only in this baseline. It deliberately returns `blocked` when the backup receipt has not yet been marked restore-ready.

`penta_flush_ephemeral_v1()` defaults to dry-run. Its first production scope is terminal PentaMail outbox rows older than an explicit TTL. Canonical records are excluded.

## Production truth

A software repair and a business/economic release are different facts. Removing the PentaGreen `23514` execution defect does **not** authorize economic activation. PentaGreen remains HOLD whenever governed acceptance, exact certification, policy assurance, rights, checkout, pricing/tax, fulfillment or other required evidence remains incomplete.
