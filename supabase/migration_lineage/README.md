# Supabase Migration Lineage Recovery

This directory records the 2026-08-27 repair of Git/Supabase migration-history drift after the canonical repository transition to `crownthrive1/CrownThrive-OS`.

## Certified facts

- Production ThriveBase recorded migration versions: **991**.
- SQL files present in `supabase/migrations` before repair: **49**.
- Existing local migrations preserved at exact production timestamps: **27**.
- Local-only timestamp-drift migrations archived append-only: **20**.
- Noncanonical local migration filenames archived append-only: **2**.
- Missing production timestamps materialized as public no-op lineage markers: **964**.
- Final active timestamp parity: **991 / 991**.
- Production migration-history rows changed: **0**.

## Security boundary

Exact historical SQL was not bulk-published from ThriveBase because a bounded scan identified **18** migrations containing secret-like literals, Vault literal creation patterns, or similarly protected implementation material. The production `supabase_migrations.schema_migrations` table remains the authoritative custody location for exact applied statements.

The marker files in `supabase/migrations` are intentionally non-executable no-ops. They repair timestamp lineage for Supabase deployment/branching reconciliation without pretending protected historical SQL is safe for a public repository. Existing source migrations whose timestamps already match production remain intact.

## Rebuild boundary

A clean-room database rebuild using the public lineage markers alone is **HOLD** and is not certified. Clean-room recovery must use the protected ThriveBase recovery package / exact migration history or a separately certified sanitized schema baseline.

## Rollback

Pre-repair repository base: `97f9d9b993e8d80f29b0ec73f290aef44960f3ab`. No production database rollback is required because this repair does not mutate production migration history.
