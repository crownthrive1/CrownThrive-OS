# Phase 2.99 Hard-Exit Closure Ledger

**Packet:** `ct.closure.phase-2-99.hard-exit.v1`  
**Issue:** #84  
**Observed canonical main:** `12f0dd9ab97391a8dd34438f77262438c0df0999`  
**Canonical roadmap:** `CT-ADR-ROADMAP-010 / ten_phase_v1`  
**Current institutional state:** Phase 2 / 2.99  
**Phase 3:** `blocked_pending_phase_2_99_hard_exit`

## Why this packet exists

The latest external Mintlify regrade correctly identifies that the remaining Phase 2 work is primarily closure, proof, certification and adversarial reconciliation rather than rediscovery of CrownThrive's documentation architecture.

One statement in that assessment is not adopted: the five-top-level-phase namespace. The current machine authority is `CT-ADR-ROADMAP-010 / ten_phase_v1`, with ten top-level phases. PR #62's five-phase machine snapshot is preserved only as superseded lineage. This packet converts the useful closure recommendations into machine state without reopening that resolved namespace decision.

This is a **closure ledger**, not a completion declaration. It deliberately validates that open blockers remain visible.

## What is already strong enough to stop treating as one undifferentiated gap

The four macro source/count universes are now independently recovered and must remain independent:

| Universe | Source count | Current closure state |
| --- | ---: | --- |
| Holdings portfolio rows | 68 | source count certified; identity reconciliation partial; 62 typed/classified and 6 identity items still pending |
| Holdings domain rows | 82 | source count certified; current registrar/DNS/TLS/runtime certification incomplete |
| Holdings engine/service rows | 85 | source count certified; current provider/account/version/deployment/API/export certification incomplete |
| Phase 2.7 platform/framework rows | 74 | source count certified; current canonical crosswalk partial; 54 typed/classified and 20 current identities unresolved |

These counts describe different source universes. A passing 68-row recovery never proves 82-domain, 85-engine or 74-platform completion, and none of those source counts proves current deployment.

The institutional dimension rule is also fixed:

`priority ≠ lifecycle ≠ implementation state ≠ institutional disposition`

A P0 item may be unverified or blocked. A public URL may exist while capabilities remain unverified. A sunset identity may still retain IP, source, domain, contract, evidence and continuity obligations.

## Closure ladder derived from the external 96/100 assessment

The numbers below are **non-authoritative progress thresholds**, not institutional phases, votes, approvals or hard-exit decisions.

### 97 — macro certification

Not met yet.

Source-count recovery for 68 / 82 / 85 / 74 is established, but final macro certification still requires the unresolved identity/current-state queues to reach accepted current, historical, research, reserve, blocked or explicit-deferral dispositions with no silent promotion.

In particular:

- six Holdings portfolio identity-resolution items remain;
- twenty S103 current identity items remain unresolved;
- current domain registrar/DNS/TLS/runtime evidence is incomplete;
- current engine/provider/account/version/deployment/API/export evidence is incomplete;
- source/claim population and retroactive reconciliation remain active until hard exit.

### 98 — articleization and P0/P1 closure

Not met yet.

The 795-title forensic source inventory is verified and the deterministic generator exists, but the current articleization record still says:

- complete machine manifest generated in repository: pending;
- P0/P1 disposition completion: pending;
- all 795 terminal dispositions: incomplete;
- all 795 section/category, exposure, risk, owner, route/nonpublic, source and navigation/unlisted mappings: incomplete.

P0/P1 required categories need substantive versioned bodies or explicit unresolved-source states. Fluent reconstruction is never a substitute for source authority.

### 99 — final adversarial reconciliation

Not met yet.

The final audit must reconcile, without hiding or averaging:

- contradiction records and retroactive corrections;
- `not_connected`, `unverified`, `blocked`, `source_not_recovered`, `owner_input_required` and equivalent unresolved states;
- final accepted deferrals and their owner/evidence/revisit conditions;
- restricted/private source boundaries;
- current provider/account/deployment state;
- security findings and specialist decisions;
- repository packet sequence/collisions and canonicalization;
- off-provider continuity, export, backup, restoration and reconstruction;
- no leaked secrets or private routing values;
- no historical/research capability promoted to current production.

### 100 — Phase 2.99 hard-exit certification

Not met.

Only the formal hard-exit evaluation can authorize:

`PHASE 2 — COMPLETE / INSTITUTIONALLY CERTIFIED`

and:

`PHASE 3 ENTRY GATE — OPEN`

