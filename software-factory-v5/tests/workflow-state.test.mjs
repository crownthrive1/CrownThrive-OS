import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

async function readWorkflow(){
  for (const path of ['.github/workflows/skills-factory-hourly.yml','../.github/workflows/skills-factory-hourly.yml']) {
    try { return await readFile(path,'utf8'); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  throw new Error('skills-factory-hourly.yml not found from package root');
}

test('hourly workflow hydrates durable state before producing', async () => {
  const workflow = await readWorkflow();
  const hydrate = workflow.indexOf('Hydrate last published runtime state');
  const produce = workflow.indexOf('Produce current hourly batch');
  const process = workflow.indexOf('Process PentaGreen handoff queue');
  const publish = workflow.indexOf('Publish append-only runtime state branch');
  assert.ok(hydrate >= 0 && hydrate < produce);
  assert.ok(produce < process && process < publish);
  assert.match(workflow,/automation\/skills-factory-state/);
  assert.match(workflow,/git add -f software-factory-v5\/generated/);
});
