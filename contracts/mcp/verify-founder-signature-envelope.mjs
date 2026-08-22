#!/usr/bin/env node
import fs from 'node:fs';

const envelope = JSON.parse(fs.readFileSync(new URL('./founder-signature-envelope.v1.json', import.meta.url), 'utf8'));
const plan = JSON.parse(fs.readFileSync(new URL('./external-certification-plan.v1.json', import.meta.url), 'utf8'));
const requireSigned = process.argv.includes('--require-signed');

if (envelope.certification_id !== plan.certification_id) throw new Error('certification identity mismatch');
if (envelope.signature_state !== 'invalidated_by_material_security_remediation') throw new Error('security-remediated envelope must remain invalidated');
if (envelope.replacement_authorized_payload_sha256 !== null) throw new Error('replacement digest cannot exist before independent review');
if (envelope.authorized_effect.provider_read_budget !== 0) throw new Error('provider reads must remain disabled');
if (envelope.authorized_effect.provider_write_budget !== 0) throw new Error('provider writes must remain disabled');
if (envelope.authorized_effect.oidc_minting !== false) throw new Error('OIDC minting must remain disabled');
if (envelope.authorized_effect.non_d0_tool_enablement !== false) throw new Error('non-D0 enablement must remain false');
if (envelope.authorized_effect.sovereign_vote_authority !== false) throw new Error('signature envelope must remain non-sovereign');
if (envelope.authorized_effect.phase_3_advancement !== false) throw new Error('signature cannot advance Phase 3');
if (requireSigned) throw new Error('replacement founder signature is unavailable; execution is blocked');

console.log(JSON.stringify({
  certification_id: envelope.certification_id,
  signature_state: envelope.signature_state,
  replacement_digest: null,
  provider_reads: 0,
  provider_writes: 0,
  execution_enabled: false
}, null, 2));

