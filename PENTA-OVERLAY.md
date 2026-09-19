# PentaOverlay

PentaOverlay is the CrownThrive OS repository-resource reconciliation control plane. It replaces repeated manual repository-resource reconciliation as the primary operating lane once its production activation conditions are met.

## Mission

PentaOverlay continuously reads `.crownthrive/resources/repository-resources.v1.json`, resolves the live GitHub state for every registered resource, applies only explicitly safe reference-fork fast-forwards, hands managed overlays to their governed upstream-convergence path, and prepares a single central registry PR when material state changes.

It is a convergence and continuity Penta, not an authority generator.

## Reference forks

For `REFERENCE_FORK` resources PentaOverlay resolves the CrownThrive fork's actual default branch and the registered upstream repository's actual default branch. It may mutate only when all of the following are true:

1. the fork has zero CrownThrive-only commits;
2. the current fork head is an ancestor of the upstream head;
3. provider write capability is already authorized;
4. the update is a non-force fast-forward; and
5. the resulting CrownThrive fork head reads back exactly as the intended upstream head.

A divergent or CrownThrive-ahead reference fork is a HOLD. PentaOverlay never resets, rebases, force-pushes, or overwrites it.

## Managed overlay forks

For `MANAGED_OVERLAY_FORK` resources PentaOverlay preserves every CrownThrive commit and all upstream provenance. When upstream moves it first looks for an existing repository-local upstream-follow workflow. If one exists, that workflow remains the execution owner and PentaOverlay may dispatch it when provider authorization permits.

If no upstream-follow workflow exists, PentaOverlay may prepare one governed convergence branch and PR by merging upstream into a branch derived from the current CrownThrive default head. A merge conflict remains HOLD. No direct fast-forward of the managed overlay is permitted.

PentaOverlay never creates duplicate active convergence PRs for the same managed repository.

## First-party sources

First-party resources are read back at their actual GitHub default branch and exact live head. PentaOverlay does not rename `main` to `master` or `master` to `main` for cosmetic consistency.

The `CrownThrive-OS` self-reference remains dynamic by contract because a static registry head necessarily predates the merge that changes the registry.

## Supabase boundary

`crownthrive1/Supabase` and the historical name `crownthrive1/thivebase-supabase-` are Supabase platform references only. They are not canonical ThriveBase state authority. PentaOverlay hard-fails classification if that resource is promoted away from `REFERENCE_FORK`, `supabase_platform_reference`, and `reference_only`.

## Provider binding

The production multi-repository lane expects `PENTAOVERLAY_GITHUB_TOKEN` or a successor scoped GitHub App installation token. The credential value is never stored in the registry, receipt, source, artifact, or summary.

If provider binding cannot read a registered private repository or cannot perform an otherwise eligible mutation, the capability remains HOLD. Workflow completion means the engine ran; it is not proof that provider mutation passed.

## Scheduling and activation

`.github/workflows/penta-overlay.yml` runs the control plane every four hours and supports manual dispatch. Pull requests that change PentaOverlay run deterministic contract tests without provider mutation.

A merge to `main` that materially changes PentaOverlay itself also performs one immediate canonical reconciliation. The top-level push trigger is path-scoped to PentaOverlay production files, so unrelated CrownThrive OS pushes do not create duplicate repository sweeps. This gives each production change an immediate provider/readback exercise while the four-hour schedule remains the steady-state cadence.

A production reconciliation can create one central governed registry PR only when:

- the reconciliation receipt is `PASS_OBSERVED`;
- a material registry change exists;
- the checked-out `main` head is still the exact live `main` head; and
- there is no already-open PentaOverlay registry candidate.

The existing CrownThrive PR, security, serialization, governance, and merge gates remain responsible for deciding whether that candidate can merge.

## Dependencies

PentaOverlay composes existing CrownThrive capabilities rather than inventing parallel services: PentaVergence, PentaFederation, PentaRoute, PentaActions, PentaPR, PentaMerge, PentaRelease, PentaSerialized, PentaResults, PentaSecurity, and PentaSELF.

Provider-dependent read/write capability is independently held until live provider evidence exists. That HOLD does not erase the PentaOverlay control plane; it prevents unsupported mutations.

## Retirement of the manual lane

`penta/retirements/repository-resource-manual-reconciliation.v1.json` makes the former repeated manual reconciliation lane conditionally superseded by PentaOverlay. Historical branches, PRs, receipts, provenance, and emergency break-glass diagnosis are preserved. The old lane is not deleted or allowed to compete as a second scheduler.

The retirement becomes effective only after PentaOverlay is canonical on `main`, its exact merged subject passes contract checks, a reconciliation executes from canonical `main` by schedule, manual dispatch, or PentaOverlay production-change activation, and the required multi-repository provider read binding is proven by live readback.

## Non-authority invariant

PentaOverlay never creates provider-write, credential, money, rights, certification, vote/quorum, or D3 authority. Third-party fork content remains third-party reference/provenance and is never relabeled as CrownThrive-authored IP.
