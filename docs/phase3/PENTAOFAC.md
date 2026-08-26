# PentaOFAC — CrownThrive OS Binding

PentaOFAC is the Phase 3 sanctions-data monitoring and evidence subsystem for the CrownThrive OS.

Canonical implementation and authority contract live in `crownthrive1/chlom-protocol`:

- `registry/penta-ofac-v1.json`
- `docs/architecture/PENTAOFAC.md`
- ThriveBase runtime: `https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-ofac?action=status`

The OS consumes PentaOFAC as a compliance signal source. A sanctions-feed change does not itself authorize blocking funds, rejecting counterparties, or declaring a person/entity sanctioned. Downstream action remains separately governed by CHLOM policy and evidence.

PentaOFAC monitors both OFAC SDN Advanced XML and Consolidated non-SDN Advanced XML on staggered 15-minute schedules, validates XML/namespace integrity, computes SHA-256 fingerprints, records change events, and preserves operational evidence in ThriveBase.
