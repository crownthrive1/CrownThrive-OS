# Penta Flow-Control Independent Certification

## Scope

Campaign: `ct.penta.flow-control.20260826.v1`

Release candidate: `crownthrive1/CrownThrive-OS@618fc84a503152d5075019272789c9694974e11a`

## Required certification evidence

Certification is fail-closed and requires all of the following for the exact campaign and exact release commit:

1. Independent verifier receipt with a distinct verifier identity.
2. Receipt decision of `PASS`.
3. Runtime readback proving the provider adapter is disabled and no provider jobs were released.
4. Binding readback proving concurrency `4`, claim batch `8`, paid cost ceiling `0`, internal-unit ceiling `1,000,000`, and all provider-write, money-movement, rights-disposition, and credential authorities are `false`.
5. Rollback evidence containing a baseline, an explicit rollback test, pre-rollback readback, post-rollback readback, and proof that post-rollback state matches the baseline.

## Current state

The live campaign binding has been read back from Supabase with the required bounded values and all four authority flags false. The release candidate is the exact PentaPR 2.0.3 commit above.

The independent verifier receipt is not present in the live evidence set, and the runtime release-baseline and activation-receipt tables currently contain no campaign certification record. Therefore the campaign is **NOT CERTIFIED** and must remain contained.

## Software gate

`scripts/penta_flow_control_certifier.py` implements the deterministic gate. It emits `CERTIFIED` only when every required check passes. Missing or mismatched independent evidence produces `NOT_CERTIFIED` and a non-zero exit code.

`tests/test_penta_flow_control_certifier.py` covers the positive path and fail-closed cases for missing independence, self-verification, adapter enablement, incomplete rollback, and CLI failure behavior.

## Authority boundary

This software verifies evidence. It does not create an independent receipt, enable provider execution, release provider jobs, or grant authority. An independent verifier must supply the receipt after performing the required external verification and rollback/readback exercise.

## Persistent hand-raise successor

`docs/phase3/PENTA_HOLD_HAND.md` defines the additive PentaHoldHand/PentaCrawler/PentaHelp contract. A HOLD remains visibly raised while those systems discover and route missing evidence. They may make a resolution receipt eligible only after every exact-head independent predicate passes; they do not self-certify or delete the historical HOLD.

The successor `ct.penta.agentic.hold-governance.v1` routes each raised hand through DISCOVER, GOVERN, EXECUTE, VERIFY, and PRESERVE receipts from active Penta agents. It prospectively supersedes the legacy A/B/C/D/S scheduler topology for HOLD resolution while retaining all historical records. The originator cannot approve itself, VERIFY remains independent, D3 remains bound to active founder authority, and agentic approval alone has no certification or runtime-activation effect.
