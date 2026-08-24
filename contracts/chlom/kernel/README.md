# CHLOM Kernel & Contract — Phase 2.99 Reference Contract

**Stable packet:** `ct.packet.chlom.cell.kernel.contract-v1`  
**Request contract:** `ct.contract.chlom.kernel.request.v1`  
**Decision contract:** `ct.contract.chlom.kernel.decision.v1`  
**State:** Phase 2.99 prototype semantic oracle, not a production service.

This Cell 01 packet defines the provider-independent contract that later policy, authority, evidence, rights, economics, API/MCP and community-engine adapters must preserve. It does not grant a provider institutional authority and it never executes a provider mutation.

## Contract boundary

The strict v1 request requires a stable request, correlation and idempotency identity; authenticated actor and organization identity; resource identity, organization and observed version; risk class; explicit `execution_mode`; expected resource version; authority/approval claim arrays; and documentation-impact metadata.

The reference engine remains fail closed:

- missing or malformed v1 contract fields raise a contract error;
- omitting both `contract_id` and `contract_version` no longer downgrades an untrusted request into legacy semantics;
- the only legacy path retained is the exact parent reference-test fixture, labeled `legacy-v0-test-only`, so historical unit-test lineage can remain green without creating a general runtime fallback;
- unauthenticated actors are denied;
- cross-organization requests are denied;
- any execution mode other than `decision_only` is denied;
- optimistic version mismatch is held;
- D3 never becomes autonomous allow;
- caller-provided `actor.roles`, `approval_evidence` and `authority_evidence` are claims/evidence, not authority;
- authority-sensitive strict-v1 allows require a separately supplied `VerifiedAuthorityContext` whose actor and organization match the request and which supplies verified roles, relationships, delegations and approvals;
- authority-sensitive decisions hold unless both verified relationship and delegation references exist;
- governed evidence references may be preserved, but free-form/non-governed authority evidence is persisted only as an opaque SHA-256 evidence digest and never verbatim;
- an identical idempotent retry reuses a prior strict-v1 decision only when both the request payload and normalized verified-authority context are semantically unchanged;
- removing or materially changing verified actor/org/roles/relationships/delegations/approvals/governed authority evidence under the same request and idempotency key fails closed instead of replaying a cached allow;
- reusing an idempotency key for a different request payload fails closed.

The authority-context idempotency binding covers all authority fields currently available to Cell 01. Authority version, expiry and revocation identity belong to Cell 03; those lifecycle fields must join the integrated authority fingerprint before any later production authority implementation can rely on cached decisions.

This contract deliberately leaves the future authority adapter/provider implementation to Cell 03. Cell 01 only defines the provider-independent trust boundary consumed by that future adapter.

## DAIL and docs impact

Every non-replayed reference decision emits `ct.chlom.reference.decision.v1` into the existing append-oriented SHA-256 DAIL chain with request/decision contract identity, correlation/idempotency identity, actor/org/resource identity, concurrency versions, sanitized authority evidence references/digests, whether authority context was independently verified, verified relationship/delegation references, verified approvals, policy result, required approvals, risk class and docs impact.

This closes the kernel side of the TEVV finding that caller-provided authority evidence could be persisted verbatim. Cell 04 still owns the broader versioned evidence/attestation/DAIL schema, correction, tamper, retention and export contract.

This contract page and the machine schemas are governed documentation inputs. **Free-form Markdown does not execute as CHLOM policy.**

## Validation fixtures

`conformance.v1.json` and `test_kernel_contract.py` cover positive and fail-closed behavior, including missing contract identity, missing idempotency identity, cross-org access, provider-mutation intent, version conflict, D3 hold, safe idempotent retry, conflicting idempotency-key reuse, caller self-asserted authority rejection, verified identity+org+relationship+delegation+approval requirements, authority-context removal/change across an identical idempotency replay, and non-verbatim restricted/free-form evidence persistence.

Existing PR #67 reference-runtime tests must remain green. The legacy behavior needed by those six parent tests is isolated to their exact `req_test` / `ct.actor.test` / `ct.resource.test` / `environment=test` / `reason=test_only` fixture and must not become an adapter/runtime compatibility promise.

The governed Cell-01 workflow integrated through PR #96 directly invokes `contracts/chlom/kernel/test_kernel_contract.py` in addition to the parent runtime suite. Any new Cell-01 head must rerun that unchanged direct suite. Cell 08 owns independent TEVV revalidation and must rerun the authority-context idempotency replay finding against this repaired head without weakening the prior HIGH vectors.

## Specialist and authority boundary

Required review for later promotion: `security_privacy`, `ai_ml_llm_tevv`, and `operations_sre`. This packet is D0/D1-buildable reference code but any material D2 promotion follows CT-ADR-GOV-011. D3 remains human/qualified-professional authority.

No OPA, OpenFGA, Cedar or Temporal component is adopted by this packet. They remain evaluation candidates until their independent intake and compatibility gates pass.

## Rollback and integration handoff

Rollback is a revert of the bounded Cell 01 child PR; no provider state or data migration exists to reverse.

The former #64 → GitHub-main-perimeter → #65 governance predecessor sequence is now canonical. Cell 01 and parent #67 remain on a historical CHLOM stack relative to current `main`, so canonical promotion still requires an Agent-A-owned parent/current-main integration packet after fresh Cell-01 Security/TEVV acceptance. Pair the accepted kernel with Cell 04 Evidence/DAIL without changing either cell's ownership. Then integrate Cell 02 Policy and Cell 03 Authority only under an Agent A cross-cell integration packet.
