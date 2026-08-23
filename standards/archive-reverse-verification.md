# Archive Reverse & Decryption Verification Standard

## Status
CONTROLLED_TEST / RESTRICTED.

## Purpose
Provide a bounded, independently auditable reversibility check for CrownThrive encrypted institutional archives without turning decryption capability into a general-purpose secret-export surface.

## Canonical agent
`ct.agent.archive-reverse-verifier`

The agent is A1 / D2, non-voting, no-self-approval, unscheduled, and callable only through an authorization record for the Founder or an explicitly Founder-granted special agent.

## Required sequence
1. Resolve the requested member from frozen archive membership.
2. Resolve the single committed ciphertext chunk containing that member.
3. Verify the stored ciphertext SHA-256 before decryption.
4. Resolve the archive key by alias through the existing Supabase Vault path; never copy key material into agent assets.
5. Decrypt only the bounded chunk in transaction memory.
6. Recompute and compare the plaintext SHA-256.
7. Extract only the requested member.
8. Compare the recovered public contract digest against the canonical registry digest.
9. Persist only hashes, identifiers, disposition, authorization identity, and evidence. Do not persist decrypted plaintext.
10. Append a restricted DAIL event.

## Authorization boundary
The authorized entrypoint is service-role-only at the database ACL. It additionally checks `chlom_runtime.archive_reverse_authorizations` on every invocation. Agent grants must be explicitly Founder-granted. Revoked, suspended, expired, unknown, or ungranted principals fail closed.

The internal decryptor is not an end-user API and is also denied to `anon` and `authenticated`.

## Prohibitions
No bulk decryption, secret-body return, credential export, plaintext persistence, automatic schedule, provider write, money movement, rights grant, vote, D3 action, self-authorization, or self-certification.

## Controlled-test proof
On 2026-08-23 the Founder-authorized procedure reversed algorithm member `ct.alg.factory.g43.rewards_loyalty.causal_forecaster.risk.v1` from archive v21 algorithm chunk 38, ordinal 37341. Ciphertext and plaintext hashes verified, the member was recovered, and recovered/canonical contract digests matched exactly. Receipt: `ae1bfb5f-4a38-4e07-99b7-a2b449c6aa7e`. No secret body was returned.

## Custody
Runtime authorization and receipts are private THRIVEBASE state. Cryptographic key custody remains with the pre-existing Vault-backed archive key alias; this agent receives no duplicate key. The source manifest and documentation require normal CrownThrive Drive/Supabase Storage custody projection after governed canonicalization and must not be represented as completed until readback exists.
