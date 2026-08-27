#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, subprocess, sys
from dataclasses import dataclass
from typing import Any
from scripts.penta_remediation_bridge import GH, remediate
SCHEMA='ct.penta.ranger-watch.20260827.v1'; MARKER='<!-- penta-ranger-watch:'
CHECK_INTERVAL=dt.timedelta(minutes=10); REMEDIATION_WINDOW=dt.timedelta(minutes=30); ESCALATION_WINDOW=dt.timedelta(minutes=60)
def now_utc(): return dt.datetime.now(dt.timezone.utc)
def iso(v): return v.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')
def parse_iso(v):
    if not v: return None
    try: return dt.datetime.fromisoformat(v.replace('Z','+00:00'))
    except ValueError: return None
@dataclass(frozen=True)
class RangerDecision:
    due: bool; reason: str; first_seen_at: str; next_check_at: str; remediation_deadline_at: str; escalation_at: str; escalation_due: bool
class RangerState:
    def __init__(self,gh:GH,number:int):
        self.gh=gh; self.number=number; self.comment=None; self.state={'schema':SCHEMA,'events':[]}; self._load()
    def _load(self):
        for c in self.gh.paginate(f'/repos/{self.gh.repo}/issues/{self.number}/comments?per_page=100'):
            b=str(c.get('body') or '')
            if MARKER not in b: continue
            m=re.search(r'<!-- penta-ranger-watch:(\{.*?\}) -->',b,re.S)
            if not m: continue
            try: s=json.loads(m.group(1))
            except json.JSONDecodeError: continue
            if s.get('schema')==SCHEMA: self.comment=c; self.state=s; self.state.setdefault('events',[]); return
    def decision(self,head_sha:str,force:bool=False,now=None):
        cur=now or now_utc(); changed=str(self.state.get('head_sha') or '')!=head_sha; first=parse_iso(self.state.get('first_seen_at'))
        if changed or first is None: first=cur
        nxt=parse_iso(self.state.get('next_check_at')); due=force or changed or nxt is None or cur>=nxt
        reason='forced' if force else 'head_changed' if changed else 'interval_due' if due else 'not_due'
        return RangerDecision(due,reason,iso(first),iso(cur+CHECK_INTERVAL),iso(first+REMEDIATION_WINDOW),iso(first+ESCALATION_WINDOW),cur>=first+ESCALATION_WINDOW)
    def event(self,kind,payload):
        ev=self.state.setdefault('events',[]); prev=ev[-1]['event_hash'] if ev else 'GENESIS'; e={'sequence':len(ev)+1,'kind':kind,'at':iso(now_utc()),'previous_hash':prev,'payload':payload}; e['event_hash']=hashlib.sha256(json.dumps(e,sort_keys=True,separators=(',',':')).encode()).hexdigest(); ev.append(e); self.state['events']=ev[-200:]
    def save(self,head_sha,decision,outcome):
        self.state.update({'head_sha':head_sha,'first_seen_at':decision.first_seen_at,'last_check_at':iso(now_utc()),'next_check_at':decision.next_check_at,'remediation_deadline_at':decision.remediation_deadline_at,'escalation_at':decision.escalation_at,'escalation_due':decision.escalation_due,'last_outcome':outcome,'watch_interval_seconds':600,'remediation_window_seconds':1800,'escalation_window_seconds':3600,'semantic_tag_authority':'PentaTagger','remediation_authority':'PentaCrawler/PentaFlows/PentaHelper','terminal_authority':'PentaPR/PentaMerge/PentaCloser','merge_authority_granted':False})
        marker=f"{MARKER}{json.dumps(self.state,separators=(',',':'))} -->"; body=f"{marker}\n\n### PentaRanger autonomous watch\n\n- Exact head: `{head_sha}`\n- Last check: **{self.state['last_check_at']}**\n- Next check: **{self.state['next_check_at']}**\n- Remediation SLA: **{self.state['remediation_deadline_at']}**\n- Escalation boundary: **{self.state['escalation_at']}**\n- Escalation due: **{str(decision.escalation_due).lower()}**\n- Semantic tags: **PentaTagger authoritative**\n- Terminal authority: **PentaPR/PentaMerge/PentaCloser only**\n"
        if self.comment: self.gh.patch(f"/repos/{self.gh.repo}/issues/comments/{self.comment['id']}",{'body':body})
        else: self.comment=self.gh.post(f'/repos/{self.gh.repo}/issues/{self.number}/comments',{'body':body})
def run_tagger(repo,number):
    cmd=[sys.executable,'scripts/penta_github_tagger.py','verify','--repo',repo,'--kind','pr','--number',str(number),'--no-comment']; p=subprocess.run(cmd,check=False,capture_output=True,text=True,timeout=120); return {'returncode':p.returncode,'stdout':p.stdout[-4000:],'stderr':p.stderr[-4000:]}
def inspect_one(gh,number,force=False):
    pull=gh.get(f'/repos/{gh.repo}/pulls/{number}');
    if pull.get('state')!='open': return {'number':number,'status':'SKIP','reason':'pr_not_open'}
    head=str((pull.get('head') or {}).get('sha') or '');
    if not head: raise RuntimeError(f'ranger_head_missing:{number}')
    state=RangerState(gh,number); d=state.decision(head,force=force)
    if not d.due: return {'number':number,'status':'NOT_DUE','head_sha':head,'next_check_at':d.next_check_at}
    state.event('RANGER_WAKE',{'head_sha':head,'reason':d.reason}); tag=run_tagger(gh.repo,number); state.event('TAGGER_READBACK',{'returncode':tag['returncode']})
    try: rem=remediate(gh,number); state.event('REMEDIATION_PASS',rem)
    except Exception as exc: rem={'status':'ERROR','error':str(exc)[:2000],'merge_authority_granted':False}; state.event('REMEDIATION_ERROR',rem)
    if d.escalation_due: state.event('RANGER_ESCALATION_DUE',{'owner':'PentaTriage','head_sha':head,'deadline':d.escalation_at,'terminal_authority_granted':False})
    state.save(head,d,{'tagger':tag,'remediation':rem}); return {'number':number,'status':'CHECKED','head_sha':head,'decision':d.__dict__,'tagger_returncode':tag['returncode'],'remediation_status':rem.get('status'),'merge_authority_granted':False}
def sweep(gh,number=None,force=False):
    nums=[number] if number is not None else [int(p['number']) for p in gh.paginate(f'/repos/{gh.repo}/pulls?state=open&per_page=100&sort=updated&direction=asc')]; results=[]; failures=[]
    for n in nums:
        try: results.append(inspect_one(gh,n,force))
        except Exception as exc: failures.append({'number':n,'error':str(exc)[:2000]})
    return {'schema':'ct.penta.ranger-sweep.20260827.v1','checked_at':iso(now_utc()),'cadence_seconds':600,'results':results,'failures':failures,'merge_authority_granted':False}
def main():
    p=argparse.ArgumentParser(); p.add_argument('mode',nargs='?',choices=('sweep','check'),default='sweep'); p.add_argument('--repo',default=os.environ.get('GITHUB_REPOSITORY')); p.add_argument('--number',type=int); p.add_argument('--force',action='store_true'); a=p.parse_args();
    if not a.repo: raise SystemExit('--repo or GITHUB_REPOSITORY is required')
    if a.mode=='check' and a.number is None: raise SystemExit('check mode requires --number')
    r=sweep(GH(a.repo),a.number,a.force); print(json.dumps(r,indent=2,sort_keys=True)); return 1 if r['failures'] else 0
if __name__=='__main__': raise SystemExit(main())
