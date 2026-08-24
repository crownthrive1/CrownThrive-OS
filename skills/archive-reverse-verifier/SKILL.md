# Archive Reverse Verifier Skill v1.2

## Identity

- Agent: `ct.agent.archive-reverse-verifier`
- Suite: `ct.skill-suite.archive-custody.v1`
- Capability: `ct.capability.archive-reverse.verify.v1`
- Runtime wrapper: `chlom_runtime.archive_reverse_verify_contract_v1`
- Protected verifier: `chlom_runtime.archive_reverse_verify_algorithm_v1`
- State: controlled-test
- Authority ceiling: D2

## Executability gate

Registration and a privilege profile are not enough to decrypt or reverse an archive member. Every verification requires the existing founder-granted standing authorization and a separate exact-resource, sensitivity-bounded, short-lived authority lease. The protected verifier independently rechecks that lease on every call.

## Bounded operation

The executable wrapper may verify one exact archived algorithm member at a time. It verifies stored ciphertext SHA-256, decrypts only the bounded containing chunk inside the protected runtime, verifies the plaintext SHA-256, finds the exact member, compares its recovered public-contract digest to canonical registry truth, and appends restricted evidence receipts.

## Hard prohibitions

Secret-body return is false. Key-material return is false. Bulk decryption, credential export, founder-root bypass, self-authorization, self-release, provider writes, money movement, rights grants, voting and D3 actions are prohibited.

The v21 controlled-test canary verified `ct.alg.chlom.aie-anomaly-ensemble` with matching ciphertext hash, plaintext hash, membership and canonical contract digest. No secret body or key material was returned. That proves bounded recoverability for that member only.
