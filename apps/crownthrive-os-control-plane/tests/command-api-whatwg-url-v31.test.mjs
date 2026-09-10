import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const read = (path) => readFile(new URL(path, root), 'utf8');

for (const path of ['api/command.js', 'api/operations.js']) {
  test(`${path} uses canonical WHATWG request parsing`, async () => {
    const source = await read(path);
    assert.match(source, /CANONICAL_COMMAND_ORIGIN = 'https:\/\/crown-thrive-os\.vercel\.app'/);
    assert.match(source, /new URL\(String\(request\?\.url \|\| '\/'\), CANONICAL_COMMAND_ORIGIN\)\.searchParams/);
    assert.doesNotMatch(source, /request\.query|req\.query/);
    assert.doesNotMatch(source, /url\.parse\(|from ['"]node:url['"]|require\(['"]url['"]\)/);
    assert.doesNotMatch(source, /x-forwarded-host|headers\.host/);
  });
}

test('command API clamps event limits from URLSearchParams', async () => {
  const source = await read('api/command.js');
  assert.match(source, /requestSearchParams\(request\)\.get\('limit'\)/);
  assert.match(source, /MIN_EVENT_LIMIT/);
  assert.match(source, /MAX_EVENT_LIMIT/);
});

test('operations API supports bounded window aliases through URLSearchParams', async () => {
  const source = await read('api/operations.js');
  assert.match(source, /params\.get\('window'\)/);
  assert.match(source, /params\.get\('hours'\)/);
  assert.match(source, /raw === '1h'/);
  assert.match(source, /raw === '7d'/);
  assert.match(source, /168/);
});
