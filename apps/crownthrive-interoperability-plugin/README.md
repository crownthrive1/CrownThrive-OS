# CrownThrive Interoperability Fabric Plugin

This directory is the public-safe application scaffold for `ct.plugin.crownthrive-interoperability-fabric` version `0.1.0`.

## Current state

- MCP/App candidate only
- backend controlled-test runtime: `chlom-interoperability-control`
- MCP server ID: `ct.mcp.chlom-interoperability-control`
- not installed
- not submitted
- not publicly listed
- checkout and entitlements disabled

The live protected implementation remains in THIVEBASE/Supabase Edge Functions. This repository contains the public contract, widget candidate and submission-readiness metadata. It does not contain credentials, service-role keys, protected transforms, private identity mappings, algorithm weights, private evidence or provider-routing topology.

## Candidate experience

The initial widget is a read-oriented interoperability dashboard that can display:

- registered systems;
- contract state;
- route state;
- compatibility score receipts;
- plugin lifecycle and commercial-gate state.

Mutation tools remain separately authorized and independently verified. The widget must never imply that a planned route is deployed or that a score is certification.

## Required promotion gates

1. exact MCP tool/readback tests;
2. widget accessibility and responsive-device tests;
3. authentication and tenant-boundary review;
4. negative testing for secret/private-identity leakage;
5. submission manifest review;
6. rights and public-policy review;
7. pricing and fulfillment authorization;
8. governed app submission and published readback.

## Files

- `app-manifest.json` — candidate application metadata and capability references
- `widget/index.html` — public-safe widget candidate

No production deployment or OpenAI submission should be inferred from this scaffold.
