#!/usr/bin/env node
import fs from 'node:fs';
import crypto from 'node:crypto';

const envelopePath = new URL('./founder-signature-envelope.v1.json', import.meta.url);
const envelope = JSON.parse(fs.readFileSync(envelopePath, 'utf8'));
const requireSigned = process.argv.includes('--require-signed');

function gitBlobSha1(bytes) {
  const prefix = Buffer.from(`blob ${bytes.length}\0`, 'utf8');
  return crypto.createHash('sha1').update(prefix).update(bytes).digest('hex');
}

const resolved = [];
for (const item of envelope.authorized_payload) {
  const bytes = fs.readFileSync(item.path);
  const blobSha = gitBlobSha1(bytes);
  if (blobSha !== item.blob_sha) {
    throw new Error(`authorized payload drift: ${item.path} expected ${item.blob_sha}, got ${blobSha}`);
  }
  resolved.push({ blob_sha: blobSha, path: item.path });
}
resolved.sort((a, b) => a.path.localeCompare(b.path));
const canonical = JSON.stringify(resolved);
const digest = crypto.createHash('sha256').update(canonical).digest('hex');
if (digest !== envelope.authorized_payload_sha256) {
  throw new Error(`authorized payload digest mismatch: expected ${envelope.authorized_payload_sha256}, got ${digest}`);
}
if (envelope.authorized_effect?.provider_write_budget !== 0) throw new Error('provider write budget must remain zero');
if (envelope.authorized_effect?.non_d0_tool_enablement !== false) throw new Error('non-D0 tool enablement must remain false');
if (envelope.authorized_effect?.sovereign_vote_authority !== false) throw new Error('certification signature must remain non-sovereign');
if (envelope.authorized_effect?.phase_3_advancement !== false) throw new Error('signature cannot advance Phase 3');

if (requireSigned) {
  if (envelope.signature_state !== 'signed') throw new Error('founder signature state is not signed');
  if (envelope.signature_text !== envelope.signature_text_required) throw new Error('founder signature text does not match the exact required attestation');
  if (typeof envelope.signed_at !== 'string' || !envelope.signed_at) throw new Error('signed_at is required');
  if (typeof envelope.signed_in !== 'string' || !envelope.signed_in) throw new Error('signed_in evidence reference is required');
} else if (envelope.signature_state !== 'awaiting_signature' && envelope.signature_state !== 'signed') {
  throw new Error(`unexpected signature_state: ${envelope.signature_state}`);
}

console.log(JSON.stringify({
  certification_id: envelope.certification_id,
  signature_state: envelope.signature_state,
  authorized_payload_sha256: digest,
  authorized_files: resolved.length,
  provider_read_budget: envelope.authorized_effect.provider_read_budget,
  provider_write_budget: envelope.authorized_effect.provider_write_budget,
  require_signed: requireSigned
}, null, 2));
