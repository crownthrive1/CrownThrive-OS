# PentaBooks Continuous Rotation Baseline v4

**Baseline ID:** PB-BASELINE-004  
**Effective:** 2026-09-04  
**Scope:** PentaBooks Rotation 003 Wave 002 Narrative Production and successor rotations; append-only backport controls apply to accepted prior packages.

## Purpose

PB-BASELINE-004 raises the minimum release contract for every independently licensable PentaBooks SKU. Production volume never substitutes for editorial, rights, custody, accessibility, provenance, or release evidence.

## Required independent product package

Each product package must carry its own consumable edition and editable source plus machine-readable release evidence. At minimum, the package contract includes:

- selling PDF and editable source
- EPUB3 and responsive web reader where format-appropriate
- product/landing-page copy and JSON-LD
- plain-text and Markdown representations
- metadata and governed cover/visual assets
- provenance record
- rights boundary
- accessibility rider
- consent/safety rider when applicable
- trade-secret boundary
- AI/model-use boundary; default deny unless an exact written grant exists
- PentaGreen candidate handoff
- release-test vectors
- content fingerprint
- QA record
- manifest and SHA-256 checksums

## Gates

A SKU does not become public or provider-activated because its content exists. The following predicates remain independent and fail closed:

1. content/package QA
2. rights and authority
3. exact package hash/fingerprint
4. Library custody and exact readback
5. Google Drive custody and exact readback
6. provider product/price activation
7. publication/reader readback
8. checkout, entitlement, delivery, expiration/recovery, refund/dispute canaries
9. public release projection

A successful upload is not a readback. For each required custody provider, the exact frozen package must be retrieved and its SHA-256, byte size, and ZIP integrity must match the authoritative package record.

## Trade-secret boundary

Public repositories, product packages, customer artifacts, Drive, and documentation may contain only non-secret metadata, stable references, fingerprints, rights boundaries, and approved aliases. Credentials, key material, private prompt grammar, unreleased internal scoring logic, protected personal data, and other secret-bearing values remain Vault-only. No secret value may be copied into this repository.

## Backport rule

Accepted prior package bytes are not rewritten merely to satisfy a newer control baseline. Where the accepted package is intact and its authoritative hash verifies, new controls are attached as append-only sidecars. A missing payload remains an explicit recovery defect and is never converted into a synthetic PASS.

## Rotation 003 Wave 002 narrative application

Track `NARRATIVE_PRODUCTION_SLOTS_13_24` produced 12 independent packages under this baseline. Internal package QA passed and both required custody providers independently read back all 12 frozen ZIPs with exact SHA-256/byte equality and ZIP-integrity PASS. Provider activation and public release remain separate predicates and are not implied by this baseline.
