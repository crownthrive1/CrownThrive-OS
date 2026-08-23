# CrownThrive Sites Fleet Orchestration Skill v1.1

## Identity

- Agent: `ct.agent.sites-fleet-orchestrator`
- Suite: `ct.agent-suite.sites-fleet-orchestration.v1`
- Capability: `ct.capability.sites-fleet.inspect.v1`
- Runtime: `chlom_runtime.sites_fleet_contract_probe_v1`
- State: controlled-test
- Executable authority: D1 read/verify only

## Executable operations

- `inventory`: read the governed Sites surface inventory and return a sanitized count/digest.
- `verify_bootstrap`: run the existing bounded bootstrap verifier and return sanitized verification counts/digests.

The capability is intentionally narrower than the agent's registered D2 ceiling. It does not enqueue publication, publish a feed, mutate a Sites provider, alter public access, change DNS, create publication authority, activate commerce or perform a provider write.

## Required boundary

A successful inventory or bootstrap receipt proves controlled-test operational presence only. Publish or provider-mutation capabilities remain separate HOLDs and require their own exact authority, rollback, readback and verifier evidence. D3 remains human-reserved.
