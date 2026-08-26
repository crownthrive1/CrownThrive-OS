# PentaTagger + PentaPR GitHub Lifecycle

## Production purpose

This control plane makes Penta classification visible and executable in GitHub without collapsing semantic tagging, lifecycle classification, merge execution, and close execution into one actor.

The canonical chain is:

1. **PentaPR** classifies an open pull request as `MERGE`, `RESTACK`, `NURTURE`, or `CLOSE` and maintains the 12-hour terminal deadline.
2. **PentaTagger** applies and reads back GitHub labels for entity type, operational lane, risk, lifecycle projection, and terminal state. It produces an idempotent receipt comment when invoked directly.
3. **PentaMerge** performs exact-head squash merge only after the governed merge gate is green.
4. **PentaCloser** performs terminal close after the hard deadline when exact-head merge remains ineligible.

PentaTagger never merges or closes. PentaPR never manufactures a successful merge gate. PentaMerge and PentaCloser preserve separate terminal authority.

## GitHub-native label model

### Identity and authority

- `penta:tagged`
- `penta:entity:pr`
- `penta:entity:issue`
- `penta:authority:tagger`
- `penta:authority:pr`
- `penta:authority:merge`
- `penta:authority:closer`

### Risk

- `penta:risk:d0` — informational or documentation-only change
- `penta:risk:d1` — bounded operational change
- `penta:risk:d2` — production, security, rights, provider, database, money, or destructive change

### Operational lanes

- `penta:lane:docs`
- `penta:lane:workflow`
- `penta:lane:database`
- `penta:lane:provider`
- `penta:lane:security`
- `penta:lane:commerce`
- `penta:lane:media`
- `penta:lane:observability`
- `penta:lane:general`

A PR or issue can carry multiple lane labels. PentaTagger reconciles only labels in its managed label families and preserves unrelated repository labels.

### Lifecycle and terminal state

PentaPR retains the compatible disposition labels:

- `penta:merge`
- `penta:restack`
- `penta:nurture`
- `penta:close`
- `penta:deadline-12h`

PentaTagger projects those dispositions into visible stage labels:

- `penta:stage:merge-ready`
- `penta:stage:restack`
- `penta:stage:nurture`
- `penta:stage:close-candidate`

Terminal writes produce:

- `penta:terminal:merged`
- `penta:terminal:closed`

The disposition label remains as audit history after terminal execution. Active stage labels are removed when an item becomes terminal.

## Operator override

`penta:hold` is the explicit operator/founder override. It blocks PentaMerge and PentaCloser. PentaPR classifies a held PR as `NURTURE / operator_hold` until the label is removed.

## Event and schedule wiring

### Pull requests

`.github/workflows/penta-pr-lifecycle.yml` reacts immediately to pull-request target events and preserves the existing scheduled lanes:

- minute 7: PentaPR classification
- minute 27: PentaMerge execution
- minute 47: PentaCloser terminal execution

Each lifecycle run invokes PentaTagger afterward, preventing independent workflows from racing or overwriting the projected lifecycle stage.

### Issues and reconciliation sweeps

`.github/workflows/penta-github-tagger.yml` reacts to issue events and performs a six-hour reconciliation sweep across open issues and pull requests.

### Verification

`.github/workflows/penta-github-tagger-contract.yml` compiles the control software, runs unit tests, and statically rejects merge/close execution paths inside PentaTagger.

## Readback contract

A label write is not treated as successful until GitHub returns the expected labels on a fresh read. A missing expected label fails the run.

Direct PentaTagger invocations maintain one idempotent marker comment per issue or PR containing:

- classified lanes
- risk level
- lifecycle or terminal projection
- label readback verdict
- deterministic receipt digest
- authority boundary

PentaPR lifecycle runs suppress the duplicate receipt comment but publish the same readback evidence into the GitHub Actions job summary.

## Source files

- `scripts/penta_github_labels.py`
- `scripts/penta_github_tagger.py`
- `scripts/penta_pr_lifecycle.py`
- `.github/workflows/penta-github-tagger.yml`
- `.github/workflows/penta-github-tagger-reusable.yml`
- `.github/workflows/penta-github-tagger-contract.yml`
- `.github/workflows/penta-pr-lifecycle.yml`
- `.github/workflows/penta-pr-lifecycle-reusable.yml`
