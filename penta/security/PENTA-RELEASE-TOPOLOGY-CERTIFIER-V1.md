# PentaCertifier mandatory release topology v1

Status: source candidate, fail-closed. This contract creates no production certification or authority.

The canonical release order is: **Build -> security scan -> threat model -> tests -> PentaSecurity decision -> CHLOM authority/rights decision -> applicable CIE decision -> independent PentaCertifier readback -> release execution**. Every receipt must bind the exact release commit and carry evidence integrity. Originators/build producers cannot act as PentaSecurity, CHLOM authority, applicable CIE, or PentaCertifier decision authority for their own release. PentaCertifier cannot execute the release it certifies.

DAIL Human, DAIL Hybrid, and DAIL Machine remain the canonical lane projections over the single CHLOM DAIL chronology. `evidence`, `decision`, and `execution` in this contract are semantic stages only. They are not CHLOM token classes, and this contract deliberately fails closed if a caller attempts to use them as a token model. The current CHLOM token model remains unresolved until authoritative CHLOM source/runtime evidence proves otherwise.

The verifier is evidence-only. It does not create rights, licenses, credentials, keys, provider writes, money movement, sovereign votes, final legal commitments, D3 authority, or external certification claims. D3 remains human-reserved and requires the existing exact D3 approval evaluator. CHLOM authority decisions must explicitly show `rights_check=PASS`, `authority_check=PASS`, `authority_expansion=false`, and `final_legal_or_rights_commitment=false` for ordinary software releases.

This source slice extends the existing CrownThrive certifier implementation; it is not a new Penta identity. It is intended to become the deterministic readback core used by the governed release path after independent certification of this implementation itself. Until provider rules and the terminal merge path are wired to require its exact-head PASS, the current provider release-authority defect remains HOLD.

Rollback boundary: exact pre-change main commit `0659a653ac96d828f0921917abd74bd3e1005179`. No production database migration, provider-rules mutation, credential change, or release mutation is included in this source candidate.
