# Penta Proprietary Software Enforcement

**Phase:** Phase 3 — Production + Convergence  
**Owner:** CrownThrive LLC  
**Operating owners:** PentaLegal, PentaPolicy, PentaScribe, PentaAssure, PentaSerialized, PentaRelease  
**Authority invariant:** software may enforce declared repository policy; it does not manufacture legal rights or legal conclusions.

## Purpose

CrownThrive already publishes a root proprietary rights notice in `LICENSE`. This control converts that declared repository posture into executable, repeatable software assurance so release packaging, first-party source, continuity receipts and institutional documentation cannot silently drift away from the declared policy.

This is a technical control layer, not a substitute for counsel, registrations, assignments, contributor agreements, chain-of-title work, contracts, third-party license review or applicable law. A PASS means the machine checks defined in `data/penta/proprietary-software-policy.json` passed for the tested tree. It does not mean every conceivable intellectual-property issue has been adjudicated.

## Penta responsibility split

- **PentaLegal** owns legal-operations routing and preserves the distinction between technical policy checks and legal determinations.
- **PentaPolicy** owns the executable policy contract and fail-closed behavior.
- **PentaScribe** keeps canonical names, notices, terms and source-of-truth references consistent.
- **PentaAssure** runs independent exact-head checks and emits PASS/HOLD evidence.
- **PentaSerialized** preserves deterministic receipts and makes silent replacement/deletion detectable.
- **PentaRelease** refuses prohibited secret/vault/private-key material and requires governed release artifacts plus provider readback.
- **PentaDocs/PentaGeneration** preserve the current rule and its lineage without turning historical policy into current authority.

## Enforced controls

`python scripts/penta_proprietary_gate.py --root .` performs four bounded classes of checks:

1. **Root rights-notice continuity.** Required strings from the current CrownThrive repository notice must remain present. A missing or materially displaced required declaration produces HOLD.
2. **First-party SPDX conflict detection.** CrownThrive protected first-party source roots are scanned for explicit `SPDX-License-Identifier:` declarations that contradict the repository's proprietary default. Third-party allowlisted roots are excluded so valid third-party licenses are not rewritten or appropriated.
3. **Release path safety.** When a release root is supplied, `.env`, secret, credential, vault, private-key and protected key-file paths are blocked.
4. **Release content safety.** High-signal private-key/token patterns are blocked from governed release material.

The gate produces a deterministic SHA-256 receipt containing the policy identifier, status, check results, scan counts, violations and optional release-tree digest. HOLD exits non-zero.

## Third-party boundary

Third-party material remains governed by its own applicable license and terms. This control must never relabel third-party code as CrownThrive proprietary material merely because it is present in the repository. Separately licensed first-party packages likewise remain governed by their explicit package/file license to the stated extent.

The control therefore looks for **explicit conflicting SPDX declarations only in first-party protected roots** and supports third-party allowlist roots. It does not infer ownership from a filename or silently strip external notices.

## PentaRelease integration

A CrownThrive OS release must preserve two independent conditions:

- the source tree passes proprietary assurance; and
- the materialized release package passes the PentaRelease secret/vault exclusion and provider readback gates.

A version number, tag, successful build or published GitHub release never turns a HOLD into PASS. Release packaging also must not include the Penta continuity vault. Vaulted AARs, governance receipts and restricted continuity material are preserved outside the public release artifact set.

## Phase 3 closeout rule

The Phase 3 major closeout release may be authorized only through an explicit bounded human release-authority record consumed by PentaRelease. That record authorizes the release decision for the named version and scope; it does **not** grant unrelated D3 authority, provider permissions, money movement, rights transfers, legal conclusions, security overrides or production maturity to child Pentas.

Phase 3 closeout must preserve outstanding PRs as one of three evidence-backed dispositions: merged/passed, closed/superseded with preserved lineage, or HOLD carry-forward. No stale, missing or failing exact-head evidence may be described as complete merely to obtain the major release.

## Source of truth

- `LICENSE`
- `data/penta/proprietary-software-policy.json`
- `scripts/penta_proprietary_gate.py`
- `tests/test_penta_proprietary_gate.py`
- `.github/workflows/penta-proprietary-assurance.yml`
- `.pentarelease/policy.json`
- `scripts/pentarelease/decide.py`
- `PENTARELEASE.md`

The governing principle remains: **technical ability is not permission, and software enforcement does not manufacture authority.**
