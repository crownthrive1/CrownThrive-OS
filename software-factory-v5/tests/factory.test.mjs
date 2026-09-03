import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = process.cwd();
const run = (output, at) => {
  const r = spawnSync(process.execPath,['src/factory.mjs','--output',output,'--at',at],{cwd:root,encoding:'utf8'});
  assert.equal(r.status,0,r.stderr);
  return JSON.parse(r.stdout.trim().split('\n').at(-1));
};

test('registry contains 59 unique skills', async () => {
  const reg=JSON.parse(await readFile(join(root,'registry/skills.registry.json'),'utf8'));
  const rows = reg.skills || reg.skill_rows.map(row => Object.fromEntries(reg.skill_columns.map((key, index) => [key, row[index]])));
  assert.equal(rows.length,59);
  assert.equal(new Set(rows.map(s=>s.skill_id)).size,59);
});

test('hourly tick produces an idempotent ten-skill PentaGreen batch', async () => {
  const out=await mkdtemp(join(tmpdir(),'ct-skills-'));
  const first=run(out,'2026-09-02T21:17:00.000Z');
  const second=run(out,'2026-09-02T21:17:00.000Z');
  assert.equal(first.current_batch.produced,10);
  assert.equal(first.current_batch.pentagreen_handoffs,10);
  assert.equal(first.idempotent,false);
  assert.equal(second.idempotent,true);
  const batch=JSON.parse(await readFile(join(out,'pentagreen/current-batch.json'),'utf8'));
  assert.equal(batch.handoffs.length,10);
  assert.ok(batch.handoffs.every(h=>h.state==='HOLD'));
});

test('next hour advances without duplicate package hashes', async () => {
  const out=await mkdtemp(join(tmpdir(),'ct-skills-next-'));
  run(out,'2026-09-02T21:17:00.000Z');
  const first=JSON.parse(await readFile(join(out,'pentagreen/current-batch.json'),'utf8'));
  run(out,'2026-09-02T22:17:00.000Z');
  const second=JSON.parse(await readFile(join(out,'pentagreen/current-batch.json'),'utf8'));
  const a=new Set(first.handoffs.map(h=>h.package_hash));
  assert.equal(second.handoffs.filter(h=>a.has(h.package_hash)).length,0);
});


test('compact runtime registry hydrates all 59 skills', async () => {
  const raw = JSON.parse(await readFile(join(root,'registry/skills.registry.json'),'utf8'));
  assert.equal(raw.registry_schema_version, '1.1.0-compact');
  assert.equal(raw.skill_rows.length, 59);
  assert.equal(raw.skill_columns.length, 9);
});
