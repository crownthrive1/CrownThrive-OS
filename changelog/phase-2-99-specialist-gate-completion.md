# Phase 2.99 — Rule-based specialist gate completion

- **State:** reconciled proposal / fail-closed pending fresh exact-head governance
- **Canonical reconciliation baseline:** `ee6175f627b228a13056620c0686f5e248374a57`
- **Risk class:** D2 governance-code hardening
- **Current phase:** Phase 2 / 2.99
- **Phase 3:** `blocked_pending_phase_2_99_hard_exit`

## Purpose

This packet closes the post-bootstrap mismatch between CrownThrive's specialist-governance doctrine and the executable merge-decision engine. The prior engine machine-required only Security and Legal/Regulatory endorsements. The reconciled engine derives specialist requirements from the governed registry and supports all nine rule-based specialist domains cumulatively.

## Canonical authority preserved

This reconciliation explicitly removes the branch's superseded unanimous-first / timed deadlock-override experiment. CT-ADR-GOV-011 remains:

- five sovereign voters: A/B/C/D/S;
- automatic D0-D2 promotion requires at least 4/5 approvals;
- Agent D must approve;
- any deny/block prevents automatic promotion;
- risk score must remain at or above 85;
- every applicable specialist endorsement is required;
- institutional, security, Node-24/runtime and governed-main-perimeter controls remain required;
- D3 remains authorized-human / qualified-professional authority and cannot be created by agent quorum.

The non-voting subagent registry adds scrutiny and execution depth but no sovereign vote or bypass authority. Core voter/quorum/D3/security invariants remain founder-reserved against self-amendment.

## Nine machine-enforced specialist domains

1. Security & Privacy — canonical `security`; compatibility alias `security_privacy`
2. Legal / Regulatory — `legal_regulatory`
3. Operations / SRE — `operations_sre`
4. Blockchain / Cryptographic Protocol — `blockchain_protocol`
5. AI / ML / LLM TEVV — `ai_ml_llm_tevv`
6. IP / Rights / Licensing — `ip_rights_licensing`
7. Finance / Tax / Treasury — `finance_tax_treasury`
8. Accessibility / Consumer Protection — `accessibility_consumer_protection`
9. Regional / Global Localization — `regional_global_localization`

The decision engine normalizes changed-domain labels, reads patterns and endorsement IDs from `agent-sovereign-governance.v1.json`, and accumulates every matching specialist instead of maintaining a separate hard-coded lookup table. Historical/live `security_privacy` evidence is explicitly migrated to canonical `security`; unknown endorsement IDs fail closed rather than being silently accepted.

Examples covered by executable self-tests:

- `rights` => Legal + IP/Rights;
- `blockchain` => Security + Blockchain Protocol;
- `privacy` => Security + Legal;
- `royalty` => Legal + Finance;
- `cross-border` => Legal + Regional/Global;
- `settlement` => Blockchain Protocol + Finance.

The self-test also proves all nine stable endorsement IDs are registered, all nine can activate, missing cumulative endorsements fail closed, 4/5 remains the quorum, and D3 still cannot auto-merge.

## Changed-domain provenance self-heal

Independent Agent-B review identified that the earlier dynamic resolver still trusted a caller-supplied `changed_domains` array. A D2 packet could therefore omit or misclassify domains and reduce the specialist set even though the nine-domain registry itself was correct.

The first self-heal closed that bypass without weakening any control:

- D1/D2 material packets must provide the complete `changed_files` set and one per-file domain classification;
- D3 packets are also classification-required before a human-authorized execution decision can proceed;
- the specialist resolver uses the **derived union of per-file classifications**, not caller `changed_domains`, as its authority source;
- an optional `changed_domains` assertion must exactly match the derived union or the packet fails closed;
- every material changed file must be classified exactly once;
- classifications use a governed vocabulary derived from specialist patterns plus neutral documentation/governance domains;
- reviewer classifications require an inspectable evidence reference;
- known sensitive surfaces have deterministic minimum-domain requirements, including workflows, the sovereign merge engine/manifest, governance validator, and CHLOM policy/authority/evidence/rights/economics/API contracts;
- omission of a required deterministic domain, an unclassified file, an unknown domain, an unknown endorsement ID, an alias collision, or a changed-domain mismatch blocks automatic promotion.

