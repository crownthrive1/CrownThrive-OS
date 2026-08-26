# CrownThrive Institutional Archive

**Status:** Active archive policy for Phase 3  
**Purpose:** Preserve superseded, stale, historical, prior-version, pre-entry, and retired documentation without allowing it to silently function as current operating instruction.

## Archive rule

CrownThrive uses **preserve + supersede + reconcile**, not silent deletion.

A document belongs in the historical/archive layer when one or more of the following is true:

- it describes an earlier institutional phase or release and is no longer the active control state;
- it has a newer canonical successor;
- its platform/provider/version claims are stale and are retained only for lineage;
- it is a historical plan, roadmap, research artifact, prospectus, recovered Help Center record, prior contract generation, or deprecated workflow;
- its identity has been renamed, merged, split, sunset, or replaced;
- its substantive body is evidence-worthy but should not be used as current implementation guidance.

## Required historical labeling

Archived material should record, where known:

- original title and path;
- version / effective period;
- archival or supersession date;
- reason for archival disposition;
- successor/current canonical record;
- source/evidence references;
- whether any requirement remains inherited by the current system.

If the original body must be preserved exactly, CrownThrive should add metadata or an archive wrapper rather than rewriting the historical text to sound current.

## States

- `HISTORICAL` — valid evidence of a prior state.
- `SUPERSEDED` — replaced prospectively by an identified successor.
- `DEPRECATED` — retained but no longer recommended/current.
- `RETIRED` — former operational item intentionally removed from active use.
- `UNRESOLVED_HISTORY` — preserved source whose current successor or disposition is not yet proven.

## Current-vs-history precedence

When historical and current material conflict, **CrownThrive OS current effective records control institution-wide state**, with OS-bound verified production/provider evidence, current effective policy, and current founder/governance adjudications controlling within their exact scope. Historical records remain evidence of what was true, intended, or believed at their effective time.

Mintlify, websites, storefronts, media surfaces, and other public properties are downstream projections. Their temporary lag does not redefine current OS state.

## Machine and search behavior

Archived pages should generally be tagged `Historical`, marked `deprecated: true`, and set `noindex: true` when indexing would create likely current-state confusion. Pages needed for public institutional history may remain discoverable, but must display their historical status prominently.

## Never do this

Archiving must not:

- fabricate missing historical article bodies;
- erase provenance or correction history;
- rewrite old evidence to match current architecture;
- convert a historical capability claim into current proof;
- expose restricted/private evidence;
- remove a contract/version that an active dependency still requires;
- treat an archive move as destruction of institutional custody.

## Phase 3 archive cohorts

Phase 3 archive processing prioritizes:

1. Phase 1 / Phase 2 / 2.5 / 2.7 / 2.8 / 2.9 / 2.95 / 2.97 / 2.98 / 2.99 status and pre-entry pages.
2. Superseded CIE/CHLOM runtime and observer versions.
3. Historical roadmap generations replaced by the current institutional roadmap namespace.
4. Renamed/legacy brand or imprint records whose successor is now canonical.
5. Recovered Help Center titles that have a substantive current successor.
6. Old release notes, manifests, and provider-state snapshots retained for audit history.

## Relationship to releases

Git tags, GitHub releases, changelogs, historical registries, and archive pages are complementary. A release is never rewritten simply because a later release exists. Corrections are additive and effective-dated.

## Current canon

For current Phase 3 orientation, use [`../phase3/CURRENT_STATE.md`](../phase3/CURRENT_STATE.md), the root `README.md`, the current version registry, and other active CrownThrive OS records. Downstream Mintlify and website projections inherit this state when their publication workstream runs; they are not alternate sources of truth.
