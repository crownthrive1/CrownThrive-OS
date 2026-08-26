# PentaSerialized™ — Serialization, Lineage & Anti-Erasure Control Plane

**Canonical ID:** `ct.penta.serialized`  
**Version:** `1.0.0`  
**State:** ACTIVE source/CI control plane  
**Institutional generation:** Phase 3  
**Portal contract:** `/io/pentas/serialized`  
**Runtime:** `penta/runtime/serialized`  
**Policy:** `penta/registry/serialized-suite.json`

## Mission

PentaSerialized™ makes CrownThrive material state transitions explicit, ordered, hash-addressed, replay-safe, and recoverable. Its core rule is simple:

> A current value may change, but its prior institutional truth may not disappear silently.

PentaSerialized does not replace Git, databases, PentaVersion, PentaScribe, PentaSnapshot, PentaRollback, PentaSOPs, PentaSLAs, PentaFormat, PentaPR, PentaMerge, PentaRelease, PentaStatus, or PentaGeneration. It supplies the common serialization and continuity contract those systems can use.

## What it prevents

PentaSerialized is designed to fail closed against:

- blind overwrite of an existing serialized artifact;
- stale writers replacing a newer revision;
- silent file deletion in governed Git change sets;
- protected canonical files being modified without a continuity receipt;
- renames that sever predecessor/successor lineage;
- idempotency-key reuse for a different operation;
- resurrection of a tombstoned record without an explicit restore;
- ledger tampering, broken parent lineage, changed stable IDs, or payload-hash mismatch;
- materialized-current-state drift away from its append-only event history.

## Runtime model

Each store contains:

```text
<store>/
  meta/store.json
  ledger/events.jsonl
  index/current.json
  snapshots/*.json
  .penta-serialized.lock
```

`ledger/events.jsonl` is append-only. Each event carries:

- a stable `artifact_id`;
- a stable human/system `artifact_key`;
- Penta/artifact `kind`;
- independent artifact `version`;
- monotonic ledger `sequence`;
- `parent_revision`;
- SHA-256 `revision_id`;
- SHA-256 `payload_hash`;
- `previous_event_hash` and SHA-256 `event_hash`;
- operation: `create`, `update`, `tombstone`, `restore`, or `migrate`;
- actor, reason, timestamp, metadata;
- optional idempotency key plus semantic mutation fingerprint.

The current index is a projection of the ledger. `verify` independently rematerializes the ledger and fails if the index differs.

## Mutation gate

### Create

A new artifact may be created without an expected revision because no previous revision exists.

### Update

An existing artifact **must** supply its exact current `expected_revision`. Missing or stale values fail closed. This is optimistic concurrency control and prevents last-writer-wins data loss.

### Tombstone

There is no runtime hard-delete method. Retirement/deletion is represented by an append-only tombstone that references the prior preserved revision and requires:

- exact expected revision;
- actor;
- reason.

### Restore

Restore never rewrites the tombstone or prior history. It appends a new live revision whose metadata points to both the tombstone and the preserved source revision.

### Idempotency

A repeated request with the same idempotency key and same semantic mutation returns the original event. Reusing the key for a different mutation fails closed.

## Git continuity gate

The `git-gate` command examines a base/head diff. It requires a serialized continuity receipt for:

1. **every deletion**;
2. **every rename**;
3. **modification of configured protected/canonical paths**.

A valid modification receipt binds the previous Git blob SHA, new Git blob SHA, reason, and rollback ref. A deletion additionally requires a tombstone declaration. A rename requires predecessor path plus successor identity.

This means a pull request cannot silently alter protected canonical records or remove a file merely because Git itself permits the operation.

### Receipt shape

```json
{
  "schema": "crownthrive.penta.serialized.git-receipt/v1",
  "receipt_id": "example",
  "changes": [
    {
      "path": "docs/versioning/VERSION_REGISTRY.json",
      "operation": "modify",
      "previous_blob_sha": "<base blob>",
      "new_blob_sha": "<head blob>",
      "reason": "Add a governed component record",
      "rollback_ref": "<known-good git ref>"
    }
  ]
}
```

Receipts live under `penta/continuity/receipts/` and become continuity evidence themselves.

## Penta family adapters

PentaSerialized v1 has explicit structural adapters for the first convergence set.

| System | Serialized minimum | Role |
|---|---|---|
| **PentaVersion™** | subject ID, version, scheme, lifecycle, effective time | Version lineage and effective-state history |
| **PentaFormat™** | format ID, media type, schema version, canonical extension | Format/schema identity and migration safety |
| **PentaSOPs™** | SOP ID, owner, lifecycle, effective time, review date, steps | Procedure lineage and controlled supersession |
| **PentaSLAs™** | SLA ID, service ID, effective time, targets, escalation owner | Service commitment/effective-period history |
| **PentaScribe™** | record ID/type, source references, lifecycle | Provenance-preserving institutional record capture |

Generic payloads remain supported so other Penta systems can adopt the envelope without pretending they use an adapter they do not yet satisfy.

## Convergence map

### PentaVersion

PentaVersion owns version semantics. PentaSerialized owns the immutable transition record. A new version does not overwrite its predecessor; it appends lineage.

### PentaFormat