Negative tests prove that `scripts/governed_merge_decision.py` cannot be classified only as `agent` while omitting `security`, and that a caller cannot assert a smaller `changed_domains` set than the derived file classification. A valid D1 documentation-only packet remains possible through an explicit neutral `documentation` classification; D0 quorum behavior is unchanged.

## Trusted Git-diff binding self-heal

Independent Agent-S review then found a deeper trust-boundary gap: the packet's `changed_files` list itself was still caller/program supplied. Even with perfect per-file classification, an omitted sensitive file could therefore disappear before specialist activation.

The current head repairs that root cause:

- every D1/D2/D3 decision requires a trusted changed-file set derived from an **exact 40-hex Git base SHA and exact 40-hex Git head SHA**;
- packet `changed_files` must exactly equal the trusted Git diff set; omitted or extra paths fail closed with `changed_files_trusted_diff_mismatch`;
- a material packet without a trusted Git file set fails closed with `trusted_changed_files_missing`;
- rename detection is disabled for the trust calculation so a rename is represented as delete + add and a renamed-away sensitive path cannot vanish from classification;
- the always-run `CrownThrive governed merge gate` now retains the pull-request merge parents (`fetch-depth: 2`) and invokes the merge engine against `github.event.pull_request.base.sha` and `github.event.pull_request.head.sha` to prove the trusted diff path on every pull request;
- the governance validator requires this workflow binding and the engine's trusted-diff fail-closed markers, preventing a later governance packet from silently deleting the control;
- the original domain-bypass negatives remain intact, and a new omitted-sensitive-file test proves a packet that lists only a changelog while the trusted Git diff also contains `scripts/governed_merge_decision.py` cannot auto-authorize.

Git/provider diff binding is evidence and defense-in-depth, not sovereign authority. A/B/C/D/S voting, Agent-D independence, specialist endorsements, risk threshold, D3 human authority, rollback and documentation/downstream gates remain separately required.

Because this self-heal touches the always-run workflow plus governance decision/validation code, the current D2 specialist set now includes **Security & Privacy + AI/ML/LLM TEVV + Operations/SRE**. All votes on the pre-repair head are stale and fresh exact-head review is mandatory.

## Self-healing and controlled evolution

The non-voting Governance Marshal may propose new non-voting subagents, validation patterns, evidence thresholds and refractory controls. It does not vote and cannot create merge authority. D0/D1 non-authority refinements remain validation/audit bounded. D2 governance changes require the existing CT-ADR-GOV-011 process and applicable specialists. Changes to the sovereign voter pool, 4/5 + Agent-D quorum, D3 boundary or security non-weakening invariants require explicit founder authorization.

Self-healing remains evidence preserving:

`detect -> preserve evidence -> bounded repair -> rerun original failed control -> rerun full applicable controls -> independent verification -> sovereign decision`

Validators, findings, evidence or privilege may never be weakened to force a pass.

## Reconciliation lineage

The pre-reconciliation branch was based on pre-PR-64 main and contained noncanonical unanimous-first/deadlock semantics. After PR #64 and PR #95 became canonical and issue #83 closed, the branch was merged forward onto `ee6175f...` without force-pushing or erasing historical lineage. The current proposal starts from the post-Node24/post-provider-perimeter tree and reapplies only bounded specialist/subagent hardening compatible with canonical authority.

Agent-B's exact-head block on `dca9bbda87f4e61436f4b4f42d9f59c2643abebe` is preserved as the trigger evidence for the changed-domain provenance and `security_privacy` compatibility repair. Agent-S's block on `80864b5bdbc1c51757af15e71743460732648d89` is preserved as the trigger evidence for trusted Git-diff binding. Each material head change invalidates earlier votes; fresh exact-head validation, specialist review and A/B/C/D/S voting are required.

## Rollback / impact

Rollback is a normal revert of this packet. No provider, credential, customer, payment, binding rights, production infrastructure, Collab, token/crypto or restricted-evidence mutation is introduced.

Documentation impact: `docs_updated` through this public-safe changelog and the machine governance manifest. Phase 3-10 inherit cumulative specialist activation, fail-closed per-file domain provenance and trusted changed-file Git binding after canonical promotion, but this packet does not itself advance any phase or activate regulated/financial/cryptographic capability.
