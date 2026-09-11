import { packetById, publicPacket } from '../lib/cie-packets.js';
import { buildPacketPdf } from '../lib/cie-pdf.js';
export default function handler(req,res){
  if(!['GET','HEAD'].includes(req.method)){res.setHeader('Allow','GET, HEAD'); return res.status(405).end();}
  const packet=packetById(req.query?.id); if(!packet) return res.status(404).json({error:'packet_not_found'});
  if(String(req.query?.format||'').toLowerCase()==='json'){res.setHeader('Content-Type','application/json; charset=utf-8'); return res.status(200).json({ok:true,packet:publicPacket(packet),sections:packet.sections});}
  const pdf=buildPacketPdf(packet); res.setHeader('Content-Type','application/pdf'); res.setHeader('Content-Disposition',`inline; filename="${packet.slug}.pdf"`); res.setHeader('Cache-Control','public, max-age=300, s-maxage=3600'); res.setHeader('X-CIE-Packet',packet.id); if(req.method==='HEAD') return res.status(200).end(); return res.status(200).send(pdf);
}
