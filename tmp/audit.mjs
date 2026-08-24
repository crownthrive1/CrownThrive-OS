import fs from 'fs';

const files = fs.readFileSync('/tmp/existing_mdx.txt', 'utf8').trim().split('\n');
const results = [];
const descMap = {};

for (const f of files) {
  const content = fs.readFileSync(f, 'utf8');
  const m = content.match(/^---\n([\s\S]*?)\n---/);
  if (!m) {
    results.push({file: f, hasFrontmatter: false});
    continue;
  }
  const fm = m[1];
  const tMatch = fm.match(/^title:\s*(.*)$/m);
  const dMatch = fm.match(/^description:\s*(.*)$/m);
  const oMatch = fm.match(/^openapi:\s*(.*)$/m);
  let title = tMatch ? tMatch[1].trim().replace(/^["']|["']$/g, '') : '';
  let desc = dMatch ? dMatch[1].trim().replace(/^["']|["']$/g, '') : '';
  // handle multi-line description with folded > or |
  if (dMatch && (dMatch[1].trim() === '>' || dMatch[1].trim() === '|' || dMatch[1].trim() === '>-' || dMatch[1].trim() === '|-')) {
    // read subsequent indented lines
    const lines = fm.split('\n');
    const idx = lines.findIndex(l => l.startsWith('description:'));
    const parts = [];
    for (let i = idx + 1; i < lines.length; i++) {
      if (/^\s+\S/.test(lines[i])) parts.push(lines[i].trim());
      else break;
    }
    desc = parts.join(' ');
  }
  const openapi = oMatch ? oMatch[1].trim() : '';
  results.push({file: f, title, desc, openapi, hasFrontmatter: true, tLen: title.length, dLen: desc.length});
  if (desc) {
    descMap[desc] = descMap[desc] || [];
    descMap[desc].push(f);
  }
}

const dupes = Object.entries(descMap).filter(([k, v]) => v.length > 1);

// Categorize issues
const issues = [];
for (const r of results) {
  if (!r.hasFrontmatter) { issues.push({...r, issue: 'NO_FRONTMATTER'}); continue; }
  const flags = [];
  const isOpenAPIOp = r.openapi && /^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+/i.test(r.openapi);
  if (!r.title && !isOpenAPIOp) flags.push('MISSING_TITLE');
  if (r.title && r.tLen > 60) flags.push(`LONG_TITLE(${r.tLen})`);
  if (!r.desc && !isOpenAPIOp) flags.push('MISSING_DESC');
  if (r.desc && r.dLen < 130) flags.push(`SHORT_DESC(${r.dLen})`);
  if (r.desc && r.dLen > 160) flags.push(`LONG_DESC(${r.dLen})`);
  if (flags.length) issues.push({...r, issue: flags.join(',')});
}

console.log('=== ISSUES ===');
for (const i of issues) {
  console.log(`${i.file} [${i.issue}] title="${i.title}" desc="${(i.desc||'').substring(0,80)}"`);
}
console.log('\n=== DUPLICATE DESCRIPTIONS ===');
for (const [d, fs] of dupes) {
  console.log(`DESC: "${d.substring(0,100)}..."`);
  fs.forEach(f => console.log(`  - ${f}`));
}
console.log(`\n${issues.length} files with issues, ${dupes.length} duplicate description groups`);
