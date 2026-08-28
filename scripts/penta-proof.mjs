import fs from 'node:fs';
import crypto from 'node:crypto';

const input = process.argv[2] || 'penta-cookie-evidence.json';
const output = process.argv[3] || 'penta-proof-envelope.json';

function fail(message) {
  console.error(`PentaProof HOLD: ${message}`);
  process.exit(1);
}

if (!fs.existsSync(input)) fail(`missing evidence file: ${input}`);
const raw = fs.readFileSync(input);
let evidence;
try {
  evidence = JSON.parse(raw.toString('utf8'));
} catch (error) {
  fail(`invalid JSON: ${error.message}`);
}

if (!evidence || typeof evidence !== 'object' || Array.isArray(evidence)) fail('evidence must be an object');
if (evidence.verdict !== 'PASS') fail(`source verdict is ${String(evidence.verdict)}`);
if (!Array.isArray(evidence.tests) || evidence.tests.length === 0) fail('tests array missing or empty');

const names = new Set();
for (const test of evidence.tests) {
  if (!test || typeof test.name !== 'string' || !test.name) fail('test name missing');
  if (names.has(test.name)) fail(`duplicate test name: ${test.name}`);
  names.add(test.name);
  if (test.status !== 'PASS') fail(`test not PASS: ${test.name}`);
}
if (evidence.failed !== 0) fail(`failed count must be zero, got ${String(evidence.failed)}`);
if (evidence.passed !== evidence.tests.length) fail(`passed count ${String(evidence.passed)} does not equal test count ${evidence.tests.length}`);
if (typeof evidence.sha !== 'string' || !evidence.sha) fail('source execution SHA missing');

const artifactDigest = process.env.PENTAPROOF_SOURCE_ARTIFACT_DIGEST ?? null;
if (artifactDigest !== null && !artifactDigest.startsWith('sha256:')) fail('source artifact digest must use sha256');

const sourceDigest = crypto.createHash('sha256').update(raw).digest('hex');
const observedAt = new Date().toISOString();
const envelopeCore = {
  schema: 'ct.penta.proof-envelope.v1',
  penta: 'PentaProof',
  version: '1.0.0',
  state: 'CERTIFIED_EVIDENCE',
  verdict: 'PASS',
  observed_at: observedAt,
  source: {
    path: input,
    schema: evidence.schema ?? 'unknown',
    execution_sha: evidence.sha,
    sha256: sourceDigest,
    test_count: evidence.tests.length,
    passed: evidence.passed,
    failed: evidence.failed,
    workflow_run_id: process.env.PENTAPROOF_SOURCE_RUN_ID ?? null,
    artifact_id: process.env.PENTAPROOF_SOURCE_ARTIFACT_ID ?? null,
    artifact_digest: artifactDigest
  },
  execution: {
    repository: process.env.GITHUB_REPOSITORY ?? 'local',
    workflow: process.env.GITHUB_WORKFLOW ?? 'local',
    run_id: process.env.GITHUB_RUN_ID ?? 'local',
    run_attempt: process.env.GITHUB_RUN_ATTEMPT ?? 'local',
    event_name: process.env.GITHUB_EVENT_NAME ?? 'local',
    ref: process.env.GITHUB_REF ?? 'local',
    actor: process.env.GITHUB_ACTOR ?? 'local'
  },
  authority_boundary: {
    evidence_verification_is_not_release_authority: true,
    evidence_verification_is_not_money_movement_authority: true,
    evidence_verification_is_not_rights_authority: true,
    no_provider_dispatch: true,
    fail_closed: true
  },
  dail_projection: {
    event_type: 'penta.proof.certification.evidence',
    immutable_payload_required: true,
    source_digest: sourceDigest,
    source_artifact_digest: artifactDigest,
    execution_sha: evidence.sha
  }
};
const envelopeHash = crypto.createHash('sha256').update(JSON.stringify(envelopeCore)).digest('hex');
const envelope = {...envelopeCore, envelope_sha256: envelopeHash};
fs.writeFileSync(output, `${JSON.stringify(envelope, null, 2)}\n`);
console.log(JSON.stringify({penta:'PentaProof', verdict:'PASS', source_sha256:sourceDigest, envelope_sha256:envelopeHash, output}, null, 2));
