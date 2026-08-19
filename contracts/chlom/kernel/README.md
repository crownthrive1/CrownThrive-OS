# CHLOM Kernel & Contract — Phase 2.99 Reference Contract

**Stable packet:** `ct.packet.chlom.cell.kernel.contract-v1`  
**Request contract:** `ct.contract.chlom.kernel.request.v1`  
**Decision contract:** `ct.contract.chlom.kernel.decision.v1`  
**State:** Phase 2.99 prototype semantic oracle, not a production service.

This Cell 01 packet defines the provider-independent contract that later policy, authority, evidence, rights, economics, API/MCP and community-engine adapters must preserve. It does not grant a provider institutional authority and it never executes a provider mutation.

## Contract boundary

The strict v1 request requires a stable request, correlation and idempotency identity; authenticated actor and organization identity; resource identity, organization and observed version; risk class; explicit `execution_mode`; expected resource version; authority/approval reference arrays; and documentation-impact metadata.

The reference engine remains fail closed:

- missing or malformed v1 contract fields raise a contract error;
- unauthenticated actors are denied;
- cross-organization requests are denied;
- any execution mode other than `decision_only` is denied;
- optimistic version mismatch is held;
- D3 never becomes autonomous allow;
- required approvals remain holds until evidence is supplied;
- authority references are transport/evidence references, not self-proving authority;
- identical retries under one idempotency key reuse the prior decision and DAIL event;
- reusing an idempotency key for a different payload fails closed.

Legacy prototype requests without a contract ID remain temporarily readable by the parent reference tests as `ct.contract.chlom.kernel.request.legacy-v0`. That compatibility path is lineage only; all new Cell 01 fixtures use strict v1.

## DAIL and docs impact

Every non-replayed reference decision emits `ct.chlom.reference.decision.v1` into the existing append-oriented SHA-256 DAIL chain with request/decision contract identity, correlation/idempotency identity, actor/org/resource identity, concurrency versions, authority references, policy result, required approvals, risk class and docs impact.

This contract page and the machine schemas are governed documentation inputs. **Free-form Markdown does not execute as CHLOM policy.**

## Validation fixtures

`conformance.v1.json` and `test_kernel_contract.py` cover positive and fail-closed behavior, including missing idempotency identity, cross-org access, provider-mutation intent, version conflict, D3 hold, safe idempotent retry and conflicting idempotency-key reuse.

Existing PR #67 reference-runtime tests must remain green. The child packet must also run its Cell 01 contract test directly.

## Specialist and authority boundary

Required review for later promotion: `security_privacy` and `ai_ml_llm_tevv`. This packet is D0/D1-buildable reference code but any material D2 promotion follows CT-ADR-GOV-011. D3 remains human/qualified-professional authority.

No OPA, OpenFGA, Cedar or Temporal component is adopted by this packet. They remain evaluation candidates until their independent intake and compatibility gates pass.

## Rollback and integration handoff

Rollback is a revert of the bounded Cell 01 child PR; no provider state or data migration exists to reverse.

Integration sequence after Cell 01 is accepted for reference use: pair the kernel contract with Cell 04 Evidence/DAIL, then integrate Cell 02 Policy and Cell 03 Authority under an Agent A integration packet. Parent PR #67 remains promotion-held behind PR #64 and PR #65 governance/security reconciliation.
