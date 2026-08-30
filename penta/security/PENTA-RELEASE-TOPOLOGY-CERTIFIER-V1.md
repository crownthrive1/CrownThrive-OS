# PentaCertifier mandatory release topology v1

Status: source candidate, fail-closed. This contract creates no production certification or authority.

The canonical release order is: **Build -> security scan -> threat model -> tests -> PentaSecurity decision -> CHLOM authority/rights decision -> applicable CIE decision -> independent PentaCertifier readback -> release execution -> exact outcome readback**. Every receipt must bind the exact release commit and carry evidence integrity. Originators/build producers cannot act as PentaSecurity, CHLOM authority, applicable CIE, or PentaCertifier decision authority for their own release. PentaCertifier cannot execute the release it certifies.

The verifier has two explicit phases and MUST NOT collapse them:

- `pre_release`: verifies the complete evidence/decision chain through independent PentaCertifier and returns `PRE_RELEASE_ELIGIBLE` only when release execution has not yet occurred. This is the only phase suitable for a terminal merge/release eligibility gate.
- `post_release`: re-verifies the complete exact-head pre-release chain, then requires the independent release execution receipt and returns `POST_RELEASE_VERIFIED` only when execution is proven. It is outcome readback, not merge authority.

This split is required because a certifier that requires the release execution receipt before declaring eligibility would invert the mandated topology and could never serve as a correct pre-release enforcement boundary.

DAIL Human, DAIL Hybrid, and DAIL Machine remain the canonical lane projections over the single CHLOM DAIL chronology. `evidence`, `decision`, and `execution` in this contract are semantic stages only. They are not CHLOM token classes, and this contract deliberately fails closed if a caller attempts to use them as a token model. The current CHLOM token model remains unresolved until authoritative CHLOM source/runtime evidence proves otherwise.

The verifier is evidence-only. It does not create rights, licenses, credentials, keys, provider writes, money movement, sovereign votes, final legal commitments, D3 authority, or external certification claims. D3 remains human-reserved and requires the existing exact D3 approval evaluator. CHLOM authority decisions must explicitly show `rights_check=PASS`, `authority_check=PASS`, `authority_expansion=false`, and `final_legal_or_rights_commitment=false` for ordinary software releases.

Current production readback also establishes that the existing `penta-release-evidence-oidc` service is a bounded GitHub OIDC projection path for PentaRelease economic/CIE evidence; it is not a substitute for the full exact-head PentaSecurity + CHLOM + applicable CIE + independent PentaCertifier chain. It must be reused where applicable, not relabeled as independent release certification.

This source slice extends the existing CrownThrive certifier implementation; it is not a new Penta identity. It is intended to become the deterministic readback core used by the governed release path after independent certification of this implementation itself. Until the provider-enforced terminal path consumes authentic exact-head receipts for every required decision and certification boundary, the current provider release-authority defect remains HOLD.

Rollback boundary: exact pre-change main commit `0659a653ac96d828f0921917abd74bd3e1005179`. No production database migration, provider-rules mutation, credential change, or release mutation is included in this source candidate.
