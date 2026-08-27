# CrownThrive OS Control Plane

A buildless Vercel application that projects PentaRG, release gates, topology, DAIL receipts, interoperability, and provider delivery state without making provider claims it cannot verify.

## Vercel project contract

- Project: `crownthrive-os-control-plane`
- Team: `crownthrive1s-projects`
- Root Directory: `apps/crownthrive-os-control-plane`
- Framework Preset: `Other`
- Build Command: none
- Output Directory: none

`/api/health` returns deployment metadata supplied by Vercel. `provider_readback` is false outside a Vercel environment, so local rendering cannot be mistaken for a production deployment.