PentaFormat owns format and schema definitions. PentaSerialized canonicalizes its JSON representation and binds schema/format revisions to hashes so migrations are detectable and reversible.

### PentaSOPs and PentaSLAs

Policies, procedures, SLAs, SLOs, review periods, escalation ownership, and effective dates change over time. PentaSerialized preserves each accepted state rather than rewriting the past to resemble the present.

### PentaScribe

PentaScribe can emit institutional records into PentaSerialized with explicit source references. The result is a provenance-linked, hash-addressed record with history rather than a mutable note.

### PentaSnapshot and PentaRollback

`snapshot` produces a content-addressed recovery baseline containing current record state and the last ledger event hash. PentaSnapshot may preserve/distribute that baseline. PentaRollback may restore from preserved revisions, but restore is represented as a new append-only revision rather than history alteration.

### PentaLiency, PentaBlue, PentaRed, and PentaHoneyPot

Integrity failures, stale-write conflicts, receipt failures, and restore results are evidence inputs to resilience/hardening. Red-team simulation remains confined to authorized isolated clone ranges; PentaSerialized does not widen attack authority.

### PentaPR, PentaMerge, and PentaCloser

PentaPR invokes continuity assurance on change sets. PentaMerge treats a HOLD from PentaSerialized as not merge-ready. PentaCloser may remediate missing receipts/lineage, but may not suppress a failed gate.

### PentaRelease

Release records, package checksums, provider readbacks, and supersession can use serialized records. Serialization does not itself prove a provider deployment or create release authority.

### PentaStatus

Status output should expose at least integrity PASS/HOLD, artifact count, event count, tombstone count, last event hash, and continuity-gate state without exposing restricted payload data.

### PentaGeneration

Stable IDs, predecessors, tombstones, restores, snapshots, and event hashes form continuity evidence that can be inherited across long-horizon stewardship and succession workflows.

## CLI

Initialize:

```bash
python -m penta.runtime.serialized init /var/lib/crownthrive/serialized
```

Create:

```bash
python -m penta.runtime.serialized put /var/lib/crownthrive/serialized \
  policy:example PentaScribe 1.0.0 @record.json \
  --actor penta-scribe --idempotency-key request-123
```

Update with compare-and-swap protection:

```bash
python -m penta.runtime.serialized put /var/lib/crownthrive/serialized \
  policy:example PentaScribe 1.1.0 @record-v1.1.json \
  --actor penta-scribe \
  --reason 'approved policy revision' \
  --expected-revision '<current revision hash>' \
  --idempotency-key request-124
```

Tombstone:

```bash
python -m penta.runtime.serialized tombstone /var/lib/crownthrive/serialized \
  policy:example \
  --expected-revision '<current revision hash>' \
  --actor penta-scribe \
  --reason 'superseded by policy:new'
```

Restore:

```bash
python -m penta.runtime.serialized restore /var/lib/crownthrive/serialized \
  policy:example \
  --expected-revision '<tombstone revision hash>' \
  --actor penta-rollback \
  --reason 'approved recovery'
```

Verify and snapshot:

```bash
python -m penta.runtime.serialized verify /var/lib/crownthrive/serialized
python -m penta.runtime.serialized snapshot /var/lib/crownthrive/serialized \
  --actor penta-snapshot --reason 'pre-release recovery baseline'
```

Repository continuity check:

```bash
python -m penta.runtime.serialized git-gate \
  --repo . \
  --base '<base sha>' \
  --head '<head sha>' \
  --policy penta/registry/serialized-suite.json
```

## Automation

`.github/workflows/penta-serialized-assurance.yml` runs:

- Python compile assurance;
- the PentaSerialized unit suite;
- a runtime smoke cycle covering create → update → tombstone → restore → verify → snapshot;
- PR/push continuity diff gating;
- scheduled integrity/self-test runs;
- PentaStatus-style summary output.

The workflow has read-only repository permissions. It validates and gates; it does not manufacture merge, release, provider-write, rights, or deletion authority.

## Failure semantics

PentaSerialized returns **HOLD** for integrity, authorization-by-contract, stale-state, receipt, format, or lineage failures. Downstream automation should stop the affected mutation and route evidence to the appropriate owner/Penta subsystem. It must not weaken validation simply to get a green build.

## Recovery semantics

A recovery is valid only when:

1. the source revision exists in preserved history or an accepted snapshot;
2. the current revision is explicitly identified;
3. the caller has independent authority to request restoration;
4. the restore appends a new event;
5. post-restore verification passes;
6. dependent systems reconcile/read back the restored state.

## Security and boundaries

- PentaSerialized stores serialized payloads; callers remain responsible for data classification and must not place secrets or restricted data into a store not approved for that class.
- Hashes prove content consistency, not truth, ownership, authorization, legal sufficiency, or provider execution.
- File locking is fail-closed on unsupported hosts.
- The v1 runtime uses local durable filesystem primitives and standard-library Python. Provider/database adapters can be certified separately without changing the canonical envelope.
- Physical retention/purge, if ever required, must be implemented as a separately governed capability with policy evidence. It is intentionally absent from v1.

## Completion/readback standard

PentaSerialized is operational for a repository/runtime surface only when the applicable code is present, tests pass, its continuity workflow passes on the exact revision, the registry/Family records are reconciled, and the merge/readback state is verified. A branch or document alone is not production proof.
