# PentaPR, PentaMerge & PentaCloser

**Phase:** 3 — Execute  
**Policy:** every open PR enters a bounded terminal lifecycle.  
**Hard limit:** 12 hours from first PentaPR observation.  
**Terminal outcomes:** `MERGED` or `CLOSED`.

## PentaPR

PentaPR is the intake, stack-awareness, nurture and disposition layer. It scans every open PR, creates a persistent lifecycle marker, fixes the deadline, and applies exactly one active disposition label:

- `penta:merge` — current exact head is mergeable and the Governed Merge Gate is successful;
- `penta:restack` — the branch is conflicting/behind and needs forward reconciliation;
- `penta:nurture` — checks, draft state, or exact-head governance evidence are incomplete;
- `penta:close` — the PR is already superseded or represented.

The deadline marker is persisted on the PR itself and is not recalculated on later runs.

## PentaMerge

PentaMerge follows PentaPR. It never force-merges. It re-reads the exact current head and requires: non-draft state, GitHub mergeability, no failed checks, no pending checks, and a successful exact-head check named `Governed Merge Gate`. Eligible PRs are squash-merged with head-SHA binding.

## PentaCloser

PentaCloser follows both systems and enforces the 12-hour terminal SLA. At or after the stored deadline it performs one final PentaMerge eligibility attempt. If the PR qualifies, it merges. Otherwise it records a terminal rationale and closes the PR. Closing preserves Git history and branch provenance; PentaCloser does not delete branches.

## Cadence

The canonical scheduled sequence is hourly:

- minute `07`: PentaPR;
- minute `27`: PentaMerge;
- minute `47`: PentaCloser.

This provides repeated nurture/merge opportunities while ensuring no tracked PR remains indefinitely open beyond its hard deadline.

## Relationship to PentaVergence and PentaFactory

PentaVergence discovers represented deltas, collisions, repair requirements and restack requirements. PentaPR converts those conditions into PR lifecycle dispositions. PentaFactory may build the repair/restack delta. PentaMerge promotes only a qualified exact head. PentaCloser terminalizes anything that did not qualify by deadline.

`PentaVergence → PentaFactory/repair → PentaPR → PentaMerge → PentaCloser → PentaAudit/Preserve`

The hard deadline is a backlog/transport rule. It does not manufacture D3, provider-write, economic, rights, security, or sovereign authority. If required evidence is absent at the deadline, the safe terminal state is `CLOSED`, not forced merge.
