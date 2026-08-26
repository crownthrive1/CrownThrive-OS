# CrownThrive Autonomous Software Factory v2

Status: **control plane installed in ThriveBase; production promotion remains fail-closed until executable adapters and release gates pass.**

This package implements the CrownThrive software-building factory as a governed runtime rather than a documentation-only concept. The factory accepts institutional build requests, creates an ordered build run, executes specialized lanes, records artifacts and evidence, emits at most **one production package per run**, and only permits implementation after validation and governance gates pass.

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

A five-minute `pg_cron` job named `ct-software-factory-tick-v2` invokes `ct_factory_tick()` to claim the next queued autonomous request and advance the first eligible lane.

## Build lanes

Every run is materialized as:

`discover -> architect -> generate -> security -> test -> package -> deploy -> assurance`

A downstream lane cannot become ready until every earlier lane is `passed` or `skipped`. A failed/held lane therefore stops forward promotion without deleting evidence.

## Production throughput invariant

A partial unique index enforces no more than one production package in `candidate`, `approved`, or `implemented` state for each build run. The intended throughput is one implemented production package per successful run, not one file, one feature, or one repository commit.

The production package manifest is expected to enumerate all affected assets, including source, migrations, Edge Functions, API/MCP contracts, documentation deltas, tests, deployment records, rollback material, and evidence digests.

## Fail-closed behavior

`production_enabled` defaults to `false` for the seed factory project. The system may autonomously discover, architect, build, test, and package while production implementation is held until the relevant deployment adapters and evidence gates are demonstrably functional. This prevents the factory from manufacturing deployment authority merely because a build succeeded.

## Source-of-truth alignment

The factory is designed to implement the shared CrownThrive operating spine: registry/data, CrownThrive IO/MCP integration, CHLOM governance, identity/permissions, support/documentation, analytics/events, and corridor-specific adapters. Each factory project carries an `asset_scope`, `build_contract`, and `deployment_contract` so platform-specific work can be produced without collapsing the ecosystem into one monolith.

## Next executable adapter layer

The worker contract in this directory is intentionally provider-neutral. Each adapter must supply its own verified endpoint, credentials, repository/deployment target, health checks, rollback operation, and authority class. High-consequence changes remain governed by CHLOM/DAIL evidence and cannot be silently promoted by a lower-authority lane.
