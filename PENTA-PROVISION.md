# PentaProvision™

PentaProvision is CrownThrive OS's fail-closed, on-demand dependency provisioner.

## Why it exists

A governed release or Penta may discover that an artifact, evidence packet, migration, receipt, schema, or other declared dependency is missing from its current execution surface even though an authoritative copy is preserved elsewhere in the governed repository lineage. Repeating that recovery manually is error-prone and creates avoidable release latency.

PentaProvision converts that recurring problem into software.

## Contract

`ct.penta.provision.v1`

PentaProvision accepts a committed request manifest containing an explicit destination path, authoritative source ref/path, and expected Git blob SHA. It verifies the source bytes against the expected SHA before staging anything. Existing destinations must already match the expected blob exactly or the operation fails closed.

PentaProvision may restore declared missing artifacts and emit receipts. It may not infer authority, invent evidence, guess source refs, overwrite mismatched content, force-push, or turn a governance HOLD into PASS. The requesting gate must rerun independently after provisioning.

## Invocation

```bash
python -m penta.runtime.provision \
  penta/provision/requests/<request>.json \
  --repo . \
  --allow-fetch \
  --apply \
  --receipt artifacts/penta-provision/<request>.receipt.json
```

Use `--apply` only after a dry-run succeeds. `--allow-fetch` permits fetching only the source ref already named in the committed request.

## Production wiring

- PentaHelp/PentaRelease/PentaFactory can raise a missing-dependency request.
- PentaProvision resolves declared authoritative source material.
- PentaSerialized/PentaResults preserve the provision receipt and hashes.
- PentaRelease reruns the exact gate that originally failed.
- Any remaining provider-state or D3 decision remains independently gated.

## Initial production proof

`ct.penta.provision.phase3-baseline-recovery.20260827.v1` restores the four exact historical migrations reported missing by the Governed Merge Gate on PentaFactory replenishment release 1.2.1. Those artifacts are recovered by preserved Git blob identity, not recreated from memory.
