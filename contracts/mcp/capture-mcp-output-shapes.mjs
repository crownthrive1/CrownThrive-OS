#!/usr/bin/env node
import fs from 'node:fs';

const serverUrl = process.env.MCP_CERTIFICATION_SERVER_URL;
const bearer = process.env.MCP_CERTIFICATION_BEARER;
const protocolVersion = '2026-07-28';
if (!serverUrl || !bearer) {
  console.error('MCP_CERTIFICATION_SERVER_URL and MCP_CERTIFICATION_BEARER are required');
  process.exit(2);
}

const tools = [
  'crownthrive_io_get_user',
  'crownthrive_io_list_data',
  'crownthrive_io_list_domains',
  'crownthrive_io_list_links',
  'crownthrive_io_list_my_team_memberships',
  'crownthrive_io_list_notification_handlers',
  'crownthrive_io_list_pixels',
  'crownthrive_io_list_projects',
  'crownthrive_io_list_qr_codes',
  'crownthrive_io_list_splash_pages',
  'crownthrive_io_list_teams',
  'crownthrive_io_statistics',
  'seo.archived_audits.list',
  'seo.audits.list',
  'seo.custom_domains.list',
  'seo.notification_handlers.list',
  'seo.teams_member.read',
  'seo.teams.list',
  'seo.user.read',
  'seo.websites.list'
];

const output = [];
for (let index = 0; index < tools.length; index++) {
  const tool = tools[index];
  const id = `shape-${index + 1}`;
  const body = {
    jsonrpc: '2.0',
    id,
    method: 'tools/call',
    params: {
      name: tool,
      arguments: {},
      _meta: {
        'io.modelcontextprotocol/protocolVersion': protocolVersion,
        'io.modelcontextprotocol/clientInfo': { name: 'CrownThrive MCP Schema Capture', version: '1.0.0' },
        'io.modelcontextprotocol/clientCapabilities': {}
      }
    }
  };
  const response = await fetch(serverUrl, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'authorization': `Bearer ${bearer}`,
      'mcp-protocol-version': protocolVersion,
      'mcp-method': 'tools/call',
      'mcp-name': tool,
      'x-crownthrive-certification-mode': 'schema-capture'
    },
    body: JSON.stringify(body)
  });
  const text = await response.text();
  let parsed;
  try { parsed = JSON.parse(text); } catch { throw new Error(`${tool}: non-JSON MCP response`); }
  if (response.status !== 200 || parsed?.result?.isError !== false || parsed?.result?.structuredContent?.ok !== true) {
    throw new Error(`${tool}: certification capture failed with HTTP ${response.status}: ${text.slice(0, 500)}`);
  }
  output.push({ tool_name: tool, structuredContent: parsed.result.structuredContent });
}

const outPath = process.argv[2] || 'mcp-output-shape-captures.json';
fs.writeFileSync(outPath, `${JSON.stringify(output, null, 2)}\n`, { mode: 0o600 });
console.log(JSON.stringify({ captured: output.length, output: outPath, crownthrive_io_reads: 12, thrivetools_seo_reads: 8, provider_writes: 0 }, null, 2));
