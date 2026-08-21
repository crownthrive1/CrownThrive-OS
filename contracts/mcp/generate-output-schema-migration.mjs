#!/usr/bin/env node
import fs from 'node:fs';

const schemasPath = process.argv[2];
const outputPath = process.argv[3] || 'mcp-output-schema-migration.sql';
if (!schemasPath) {
  console.error('usage: node generate-output-schema-migration.mjs <schemas.json> [output.sql]');
  process.exit(2);
}
const schemas = JSON.parse(fs.readFileSync(schemasPath, 'utf8'));
const names = Object.keys(schemas).sort();
if (names.length !== 20) throw new Error(`expected exactly 20 central schemas, found ${names.length}`);

function quoteLiteral(value) { return `'${String(value).replaceAll("'", "''")}'`; }
function isGeneric(schema) {
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) return true;
  const keys = Object.keys(schema).filter((key) => !['$schema','description','title'].includes(key));
  return keys.length === 1 && schema.type === 'object';
}
for (const name of names) {
  const schema = schemas[name];
  if (isGeneric(schema)) throw new Error(`${name}: generic output schema is prohibited`);
  if (schema.$schema !== 'https://json-schema.org/draft/2020-12/schema') throw new Error(`${name}: JSON Schema 2020-12 marker is required`);
  if (schema.type !== 'object' || schema.additionalProperties !== false) throw new Error(`${name}: top-level output schema must be a closed object`);
}

const statements = names.map((name) => `update integration_control.mcp_tools\nset output_schema = ${quoteLiteral(JSON.stringify(schemas[name]))}::jsonb, updated_at = now()\nwhere enabled = true and service_id in ('crownthrive_io','thrivetools_seo') and tool_name = ${quoteLiteral(name)};`).join('\n\n');
const sql = `-- CT-MCP-EXTCERT-001\n-- POST-SIGNATURE GENERATED ARTIFACT. Independent review is required before application.\n-- No rows are deleted.\n\nbegin;\n\n${statements}\n\ndo $$\ndeclare\n  v_enabled integer;\n  v_generic integer;\nbegin\n  select count(*) into v_enabled from integration_control.mcp_tools where enabled=true and service_id in ('crownthrive_io','thrivetools_seo');\n  select count(*) into v_generic from integration_control.mcp_tools where enabled=true and service_id in ('crownthrive_io','thrivetools_seo') and output_schema = '{\"type\":\"object\"}'::jsonb;\n  if v_enabled <> 20 then raise exception 'expected 20 central enabled tools, found %', v_enabled; end if;\n  if v_generic <> 0 then raise exception 'generic central output schemas remain: %', v_generic; end if;\nend $$;\n\ncommit;\n`;
fs.writeFileSync(outputPath, sql, { mode: 0o600 });
console.log(JSON.stringify({ schemas: names.length, output: outputPath, deletes: 0, provider_writes: 0 }, null, 2));
