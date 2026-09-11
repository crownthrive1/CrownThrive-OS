import { auditPackage } from '../lib/cie-public-audit.js';
export default function handler(req,res){
  res.setHeader('Cache-Control','no-store, max-age=0'); res.setHeader('Content-Type','application/json; charset=utf-8'); res.setHeader('Access-Control-Allow-Origin','*'); res.setHeader('Access-Control-Allow-Methods','GET, POST, OPTIONS'); res.setHeader('Access-Control-Allow-Headers','Content-Type');
  if(req.method==='OPTIONS') return res.status(204).end();
  if(req.method==='GET') return res.status(200).json({schema:'ct.cie.public-package-audit.service.v1',status:'OPERATIONAL',method:'POST',max_assets:30,authority:{provider_write:false,payment:false,ad_spend:false,protected_calibration:false,persistence:false}});
  if(req.method!=='POST'){res.setHeader('Allow','GET, POST, OPTIONS'); return res.status(405).json({error:'method_not_allowed'});}
  const body=typeof req.body==='object'?req.body:(()=>{try{return JSON.parse(req.body||'{}')}catch{return null}})(); if(!body) return res.status(400).json({error:'invalid_json'});
  if(!Array.isArray(body.assets)||!body.assets.length) return res.status(400).json({error:'assets_required'});
  return res.status(200).json(auditPackage(body));
}
