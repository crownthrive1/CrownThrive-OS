# PentaSELF Exact-Head Auto-Merge Policy

PentaSELF may initiate source closure only for a repair case that has completed bounded surgery and independent assurance.

## Separation of duties

- **PentaSELF** owns the repair case and submits the certified snapshot.
- **PentaSurgeon** performs the registered repair procedure.
- **PentaRounds** verifies post-operation truth and causal regression.
- **PentaDnD** independently tests the exact repair generation.
- **PentaCertify** independently certifies the same case digest.
- **PentaPR** classifies the exact pull-request head and terminal action.
- **PentaMerge** executes the provider merge.
- **PentaCloser** requires provider readback and documentation before discharge.

PentaSELF does not count its own vote, does not self-approve and does not write directly to `main`.

## Required merge gate

A PentaSELF repair PR is eligible only when all of the following are true:

1. The repair case is `certified` or `discharged`.
2. The case has two independent `pass` certifications against the exact current case SHA-256.
3. The PR targets `main`.
4. The PR is not a draft.
5. The exact head SHA matches the registered repair snapshot.
6. GitHub reports the PR as mergeable.
7. All required checks are green. A repository with zero required checks must be explicitly recorded as such; absence of data is not a pass.
8. There are zero unresolved high-severity findings.
9. PentaDocs internal documentation is published.
10. The provider merge result is independently read back with a merge commit SHA.

## Head movement

Any head-SHA change invalidates the prior gate. The new head must be registered, tested and independently certified before merge promotion can run again.

## Failure behavior

- A check failure, merge conflict, provider error or missing readback places the PR case on hold.
- PentaSELF does not roll back production merely because source closure is held.
- An older PR head cannot be merged after a newer head is registered.
- Direct pushes to `main` are outside this contract.

## Merge method

Use the repository's governed merge method. The exact provider result and merge commit SHA must be written back to the PentaPR terminal reconciliation ledger and the linked hard-repair case.
