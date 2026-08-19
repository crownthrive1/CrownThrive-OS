# CHLOM Executable Build Program

**State:** Phase 2.99 prototype build active; Phase 3 production activation blocked.

CHLOM now uses a parallel cell model so implementation can advance piece-by-piece without allowing ten different builders to mutate the same contract at once. The cells are non-voting specialist work units; sovereign repository authority remains the A/B/C/D/S model from CT-ADR-GOV-011.

The ten cells are Kernel & Contract; Policy & dS-CaaS; Identity/Relationship/Authority; Evidence/Attestation/DAIL; Rights/DLA/Licensing; Economics/Splits/Remedies; API/MCP/Adapters; Security/TEVV/Resilience; Living Docs/SDK Contracts; and Open Source Intake/Upstream Stewardship.

Each cell owns a bounded file/contract surface. Cross-cell integration requires an orchestrated integration packet, current-main collision check, relevant specialist gates and normal D0-D3 authority. A cell cannot create another quorum vote, self-authorize D3, expose restricted evidence or convert a prototype into production by naming it complete.

## Executable-first sequence

1. Prove the CrownThrive semantic kernel and DAIL event chain locally.
2. Compile/version policy and authority contracts behind stable IDs.
3. Implement rights/DLA and approval/hold semantics.
4. Implement versioned economics/remedies without live money movement.
5. Add API/MCP interfaces and provider adapters.
6. Run TEVV, adversarial, replay, isolation, correction, backup and rollback tests.
7. Enter controlled Phase 3 activation only after the full Phase 2.99 hard exit.

The first reference runtime is intentionally standard-library Python and provider-independent. It makes the institutional contract executable before CrownThrive selects external runtime engines.

## Community/open-source rule

CrownThrive should reuse strong community software where it reduces risk or needless reinvention, but the upstream package never becomes CrownThrive institutional authority. The current evaluated candidates are Open Policy Agent for policy execution, OpenFGA for relationship authorization, Cedar as a formal policy-language compatibility candidate and Temporal for durable workflows. Their current repository license files were verified as Apache-2.0, Apache-2.0, Apache-2.0 and MIT respectively.

Adoption requires a pinned release/commit, license/notice handling, security/supply-chain review, data/privacy review, operational exit plan, compatibility tests, SBOM, documentation impact and normal CrownThrive governance. Prefer adapters over vendoring. Fork only where governed divergence is justified, preserve attribution/notices, and contribute generic fixes upstream when practical.

## Living documentation

Machine manifests describe cell state, upstream candidates and acceptance gates. `scripts/generate_chlom_living_status.py` renders a public-safe status projection from those manifests. The runtime never executes arbitrary prose as policy; governed docs point to versioned machine policy bundles that are validated before execution. This keeps the documentation living without turning Markdown into an unreviewed code-execution surface.
