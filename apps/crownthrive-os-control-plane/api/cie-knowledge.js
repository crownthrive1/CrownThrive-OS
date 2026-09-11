import { BLOG_POSTS, HELP_ARTICLES, LEARNING_MODULES, searchKnowledge } from '../lib/cie-knowledge.js';
import { CIE_PACKETS, publicPacket } from '../lib/cie-packets.js';
export default function handler(req,res){
  res.setHeader('Cache-Control','public, max-age=60, s-maxage=120, stale-while-revalidate=600'); res.setHeader('Content-Type','application/json; charset=utf-8'); res.setHeader('Access-Control-Allow-Origin','*');
  if(req.method!=='GET'){res.setHeader('Allow','GET'); return res.status(405).json({error:'method_not_allowed'});}
  const q=String(req.query?.q||''); const type=String(req.query?.type||'all').toLowerCase(); const slug=String(req.query?.slug||'').toLowerCase();
  if(slug){ const blog=BLOG_POSTS.find((p)=>p.slug===slug); if(blog) return res.status(200).json({ok:true,type:'blog',item:{...blog,url:`/cie/blog/${blog.slug}`}}); const help=HELP_ARTICLES.find((p)=>p.id===slug); if(help) return res.status(200).json({ok:true,type:'help',item:help}); }
  const results=searchKnowledge(q,type); if(type==='packet'||type==='packets') return res.status(200).json({ok:true,type:'packet',count:CIE_PACKETS.length,results:CIE_PACKETS.map(publicPacket)});
  return res.status(200).json({ok:true,schema:'ct.cie.knowledge.v1',query:q,type,count:results.length,results,totals:{blogs:BLOG_POSTS.length,help:HELP_ARTICLES.length,learning:LEARNING_MODULES.length,packets:CIE_PACKETS.length},surfaces:{learn:'/cie/learn',blog:'/cie/blog',help:'/cie/help',packets:'/cie/packets',failure_lab:'/cie/failure-lab'}});
}
