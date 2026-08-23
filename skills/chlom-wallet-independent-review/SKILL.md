# CHLOM Wallet Independent Review Skill v2

## Identity

- Suite: `ct.agent-suite.chlom-wallet-independent-review.v1`
- Version: `2.0.0`
- Capability: `ct.capability.chlom-wallet.independent-review.v2`
- Runtime: `chlom_runtime.wallet_independent_review_contract_v2`
- State: controlled-test
- Authority: D1 for the executable wrapper; reviewer identities retain their separately registered ceilings

## Reviewer roles

- Protocol: `ct.chlom.agent.blockchain-crypto`
- Security: `ct.chlom.agent.security`
- Recovery: `ct.chlom.agent.recovery`
- Quorum: `ct.relay.agent-d`
- Release: `ct.chlom.agent.release-certifier`

Each role resolves its current scheduled work ID, exact Git head and evidence digest from the existing v2 schedule definition. The wrapper does not invent or loosen those bindings.

## Executable operations

`status` reads the current independent-review status and returns only a digest plus bounded contract metadata.

`heartbeat` uses the exact v2 schedule/work/head/evidence binding to emit a real reviewer heartbeat, then records a separate executable-capability receipt.

## No decision effect

The executable-contract canary does not submit an independent review receipt, cast a vote, satisfy quorum, release a wallet, advance a phase, deploy code or move money. D3 is human-reserved. Provider write authority is not created.
