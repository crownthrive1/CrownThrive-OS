// Syntax-only validation: never import or execute the supplied source.
import { readFileSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import { spawnSync } from 'node:child_process';

if (process.argv.length !== 3) {
  throw new Error('Usage: node scripts/check_typescript_syntax.mjs <source.ts>');
}
const source = readFileSync(process.argv[2], 'utf8');
// Node --check does not strip TypeScript, even with --experimental-strip-types.
// Reject unsupported/non-erasable syntax rather than silently transforming it.
const stripped = stripTypeScriptTypes(source, { mode: 'strip' });
const result = spawnSync(process.execPath, ['--input-type=module', '--check'], {
  input: stripped,
  encoding: 'utf8',
});
if (result.error) throw result.error;
if (result.stdout) process.stdout.write(result.stdout);
if (result.stderr) process.stderr.write(result.stderr);
process.exit(result.status ?? 1);
