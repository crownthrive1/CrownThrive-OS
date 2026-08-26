# Penta Resilience Suite™

**Status:** institutional software baseline v1.0.0  
**Owner:** CrownThrive, LLC  
**Control plane:** CrownThrive IO  
**Documentation plane:** PentaDocs  
**Authority:** CrownThrive/CHLOM; no component may manufacture authority.

## Purpose

The Penta Resilience Suite is CrownThrive's closed-loop resilience, adversarial-assurance, hardening, snapshot, and recovery family. It converts controlled failure exercises into evidence-backed hardening without exposing production systems to offensive tooling.

The canonical loop is:

`PentaSnapshot -> PentaHoneyPot clone -> PentaRed simulation -> PentaBlue detection/containment -> PentaLiency hardening plan -> approved apply -> health gate -> PentaRollback when required`

## Components

| Component | Role | Portal |
|---|---|---|
| PentaLiency™ | resilience engineering, risk reduction, hardening-plan authority, health-gated apply | `/io/pentas/liency` |
| PentaBlue™ | defensive detection, containment, restore validation, control effectiveness | `/io/pentas/blue` |
| PentaRed™ | sandbox-only adversarial simulation against an authorized PentaHoneyPot clone | `/io/pentas/red` |
| PentaHoneyPot™ | ephemeral OS-clone range, duel orchestration, range proof, teardown | `/io/pentas/honeypot` |
| PentaSnapshot™ | evidence-backed SHA-256 filesystem snapshots and manifests | `/io/pentas/snapshot` |
| PentaRollback™ | approved restore primitive, staging verification, recovery health gates | `/io/pentas/rollback` |

`PentaSnapShot` is accepted as a spelling alias in human input. The canonical institutional mark and software identifier is **PentaSnapshot™**.

## Non-negotiable security boundary

PentaRed has no production-target primitive and no arbitrary host/network target interface. It is intentionally constrained to local deterministic simulation scenarios inside a PentaHoneyPot clone bearing a valid, short-lived RangeLease. Attempts to target the source tree, leave the range root, use a stale lease, cross a symlink boundary, or invoke an unapproved scenario fail closed.

The v1 simulation catalog covers configuration tampering, privilege drift, secret-canary exposure, service degradation, and integrity tampering. These are filesystem-local simulations; they are not exploit payloads, malware, scanning, credential theft, persistence, phishing, C2, or remote execution.

## PentaHoneyPot duel lifecycle

1. Compute the SHA-256 evidence manifest for the selected source tree.
2. Copy the tree to an ephemeral range.
3. Create the range marker and deterministic lab fixtures.
4. PentaSnapshot captures the clone baseline.
5. RangePolicy issues a short-lived RangeLease bound to the clone and source digest.
6. PentaRed executes only allowlisted simulated tamper events.
7. PentaBlue detects each mutation, contains it, and restores the clone from the baseline.
8. The clone digest must return to the baseline digest.
9. The original source digest is recomputed and must equal the pre-drill digest.
10. The range lease is revoked and the ephemeral clone is destroyed.
11. A tamper-evident DrillReport is emitted to PentaLiency.

## PentaLiency hardening contract

PentaLiency consumes only verified drill reports where the real source tree remained unchanged. It maps findings into named CrownThrive resilience controls and produces a priority-ordered HardeningPlan. Planning is dry-run by default.

Applying a plan requires an `approved_change_id`. Before mutation, PentaSnapshot captures the target. The current v1 writer only creates governed control-policy artifacts under `.penta-hardening/controls`; it does not accept arbitrary shell commands or arbitrary patch payloads. A post-change health gate runs immediately. If the gate fails, PentaRollback restores the pre-change snapshot.

## Recovery semantics

PentaRollback verifies the snapshot digest, stages restoration, verifies the staged digest, atomically swaps the target where the filesystem permits it, evaluates the recovery health check, and retains the prior target until the health gate succeeds. Missing change authority or failed snapshot verification stops recovery before mutation.

## Status and evidence

Each drill produces IDs for range, events, detections, findings, plan, snapshots, actions, and rollback. The runtime includes a machine-readable PentaStatus adapter. PentaStatus should aggregate at minimum: latest drill time, source-immutability proof, clone-restoration proof, open critical/high findings, hardening plan age, pending approved changes, last snapshot verification, last rollback result, and control drift.

PentaScribe should maintain glossary/mark/index entries; PentaDocs owns this operating guide; PentaSecure consumes defensive findings; PentaCertify certifies execution paths; PentaNurture tracks control health; PentaPR/PentaMerge govern code changes; PentaRelease versions shipped resilience software; PentaTime schedules recurring drills; PentaMail may deliver owner reports but does not own status truth.

## CLI

From repository root:

```bash
python -m penta.runtime.resilience drill ./path-to-tree
python -m penta.runtime.resilience plan ./path-to-tree
python -m penta.runtime.resilience harden ./path-to-tree --approved-change-id CHG-1234
```

The CLI deliberately contains no command for attacking a hostname, IP address, URL, provider account, or production endpoint.

## Operational contracts

### Inputs

- source filesystem tree selected for cloning;
- allowlisted simulation scenario identifiers;
- verified DrillReport for PentaLiency;
- approved change ID for hardening or rollback;
- optional health-check callback for recovery gates.

### Outputs

- SHA-256 tree evidence and SnapshotManifest;
- RangeLease and range lifecycle IDs;
- AttackEvent and Detection records;
- Finding records and HardeningPlan;
- governed hardening control artifacts;
- RollbackResult and PentaStatus-compatible readback.

### Dependencies

The baseline uses only the Python standard library. Provider-native database, deployment, object-storage, secret-store, VM/container, or cloud snapshots require separately certified adapters. Those adapters belong behind PentaBuild/PentaCertify/PentaCredentials/PentaNurture controls and may not be inferred as production-ready merely because the filesystem baseline passes.

### Access and permissions

- PentaRed: ephemeral range lease only; no production/network target surface.
- PentaBlue: range read/write for detection and containment; baseline snapshot read.
- PentaHoneyPot: source read, temporary-clone create/destroy, range lease issuance/revocation.
- PentaLiency: verified evidence read; governed hardening policy write only after approved change ID.
- PentaSnapshot: source read and governed snapshot-store write.
- PentaRollback: verified snapshot read plus target restore only with approved change ID.

### Incident and escalation

Any source-tree drift during a duel is a critical policy violation and aborts the run. Snapshot digest failure, range escape, stale range proof, symlink escape, unapproved scenario, or missing change authority fails closed. Failed post-hardening health checks invoke rollback. Persistent failures should route to PentaSecure/PentaTriage/PentaStatus and, where software remediation is required, PentaBuild/PentaCertify/PentaPR/PentaMerge.

## Assurance automation

`.github/workflows/penta-resilience-assurance.yml` compiles the package, executes the unit assurance suite, and runs a sandbox-only smoke drill. A scheduled/manual full-repository clone drill preserves its report as a GitHub Actions artifact for evidence review; the drill does not attack network endpoints or mutate the checked-out source tree.

## Production-readiness gates

- unit tests pass;
- PentaRed source-target rejection passes;
- original tree digest remains unchanged after every drill;
- clone returns to baseline digest after Blue containment;
- snapshot verification passes before rollback;
- hardening requires approved change ID;
- failed hardening health gate triggers rollback;
- PentaStatus readback is available;
- provider-specific snapshot/restore adapters require PentaBuild + PentaCertify certification before production eligibility.

## Versioning

This document and the software package begin at `1.0.0`. Provider-native recovery is an extension surface, not assumed by this filesystem baseline.
