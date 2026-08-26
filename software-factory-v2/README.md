# PentaFactory™ Runtime — Software Factory v2

Status: **governed control-plane/runtime package; production promotion remains fail-closed until executable provider adapters and release gates pass.**

PentaFactory is CrownThrive's canonical governed software/framework production system. This `software-factory-v2` package is its executable compatibility runtime and preserves the stable `ct.factory.v2` / `ct_factory_*` contracts already used by ThriveBase and downstream automation.

The runtime accepts institutional build requests, creates an ordered build run, executes specialized lanes, records artifacts and evidence, emits at most **one production package per run**, and permits implementation only after validation, rights/authority, deployment, rollback, and assurance gates pass.

## Runtime contract

The factory is controlled by ThriveBase and uses these persistent entities:

- `ct_factory_projects`
- `ct_factory_build_requests`
- `ct_factory_build_runs`
- `ct_factory_work_units`
- `ct_factory_artifacts`
- `ct_factory_release_packages`
- `ct_factory_deployment_targets`
- `ct_factory_events`

The current CrownThrive OS v2 dispatcher seeds the governed `factory_tick` task internally rather than requiring an independent external scheduler. Historical `ct-software-factory-tick-v2` identifiers may remain in compatibility surfaces, but do not define the canonical product name.

## Build lanes

Every run is materialized as:

`discover -> architect -> generate -> security -> test -> package -> deploy -> assurance`

A downstream lane cannot become ready until every earlier lane is `passed` or `skipped`. A failed or held lane stops forward promotion without deleting evidence.

## Production throughput invariant

A partial unique index enforces no more than one production package in `candidate`, `approved`, or `implemented` state for each build run. The intended throughput is one implemented production package per successful run, not one file, one feature, or one repository commit.

The production package manifest is expected to enumerate all affected assets, including source, migrations, Edge Functions, API/MCP contracts, documentation deltas, tests, deployment records, rollback material, and evidence digests.

## Fail-closed behavior

`production_enabled` defaults to `false` for seed projects unless explicit current authority and adapter verification say otherwise. PentaFactory may autonomously discover, architect, generate, test, and package while production implementation is held until the relevant deployment adapters and evidence gates are demonstrably functional. A successful build does not manufacture deployment authority.

## Penta integration

PentaFactory is designed to implement the shared CrownThrive operating spine while interoperating with bounded Penta systems:

- **PentaDocs** — documentation impact, changelogs, current-state and historical projection;
- **PentaRoute / PentaFederation** — provider and integration routing where certified;
- **PentaGeneration** — software/version/recovery continuity;
- **PentaStudios / PentaBooks and corridor systems** — governed build targets rather than duplicate factories;
- **CHLOM** — rights, provenance, authority, evidence, rules and remedies;
- **ThriveBase** — runtime state, queues, ledgers, artifacts and execution evidence.

Each factory project carries an `asset_scope`, `build_contract`, and `deployment_contract` so platform-specific work can be produced without collapsing the ecosystem into one monolith.

## Provider adapter rule

The worker/compiler contract in this directory is provider-neutral. Each production adapter must supply its own verified endpoint, credential path, repository/deployment target, health checks, rollback operation, authority class, provider-native write evidence, and readback evidence. High-consequence changes remain governed and cannot be silently promoted by a lower-authority lane.

## Compatibility

The following may remain intentionally stable for runtime compatibility even when human-facing naming says **PentaFactory**:

- `ct.factory.v2`
- `ct_factory_*` database objects
- existing `ct-software-factory-*` worker/scheduler identifiers
- `ct.pentaframework-factory.v1` where an already-deployed provider contract depends on it
- existing provider function slugs until a governed migration replaces them

Compatibility identifiers are not competing product names.