# Master Governed Agent Control Self-Test Skill v1

## Scope

- Suite: `ct.agent-suite.master.v1`
- Capability: `ct.capability.master-agent.control-self-test.v1`
- Runtime: `chlom_runtime.master_agent_control_probe_v1`
- Executable authority: D1
- Operation: `self_test` only

## Eligibility

This capability is allowlisted only to Master Suite skills whose current `mcp_state` is `test`. Current coverage is 32 test subroutes. The 42 `disabled` subroutes remain intentionally dormant and are not auto-activated by this contract.

## What the self-test proves

The control self-test resolves the exact skill package, agent template, registered autonomy/authority ceiling, existing executable-capability count, active schedule count and prior health state. It records a controlled-test invocation and can support operational-presence health evidence.

## What it does not do

The self-test performs no domain action. It grants no provider read/write, sales, pricing, identity, security, remediation, publication, commerce, licensing, project, voting or D3 authority. It cannot turn a dormant subroute on, change an agent's registered ceiling, self-certify, move money, grant rights, return secrets or write directly to main.
