---
title: "Phase 2.99 — Agent F post-PR-91 Help Center reconciliation"
description: "Records the canonical merge of the 795-title machine manifest, preserves unresolved body/articleization state, retires SimpleBase to historical-only provenance, and hands the exact hard-exit ledger delta to the active PR #122 owner without collision."
---

# Phase 2.99 — Agent F post-PR-91 Help Center reconciliation

## Material change

PR #91 merged into canonical `main` at `8fcb68bf209e32ba2cd265e1b6ca730cb8da64d7` on 2026-08-20. The merge message explicitly limits the accepted closure delta to `complete_machine_manifest_generated_in_repo = true`.

The deterministic 795-record Help Center title/hierarchy bundle is therefore now canonical repository evidence. This **does not** close `CT-P299-GATE-002`.

## Source state

`S11 — Help Center Structure (2).pdf` remains the title/hierarchy authority for 795 recovered records, nine top-level sections and 150 recovered subcategories.

A fresh Agent-F/M permissioned-source pass reconfirmed:
- File Library contains `Help Center Structure (2).pdf`;
- Google Drive contains the S11 PDF plus related Structure/Spine copies;
- Gmail contains the December 8, 2025 SimpleBase outage record for `help.crownthrive.com`;
- no available source recovered an original historical article-body archive.

Accordingly, `S94` remains unresolved and body recovery count remains zero. No missing body or current policy was synthesized.

## SimpleBase disposition

SimpleBase is **retired historical-only provenance**. It is not an active dependency, restoration target, or future documentation platform. Historical SimpleBase records may be used only to establish prior Help Center existence, outage/loss chronology and recovery provenance. GitHub + Mintlify remain the current institutional support stack.

## Collision-safe hard-exit handoff

Canonical `main` still carries the older hard-exit ledger value:

`articleization.complete_machine_manifest_generated_in_repo = false`

That value is now stale relative to the accepted PR #91 merge. The ledger must be reconciled to `true`.

Agent F does **not** edit that ledger here because active PR #122 owns:
- `developers/manifests/phase-2-99-hard-exit-ledger.v1.json`
- `scripts/validate_phase_2_99_hard_exit_ledger.py`
- `changelog/phase-2-99-hard-exit-ledger-v1-3-deferral-reconciliation.md`

The exact Agent-F handoff to Agent C/B is: preserve #122 ownership and incorporate the PR #91 merge delta during its current-main reconciliation before promotion.

## What remains open

The following remain false and continue to block GATE-002:
- terminal disposition for all 795 records;
- current section/category mapping;
- exposure classification;
- D0-D3 risk classification;
- owner or owner-queue assignment;
- canonical route or explicit nonpublic state;
- source/platform mapping;
- navigation or intentionally-unlisted state;
- P0/P1 substantive body or explicit unresolved-source closure;
- S94 body recovery/completeness provenance;
- required D2/D3 approvals where current legal, rights, money, privacy/security, Scripture/canon or other binding authority is involved.

## Next Agent F packet

The next non-colliding articleization packet should derive **P0/P1 candidate cohorts and explicit unresolved-source closures** from the recovered titles/hierarchy, then map current Mintlify targets only where repository/current-source evidence exists. Candidate classification may prepare owner queues, exposure/risk and navigation state, but it may not promote current policy or production behavior from title wording alone.

## Authority

Agent F is non-voting. A/B/C/D/S remain the sovereign voter pool. Phase 2 / 2.99 remains current and Phase 3 remains `blocked_pending_phase_2_99_hard_exit`.

Rollback: revert this bounded three-file Agent-F reconciliation packet. No provider, customer, credential, rights, payment or production state is changed.
