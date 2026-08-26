# Penta GitHub Execution Fabric

**Version:** 1.0.0  
**State:** production for GitHub-hosted, secret-free repository validation  
**Self-hosted state:** certification-only until exact machine attestation passes

The fabric converts GitHub work into a bounded, testable and evidence-producing pipeline.

| Component | Production responsibility |
| --- | --- |
| **PentaRunners** | Registers runner pools, labels, eligibility, priority and action ceilings. |
| **PentaPunters** | Routes each validated request to the highest-priority eligible production runner. It cannot promote a held runner. |
| **PentaActions** | Stores immutable argument-vector contracts. Shell interpolation and unregistered commands are rejected. |
| **PentaResults** | Emits a deterministic receipt containing request, contract, stdout, stderr and final-result SHA-256 digests. |

## Execution path

`action request → contract validation → production runner selection → action allowlist → shell-free execution → sealed result receipt → GitHub artifact`

The production workflow is `.github/workflows/penta-github-execution-fabric.yml`. It runs on the already-approved `ubuntu-latest` pool, validates the repository-wide Node 24 Actions policy, executes the fabric test suite and publishes a 30-day evidence artifact.

## Fail-closed controls

- Unknown actions, duplicate identities, malformed labels and shell-enabled actions fail.
- A runner must be explicitly `production`; `certification_only` and `hold` cannot receive work.
- A production runner must separately allow the selected action.
- Self-hosted execution remains restricted to `.github/workflows/penta-runner-fabric-certification.yml` until exact runner evidence supports a separate policy promotion.
- Receipts prove the observed execution only. They do not create provider, release, economic, legal or governance authority.

## Local certification

```bash
python3 -m unittest tests.test_penta_github_fabric
python3 scripts/validate_github_actions_runtime_policy.py
python3 -m penta.github_fabric.cli \
  --contract penta/github_fabric/contract.v1.json \
  --request penta/github_fabric/request.example.json \
  --receipt /tmp/penta-github-execution-result.json
```

Rollback is one commit revert. Existing runner certification and runtime-supply-chain controls remain authoritative and unchanged.
