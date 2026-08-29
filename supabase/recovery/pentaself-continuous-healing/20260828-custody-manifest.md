# PentaSELF Continuous Healing — Production Migration Custody Manifest

Observed production window: 2026-08-27 23:54 ET through 2026-08-28 00:06 ET  
Canonical provider: ThriveBase / Supabase project `tzajnzshmtzjenqulehq`  
Operating phase: canonical Phase 3 — Execute / founder-declared Phase 3.5 convergence and hardening

## Custody state

**HOLD — exact SQL source restoration and replay evidence remain required.**

The six migrations below were applied additively to production to establish durable PentaSELF message intake, problem ownership, bounded healing, verification, and hourly founder reporting. This manifest preserves exact provider version identity, local source digest, byte count, line count, and the non-negotiable replay rules. It does not claim that a manifest substitutes for the six exact SQL migration files.

| Provider version | Migration name | SHA-256 | Bytes | Lines |
|---|---|---|---:|---:|
| `20260828035429` | `penta_self_continuous_healing_schema_v1` | `69333cbadeb572bb3dd2b93eb91f90cb305235258abe5036e201bfff2c040bdd` | 21,259 | 394 |
| `20260828035549` | `penta_self_continuous_message_intake_v1` | `ba2da7df93f4b7ea475b7277fb46fbfde4b92e0bc4ac6ae34f0b7fba0e2038af` | 18,652 | 240 |
| `20260828035701` | `penta_self_continuous_heal_cycle_v1` | `b8ccc1958827d27b095ca425b773d3a27fdd83640ebd3917ac2ce076c820d8eb` | 14,169 | 186 |
| `20260828035757` | `penta_self_continuous_status_and_reporting_v1` | `f423826fd56be4963ec91e5164c54219d960cee903d64a0194d68fba5944c4b7` | 10,814 | 126 |
| `20260828035903` | `penta_self_continuity_schedule_and_problem_handoff_v1` | `f56ac796d0e0d4664fda40ca8bc27d13ef399bb6d44aa1f118606a95f062144a` | 15,222 | 138 |
| `20260828040634` | `penta_self_single_hourly_founder_report_lane_v1` | `37c7a8d2cf72fffa5230f8de1b649a3579c963297d7b7df0c3f27e4c71c3416d` | 6,131 | 106 |

Combined local source inventory: 86,247 bytes / 1,190 lines.

## Production behavior established

- Cursor-based inspection of every message entering registered CrownThrive institutional event sources.
- A durable problem ledger with unique fingerprints, persistent ownership, retry scheduling, independent verification evidence, and no-delete history.
- Append-only message-scan and repair-attempt receipts.
- Direct bounded D0–D2 repair handlers plus delegated PentaBuild, PentaCertify, PentaRelease, PentaStatus, PentaScribe, PentaDocs, PentaCredentials, PentaHook, and PentaLiaison lanes.
- D3 remains human-reserved.
- No authority manufacture, credential manufacture, uncertified provider write, release-gate bypass, or unauthorized money movement.
- Continuous detect → heal → verify cycles on odd minutes: `1-59/2 * * * *`.
- One hourly founder healing report at minute `0`, addressed to `jones.usmc.kj@gmail.com`.
- One Mailgun slot remains reserved inside the governed 10-message rolling-hour ceiling.
- The commercial release packager was staggered from minute 27 to minute 33 to separate it from developer-commerce reconciliation and reduce deterministic deadlock risk.

## Exact restoration standard

PentaSerialized, PentaBuild, and PentaCertify must not close this custody lane until all of the following are true:

1. The six exact SQL files exist under `supabase/migrations/` with filenames matching the provider versions and migration names above.
2. Each repository file reproduces the SHA-256, byte count, and line count recorded in this manifest.
3. Ordered non-production replay succeeds against the repository migration chain.
4. RLS, explicit client-deny policies, service-role access, append-only triggers, required cron schedules, and function grants are verified after replay.
5. Current production readback confirms the same objects and invariants without rewriting provider migration history.
6. DAIL/PentaSerialized receipts preserve this manifest, the eventual source commit, replay evidence, and any corrective lineage.

## Current source-custody disposition

This branch records the lineage immediately so the production changes cannot become invisible. The source-custody problem remains assigned to `PentaSerialized/PentaBuild/PentaCertify` in the PentaSELF problem ledger and must remain open until exact SQL source and replay readback are present.
