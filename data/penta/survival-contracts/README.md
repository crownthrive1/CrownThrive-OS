# Registered Penta Survival Contracts

This directory contains one machine-readable `PENTA_SURVIVAL_CONTRACT` per registered Penta identity.

Rules:

- filename pattern: `penta.<machine-key-suffix>.v<contract-major>.json`;
- every file must be listed in `data/penta/survival-contracts.registry.json`;
- the registry stores the canonical SHA-256 of the complete contract;
- `penta_id`, canonical name, and maturity must match the current Penta Family catalog record;
- `certified` and `production` declarations must reference an independently verified, unexpired executed-proof bundle under `penta/survival/evidence/`, bound to the exact source commit, artifact SHA-256, runtime/build, doctrine, compiled behavior and function-set hashes;
- template values, prose assertions, model output, workflow success alone, or provider capability do not constitute survival proof;
- retired identities retain their last valid declaration and evidence lineage but are not execution-eligible because of this record.

Start from `data/penta/survival-contract.template.v1.json`. Fix candidate commit A first, build and test the exact artifact, generate a proof bundle outside A, then bind that bundle from the declaration and register the declaration digest in control-plane metadata commit B. B may contain evidence about A; it must never rebuild or relabel A.
