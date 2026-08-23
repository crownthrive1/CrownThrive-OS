# Corridor Architecture Framework Precompile Skill v1.1

- Agent: `ct.framework-agent.corridor-architecture`
- Suite: `ct.agent-suite.framework-factory-precompile.v1`
- Capability: `ct.capability.framework-precompile.inspect.v1`
- Runtime: `chlom_runtime.framework_precompile_contract_probe_v1`
- State: controlled-test

The agent may inspect registered Corridor Architecture package/work state and prepare bounded precompile evidence. It cannot create corridor authority, activate platforms, materialize changes, certify itself, perform provider writes, vote or execute D3 actions. Private implementation bodies and credentials are never returned.