A score, page count, CI pass, branch preview, individual workstream success or agent confidence cannot substitute.

## Current blocking sequence

### Repository/security governance

Canonical `main` remains the merged PR #63 baseline observed by this packet.

PR #64 is open and non-canonical. Its observed exact head is `7d8e11e90aa2c9675b9775095bd367e00eea5eaa`. Earlier head-bound approvals are stale. It currently owns the runtime/supply-chain and fail-closed main-perimeter bootstrap lane.

Issue #83 is the provider-admin activation gate that must not execute before the #64 substrate is canonical. If #64 is adopted, #83 then governs exact provider-side `main` protection/ruleset activation and verification.

PR #65 remains behind #64 and, if the #64/#83 sequence is adopted, must reconcile onto the resulting canonical state before fresh head-bound votes can count.

PR #66 / issue #79 preserve the unresolved `integration_control` RLS defense-in-depth finding. Current evidence does not prove anonymous/authenticated exposure, but the critical hardening disposition remains open. Any consequential production RLS/grant/policy mutation remains D3 human/qualified-security authority.

### CHLOM executable build lane

PR #67 and its cell PRs may continue as Phase 2.99 prototype/reference build work, but they are not permission to bypass unresolved repository/security sequencing. A prototype semantic oracle is not a production service.

### Collab Portal

Collab Portal remains fail-closed. All seven certification predicates have not passed simultaneously. The private fallback tracking route therefore remains active. No value from private routing or credential material belongs in this ledger.

## Final-deferral contract

Phase 2 does not require every external system to become connected or every historical body to be recovered. It does require every material unresolved item to terminate in an inspectable disposition.

An accepted deferral must include at least:

```yaml
deferral_id: ct.deferral.<stable-id>
subject_id: <stable institutional object>
current_state: not_connected | unverified | blocked | source_not_recovered | owner_input_required | other_explicit_state
why_unresolved: <evidence-based reason>
risk_class: D0 | D1 | D2 | D3
blocking_phase_2_99_exit: true | false
authority_for_nonblocking_deferral: <decision or approval reference>
evidence_refs: []
owner_or_queue: <stable role/queue>
revisit_trigger: <event/evidence/date>
continuity_or_fallback: <if applicable>
docs_impact: docs_updated | docs_no_change | docs_delta_opened
```

Missing evidence is never represented as permission. A deferral that materially affects safety, legal authority, security, rights, money, privacy, source integrity or institutional continuity cannot become nonblocking merely to reach a target score.

## Machine ledger

`developers/manifests/phase-2-99-hard-exit-ledger.v1.json` is the public-safe current closure checkpoint.

`scripts/validate_phase_2_99_hard_exit_ledger.py` validates the checkpoint fail-closed. Its PASS means **the ledger is coherent**, not that the hard exit has passed.

The validator rejects:

- replacement of the ten-phase roadmap with the superseded five-phase snapshot;
- collapse of the 68 / 82 / 85 / 74 count universes;
- false promotion of incomplete macro reconciliation;
- false completion of the 795-article estate;
- premature Phase 2 completion or Phase 3 opening;
- loss of the PR #64 → provider gate sequencing boundary;
- false closure of the RLS security disposition;
- false Collab Portal certification/fallback retirement;
- promotion of the external 97/98/99/100 assessment thresholds into institutional authority.

## Workflow integration boundary

This bounded packet does **not** modify `.github/workflows/**`, `developers/manifests/agent-sovereign-governance.v1.json`, or `scripts/validate_agent_sovereign_governance.py` because those surfaces are actively owned by PR #64/#65.

After that predecessor sequence is dispositioned, an Agent A integration packet may wire the closure validator into the always-run governed merge gate. Until then, repository CI validates this packet's ordinary documentation/security integrity while the closure validator is independently runnable and self-testing.

## Rollback

Rollback is a straight revert of the bounded #84 closure-ledger packet.

No provider configuration, database policy, credential, payment, rights grant, customer state, Collab mutation, CHLOM production service or Phase 9 crypto/token state is changed.

## Hard-exit decision rule

The final decision remains:

```text
recover
→ reconcile
→ classify
→ resolve or explicitly defer
→ prove article/P0/P1 closure
→ prove security/repository/provider boundaries
→ prove continuity/recovery
→ adversarial audit
→ canonicalize exact accepted state
→ evaluate every hard-exit predicate
→ certify only if all blocking gates pass
```

Until then:

```yaml
phase_2_99_exit: not_met
phase_2_complete: false
phase_3_entry: blocked_pending_phase_2_99_hard_exit
```
