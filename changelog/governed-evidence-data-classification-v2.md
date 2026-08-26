# Governed evidence-data classification v2

Date: 2026-08-26
Issue: #121

This change repairs two bounded current-PR governance classifier defects without weakening conservative fallback behavior.

1. The four registered Help Center title/hierarchy evidence transport files are classified through an exact-path contract as `institutional_general` rather than receiving the generic nine-domain fallback.
2. Neutral-only D2 documentation/evidence remains valid only when every derived domain is explicitly registered neutral.
3. Representative payment/royalty, token/wallet, license/rights, customer/privacy, and localization/country data paths are tested as material and cannot inherit neutral treatment.
4. Every unknown `data/` path retains the conservative nine-domain fallback.
5. Extension/name spoofing cannot inherit neutral classification; exact registered path identity is mandatory.
6. Trusted Git diff binding, per-file classification completeness, omitted-file failure, missing-specialist failure, sovereign quorum semantics, mandatory Agent D, and permanent `auto_merge_authorized=false` CI authority block remain unchanged.

The new contract and v2 preflight are inert until the governed merge workflow is explicitly switched to consume them through a reviewed activation packet.
