# CrownThrive Institutional Asset Fabric Plugin

**Plugin ID:** `ct.plugin.institutional-asset-fabric`  
**Version:** `0.1.0`  
**Runtime:** `ct.mcp.institutional-asset-fabric` version `0.1.0`  
**State:** controlled test / governed HOLD

This package is the public-safe repository contract for CrownThrive's institutional asset controller. It supports governed discovery, planning, scrutiny, versioning and independent verification of plugins, pallets, kernels, scripts, workflows, skills, prompts, tests, policies, runbooks and bundles.

## Package boundary

This repository package may contain:

- stable IDs and versions;
- public tool contracts;
- candidate manifests;
- blueprint catalogs;
- public-safe documentation;
- generators and validators;
- widget resources;
- cryptographic digests;
- lifecycle and blocker state.

It does not contain:

- credentials or private keys;
- private identity mappings;
- exact kernel weights or thresholds;
- protected compiler policy;
- private provider topology;
- confidential evidence bodies;
- service-role configuration;
- arbitrary executable binaries.

## Root tools

- `assets.status`
- `assets.search`
- `assets.fetch`
- `assets.blueprints.list`
- `assets.dependencies.plan`
- `assets.compile.plan`
- `assets.verify`
- `assets.risks.scan`
- `assets.supersession.plan`
- `assets.bundles.list`
- `assets.generation.run`

All tools are non-destructive. Planning tools do not execute source or provider operations. Generation creates candidate blueprint records only.

## Current scale

- 4,000 deterministic blueprint candidates;
- 456 curated asset specifications;
- 32 plugins;
- 24 pallets;
- 16 protected kernels;
- 96 scripts;
- 64 workflows;
- 64 skills;
- 64 prompt packs;
- 32 TEVV suites;
- 32 policies;
- 32 runbooks;
- 160 bounded execution plans;
- eight asset bundles.

The counts describe governed records, not 4,000 production deployments.

## Promotion boundary

A package remains controlled test until exact source, dependencies, tests, security/privacy, execution plan, readback and independent certification are complete. Installation, app submission, publication, rights, pricing, fulfillment, checkout and entitlements remain separate gates.
