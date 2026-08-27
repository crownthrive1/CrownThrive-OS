# GitHub Actions Runtime and Supply-Chain Standard

**Effective:** 2026-08-26<br />
**Phase:** 3<br />
**Historical origin:** adopted during the retired Phase 2.99 transition
**Status:** current, fail-closed  
**Machine policy:** `developers/manifests/github-actions-runtime-policy.v1.json`

## Purpose

CrownThrive treats the JavaScript runtime used by GitHub Actions as part of the repository security boundary. A workflow is not compliant merely because GitHub can temporarily force a deprecated action onto a newer runtime. The action itself must be on an upstream line that declares the approved runtime, the workflow reference must be immutable, and the repository must fail closed when that state drifts.

The current runtime floor is **Node 24**. **Node 20 action runtime is prohibited** for CrownThrive governed workflows.

## Current approved action inventory

| Action | Approved line | Immutable reference | Runtime | Use |
| --- | --- | --- | --- | --- |
| `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | Node 24 | repository checkout |
| `actions/setup-python` | `v7` | `5fda3b95a4ea91299a34e894583c3862153e4b97` | Node 24 | Python toolchain |
| `actions/setup-node` | `v6.5.0` | `249970729cb0ef3589644e2896645e5dc5ba9c38` | Node 24 | governed Node/TypeScript toolchain |
| `actions/dependency-review-action` | `v5.0.0` | `a1d282b36b6f3519aa1f3fc636f609c47dddb294` | Node 24 | dependency-change review |
| `actions/upload-artifact` | `v7.0.1` | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` | Node 24 | governed evidence upload |
| `actions/attest-build-provenance` | `v4.1.1` | `0f67c3f4856b2e3261c31976d6725780e5e4c373` | Node 24 | provenance attestation for certification evidence |

GitHub CodeQL remains **provider-managed default setup** for this repository. While that provider mode is enabled, CrownThrive must not add a duplicate `github/codeql-action/*` advanced workflow simply to satisfy a local workflow checklist.

## Immutable-reference rule

Every remote `uses:` reference in `.github/workflows/*.yml` or `.github/workflows/*.yaml` must use a full 40-character commit SHA. A human-readable version comment must remain beside the SHA.

Mutable branch references, moving major tags and abbreviated SHAs are prohibited in governed workflow execution. Local actions referenced with `./` are evaluated as repository code and are not subject to the remote-action SHA rule.

This is a supply-chain control, not only a deprecation control. An upstream tag moving unexpectedly must not silently change CrownThrive's executable CI.

## Runner compatibility

The machine policy records `2.327.1` as the minimum Node-24-capable Actions runner floor for this policy generation.

GitHub-hosted runners are permitted. Production and secret-bearing self-hosted execution remains blocked until a separate machine-verifiable promotion proves the required runner generation and Node-24-supported operating-system/architecture profile. One workflow-dispatch-only, secret-free bootstrap certification lane may use the exact labels and repository/ref guard registered in the machine policy so it can produce that attestation. The exception does not authorize provider credentials or production work. Unsupported Node-24 targets, including ARM32 self-hosted runners and macOS 13.4 or older, must not be introduced by assumption.

## Prohibited migration shortcuts

The following are not valid repairs:

- using `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` as a permanent compliance substitute for upgrading an action;
- using `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION`;
- suppressing a runtime deprecation warning without correcting the action;
- weakening/removing the runtime validator so a stale workflow passes;
- introducing a mutable `@vN`, branch or abbreviated-SHA action reference;
- direct-to-`main` automated dependency mutation;
- treating a Dependabot proposal as approved merely because it was generated automatically.

## Deterministic gate

`scripts/validate_github_actions_runtime_policy.py` is a blocking gate in both Documentation Governance and Security Governance. It scans **all GitHub Actions workflow files** and verifies:

1. Node 24 is the policy floor and Node 20 is prohibited.
2. Every remote action is in the approved inventory.
3. Every remote action uses the exact approved full-length SHA and version comment.
4. No runtime escape-hatch variable is present.
5. No unverified production/self-hosted runner is introduced and the one bootstrap certification lane remains exact-label, exact-repository, exact-ref and secret-free.
6. Provider-managed CodeQL is not duplicated by an advanced CodeQL action.
7. Daily GitHub Actions dependency proposals remain configured through Dependabot.
8. Runtime self-healing cannot write directly to `main` or bypass agent governance.

Any failure is a merge block. Runtime/supply-chain drift is classified at least **high** because CI executes inside the institutional control plane.

## Self-healing and refractory behavior

GitHub Actions dependency healing uses a bounded refractory loop:

```text
upstream action/update signal
→ Dependabot pull-request proposal
→ runtime-policy failure or changed-SHA detection
→ upstream runtime/security verification
→ reconcile machine policy + workflow SHA together
→ rerun runtime gate
→ rerun Documentation Governance
→ rerun Security Governance
→ consume applicable provider security evidence
→ independent agent verification
→ ordinary risk/quorum/authority gate
→ merge only if all gates pass
```

The refractory property is deliberate: the same unresolved action-runtime drift remains blocking after repeated cycles. An agent cannot make the alarm disappear by forcing a runtime, suppressing a warning or deleting the detector. A verified repair updates the executable reference and machine policy together, after which the original failing check must pass.

Dependabot is the update **proposal source**, not sovereign authority. Its pull requests enter the same CrownThrive D0-D3, specialist, risk, quorum, Agent D and rollback controls as other governed changes.

## Agent reconciliation rule

Every Agent A/B/C/D/S cycle that touches a workflow, action reference, runner policy, CI validator, dependency policy or security workflow must include the GitHub Actions runtime gate in its handoff evidence.

Agents must reconcile against the newest PR head before writing. If another agent has already upgraded the action line, the next agent validates and extends that packet rather than opening a competing implementation. A stale action reference or stale runtime assertion in a validator is itself drift and must be corrected in the same packet.

## Phase gates

This standard originated as a historical Phase 2.99 hard-exit and Phase 3 entry requirement. It now operates as an ongoing **Phase 3 execution and supply-chain gate**. Phase 3 work remains blocked within the affected scope while any governed workflow contains an unapproved/mutable action reference, a Node-20 action line, an unverified production self-hosted runner, a prohibited runtime escape hatch, or an unreconciled dependency update.

GitHub branch/ruleset enforcement remains separate defense-in-depth under `CT-ADR-GOV-011`; passing the runtime gate does not manufacture current provider enforcement or satisfy independent component/provider gates.
