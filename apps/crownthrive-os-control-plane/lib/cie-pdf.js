function ascii(value) {
  return String(value ?? '')
    .normalize('NFKD')
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/[^\x20-\x7E\n]/g, '');
}
function esc(value) { return ascii(value).replace(/\\/g,'\\\\').replace(/\(/g,'\\(').replace(/\)/g,'\\)'); }
function wrap(value, width = 82) {
  const words = ascii(value).split(/\s+/).filter(Boolean); const lines=[]; let line='';
  for (const word of words) { const next = line ? `${line} ${word}` : word; if (next.length > width && line) { lines.push(line); line=word; } else line=next; }
  if (line) lines.push(line); return lines;
}
function pageLines(packet, section, index) {
  const lines = [];
  lines.push({t:'CULTURAL IMPRINT ENGINE',s:9,b:true});
  lines.push({t:packet.title,s:index===0?20:15,b:true});
  lines.push({t:index===0?packet.subtitle:`${String(index+1).padStart(2,'0')} / ${section[0]}`,s:index===0?12:11,b:false});
  lines.push({t:'',s:8});
  if (index===0) {
    lines.push({t:packet.description,s:11});
    lines.push({t:'',s:8});
    lines.push({t:'How to use this packet:',s:11,b:true});
    lines.push({t:'Print it, write in it, or keep it beside the CIE Live Lab. The packet is designed to turn cultural and brand judgment into explicit operating context.',s:10});
  }
  for (const item of section[1]) lines.push({t:`- ${item}`,s:10});
  lines.push({t:'',s:8});
  lines.push({t:'Evidence note: This take-home packet is educational. A completed worksheet is not legal clearance, payment authority, ad-spend authority or provider-write authority.',s:8});
  lines.push({t:`CrownThrive, LLC | CIE Website 2.0 | Packet ${packet.id.toUpperCase()} | Page ${index+1} of ${packet.pages}`,s:8});
  return lines;
}
function streamFor(lines) {
  const out=['BT','/F1 10 Tf','54 742 Td']; let current=10;
  for (const line of lines) {
    if (line.t === '') { out.push('0 -10 Td'); continue; }
    const size=line.s||10; if (size!==current) { out.push(`/F1 ${size} Tf`); current=size; }
    const wrapped=wrap(line.t, size>=18?48:size>=14?60:82);
    for (const text of wrapped) { out.push(`(${esc(text)}) Tj`); out.push(`0 -${Math.max(12,Math.round(size*1.45))} Td`); }
  }
  out.push('ET'); return out.join('\n');
}
export function buildPacketPdf(packet) {
  const pageCount = Math.min(packet.pages, packet.sections.length);
  const objects=[]; const add=(body)=>{objects.push(body); return objects.length;};
  const catalog=add('<< /Type /Catalog /Pages 2 0 R >>');
  add('PAGES_PLACEHOLDER');
  const font=add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');
  const pageRefs=[];
  for (let i=0;i<pageCount;i++) {
    const stream=streamFor(pageLines(packet,packet.sections[i],i));
    const contentNum=objects.length+2;
    const pageNum=add(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 ${font} 0 R >> >> /Contents ${contentNum} 0 R >>`);
    add(`<< /Length ${Buffer.byteLength(stream,'utf8')} >>\nstream\n${stream}\nendstream`);
    pageRefs.push(`${pageNum} 0 R`);
  }
  objects[1]=`<< /Type /Pages /Count ${pageRefs.length} /Kids [${pageRefs.join(' ')}] >>`;
  let pdf='%PDF-1.4\n% CIE Take-Home Packet\n'; const offsets=[0];
  objects.forEach((body,i)=>{offsets.push(Buffer.byteLength(pdf,'utf8')); pdf+=`${i+1} 0 obj\n${body}\nendobj\n`;});
  const xref=Buffer.byteLength(pdf,'utf8'); pdf+=`xref\n0 ${objects.length+1}\n0000000000 65535 f \n`;
  for(let i=1;i<offsets.length;i++) pdf+=`${String(offsets[i]).padStart(10,'0')} 00000 n \n`;
  pdf+=`trailer\n<< /Size ${objects.length+1} /Root ${catalog} 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(pdf,'utf8');
}
