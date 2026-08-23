---
title: Founder Master Recovery and Multi-Key Decryption Standard
description: CrownThrive institutional control for Founder break-glass recovery and one-to-five-key protected asset encryption.
---

# Founder Master Recovery and Multi-Key Decryption Standard

## Status

`CONTROLLED_TEST`

This standard governs the CrownThrive asset, archive, recovery, and registered institutional cryptographic estate. It does not grant universal access to provider passwords, third-party API tokens, provider credentials, or unrelated secrets.

## Canonical hierarchy

The hierarchy is `ct.crypto.keyring.founder.v1`.

The Founder break-glass recovery root is identified by `ct.key.founder.master-recovery.v1`. Its raw secret material is Vault-only and must never be written into GitHub, documentation, DAIL, logs, receipts, public surfaces, or ordinary agent output.

The institutional unlock ring contains ten independent key handles: `K01` through `K10`, with canonical IDs `ct.key.decrypt.k01.v1` through `ct.key.decrypt.k10.v1`. Raw material for every key remains Vault-only. Each unlock key also has a ciphertext escrow copy wrapped under the Founder recovery root.

## Sensitivity profiles

| Sensitivity | Required keys | Key slots |
| --- | ---: | --- |
| S1 | 1 | K01 |
| S2 | 2 | K02 + K03 |
| S3 | 3 | K04 + K05 + K06 |
| S4 | 4 | K07 + K08 + K09 + K10 |
| S5 | 5 | K01 + K03 + K05 + K07 + K09 |

Encryption is layered in profile order. Ordinary reversal requires all profile keys and decrypts them in reverse layer order. Missing, wrong, paused, expired, or unauthorized key access fails closed.

## Founder recovery

The Founder root is a key-encryption key, not a plaintext credential dump. It can unwrap ciphertext-escrowed CrownThrive crypto keys and use them inside bounded recovery functions. Root use requires a fresh Founder authorization record and is evidenced by a restricted receipt.

The root must not be handed to the Archive Reverse Verifier. That agent may use only the multi-key ring under explicit Founder grant and may not export raw key material.

## Access classes

`founder_master_decrypt` is Founder-only. `multi_key_decrypt` may be granted to the Founder or explicitly Founder-granted special agents. Every operation performs a fresh authorization lookup. No agent may self-authorize, self-expand scope, vote itself access, or substitute a generic service-role capability for the institutional authorization check.

`anon` and ordinary `authenticated` roles have no execute authority over the protected entrypoints. Internal raw-root and raw-unwrapped-key helpers are not executable even by the generic service role.

## Custody and ciphertext

Primary secret custody is Supabase Vault. Each of the ten unlock keys is separately encrypted at rest by Vault and additionally wrapped as ciphertext under the Founder root in `chlom_runtime.founder_crypto_key_escrow_v1`.

Safe legacy CrownThrive archive/recovery crypto aliases are progressively escrowed under the Founder root without changing their existing ciphertext. Provider credential aliases are explicitly excluded from reconciliation.

Key metadata assets are registered in `chlom_secrets.trade_secret_assets`; those asset records contain identifiers, digests, classification, and Vault references only, never raw key bytes.

## Runtime contracts

- `chlom_runtime.founder_crypto_encrypt_envelope_v1` creates one-to-five-layer encrypted institutional envelopes.
- `chlom_runtime.founder_crypto_decrypt_envelope_v1` performs authorized multi-key or Founder-root recovery with ciphertext and plaintext digest verification.
- `chlom_runtime.founder_crypto_reverse_verify_algorithm_v1` proves Founder-root recovery of existing archive ciphertext without returning the protected algorithm body.
- `chlom_runtime.archive_reverse_verify_algorithm_v1` remains the normal bounded reverse-verification path for the Archive Reverse Verifier.
- `chlom_runtime.reconcile_founder_crypto_escrow_v1` wraps eligible registered archive/recovery keys under the Founder root while excluding provider credentials.

## Evidence and invariants

The implementation has passed a five-key S5 encryption/decryption canary through the Archive Reverse Verifier and separately through the Founder root. The Founder root has also recovered the current archive key from ciphertext escrow and verified a pre-existing v21 algorithm archive member. The original reverse-verifier path passed a regression test afterward.

An unauthorized-agent canary was denied by the fresh authorization gate. Key material was not returned by any test.

The DAIL verification event is `88851375-8c2e-4a3d-bfad-1478c42d3fa6`. DAIL chain verification reported zero failures after institutionalization.

## Non-negotiable prohibitions

Raw key export, public key-value disclosure, provider credential recovery through the Founder root, plaintext persistence by the reverse agent, self-approval, D3 substitution, sovereign vote manufacture, money movement, provider writes, rights grants, and automatic mass decryption are prohibited.

The existence of a Founder break-glass path does not convert technical capability into automatic institutional authority. Every use remains attributable, bounded, checked, and evidenced.
