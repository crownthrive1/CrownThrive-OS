# Integration Runtime Certification Federation

Canonical runtime evidence ledger: `crownthrive1/chlom-protocol` → `registry/integration-runtime-certification.json`.

CrownThrive-OS consumes this ledger as evidence and must not reinterpret a registered integration as authenticated or mutation-certified without the corresponding runtime evidence state.

Current state classes remain independent: registered, transport reachable, authenticated/provider verified, and mutation certified.

The canonical CHLOM runtime certifier refreshes the ledger every six hours and records degradation when a registered endpoint becomes unreachable. This repository inherits that status and does not create a competing runtime-certification source of truth.
