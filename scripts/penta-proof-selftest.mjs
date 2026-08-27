import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pentaproof-'));
const base = {
  schema: 'ct.penta.cookie-canary.v1',
  sha: '0123456789abcdef',
  tests: [{name:'a',status:'PASS'},{name:'b',status:'PASS'}],
  passed: 2,
  failed: 0,
  verdict: 'PASS'
};

function run(name, mutate, expectSuccess, env={}) {
  const input = path.join(tmp, `${name}.json`);
  const output = path.join(tmp, `${name}.proof.json`);
  const value = structuredClone(base);
  mutate(value);
  fs.writeFileSync(input, JSON.stringify(value));
  const result = spawnSync(process.execPath, ['scripts/penta-proof.mjs', input, output], {
    encoding: 'utf8',
    env: {...process.env, ...env}
  });
  const success = result.status === 0;
  if (success !== expectSuccess) {
    console.error(JSON.stringify({name, expected:expectSuccess, actual:success, stdout:result.stdout, stderr:result.stderr}, null, 2));
    process.exit(1);
  }
  return {name,status:'PASS'};
}

const results = [];
results.push(run('valid_evidence',()=>{},true,{PENTAPROOF_SOURCE_ARTIFACT_DIGEST:'sha256:'+'a'.repeat(64)}));
results.push(run('reject_failed_verdict',e=>{e.verdict='FAIL'},false));
results.push(run('reject_nonzero_failed_count',e=>{e.failed=1},false));
results.push(run('reject_duplicate_test_names',e=>{e.tests[1].name='a'},false));
results.push(run('reject_nonpass_test',e=>{e.tests[1].status='FAIL'},false));
results.push(run('reject_missing_execution_sha',e=>{e.sha=''},false));
results.push(run('reject_bad_artifact_digest',()=>{},false,{PENTAPROOF_SOURCE_ARTIFACT_DIGEST:'md5:deadbeef'}));

console.log(JSON.stringify({schema:'ct.penta.proof-selftest.v1',tests:results,passed:results.length,failed:0,verdict:'PASS'},null,2));
