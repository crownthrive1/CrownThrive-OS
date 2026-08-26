#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, json, os, re, sys, urllib.error, urllib.parse, urllib.request

API='https://api.github.com'
MARKER='<!-- penta-pr-lifecycle:'
DISP_LABELS={'MERGE':'penta:merge','RESTACK':'penta:restack','NURTURE':'penta:nurture','CLOSE':'penta:close'}
ALL_LABELS=list(DISP_LABELS.values())+['penta:deadline-12h']

class GH:
  def __init__(self, repo):
    self.repo=repo; self.token=os.environ['GITHUB_TOKEN']
  def req(self, method, path, body=None):
    data=None if body is None else json.dumps(body).encode()
    r=urllib.request.Request(API+path,data=data,method=method,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'PentaPR/1.0'})
    try:
      with urllib.request.urlopen(r,timeout=30) as x:
        raw=x.read(); return json.loads(raw or b'null')
    except urllib.error.HTTPError as e:
      raw=e.read().decode(errors='replace')
      raise RuntimeError(f'{method} {path} -> {e.code}: {raw[:300]}')
  def get(self,p): return self.req('GET',p)
  def post(self,p,b): return self.req('POST',p,b)
  def patch(self,p,b): return self.req('PATCH',p,b)
  def put(self,p,b): return self.req('PUT',p,b)
  def delete(self,p):
    try:return self.req('DELETE',p)
    except RuntimeError as e:
      if '404' in str(e): return None
      raise

def iso(t): return t.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')
def parse_iso(s): return dt.datetime.fromisoformat(s.replace('Z','+00:00'))

def ensure_labels(gh):
  existing={x['name'] for x in gh.get(f'/repos/{gh.repo}/labels?per_page=100')}
  palette={'penta:merge':'0e8a16','penta:restack':'fbca04','penta:nurture':'1d76db','penta:close':'b60205','penta:deadline-12h':'5319e7'}
  for name in ALL_LABELS:
    if name not in existing:
      gh.post(f'/repos/{gh.repo}/labels',{'name':name,'color':palette[name],'description':'PENTA PR lifecycle control'})

def checks(gh, sha):
  runs=gh.get(f'/repos/{gh.repo}/commits/{sha}/check-runs?per_page=100').get('check_runs',[])
  statuses=gh.get(f'/repos/{gh.repo}/commits/{sha}/status')
  bad={'failure','cancelled','timed_out','action_required','stale','startup_failure'}
  pending=any(x.get('status')!='completed' for x in runs) or statuses.get('state')=='pending'
  failed=any(x.get('conclusion') in bad for x in runs) or statuses.get('state') in {'failure','error'}
  governed=[x for x in runs if 'governed merge gate' in (x.get('name') or '').lower()]
  governed_ok=any(x.get('status')=='completed' and x.get('conclusion')=='success' for x in governed)
  return {'failed':failed,'pending':pending,'governed_ok':governed_ok,'count':len(runs)}

def lifecycle_comment(gh,n):
  cs=gh.get(f'/repos/{gh.repo}/issues/{n}/comments?per_page=100')
  for c in cs:
    b=c.get('body') or ''
    if MARKER in b:
      m=re.search(r'<!-- penta-pr-lifecycle:(\{.*?\}) -->',b,re.S)
      if m:
        try:return c,json.loads(m.group(1))
        except json.JSONDecodeError: pass
  return None,None

def save_state(gh,n,state):
  body=f"{MARKER}{json.dumps(state,separators=(',',':'))} -->\n\nPentaPR lifecycle control. Hard terminal deadline: **{state['deadline_at']}**. Current disposition: **{state['disposition']}**."
  c,_=lifecycle_comment(gh,n)
  if c: gh.patch(f"/repos/{gh.repo}/issues/comments/{c['id']}",{'body':body})
  else: gh.post(f'/repos/{gh.repo}/issues/{n}/comments',{'body':body})

def set_labels(gh,n,disp):
  issue=gh.get(f'/repos/{gh.repo}/issues/{n}')
  names={x['name'] for x in issue.get('labels',[])}
  for old in DISP_LABELS.values():
    if old in names and old!=DISP_LABELS[disp]: gh.delete(f'/repos/{gh.repo}/issues/{n}/labels/{urllib.parse.quote(old,safe="")}')
  for name in [DISP_LABELS[disp],'penta:deadline-12h']:
    if name not in names: gh.post(f'/repos/{gh.repo}/issues/{n}/labels',{'labels':[name]})

def classify(gh,pr):
  p=gh.get(f"/repos/{gh.repo}/pulls/{pr['number']}")
  text=((p.get('title') or '')+'\n'+(p.get('body') or '')).lower()
  if 'superseded by' in text or 'represented-zero-delta' in text: return 'CLOSE','superseded_or_represented'
  if p.get('draft'): return 'NURTURE','draft'
  if p.get('mergeable') is False or p.get('mergeable_state') in {'dirty','behind'}: return 'RESTACK',p.get('mergeable_state') or 'not_mergeable'
  c=checks(gh,p['head']['sha'])
  if c['failed']: return 'NURTURE','checks_failed'
  if c['pending']: return 'NURTURE','checks_pending'
  if p.get('mergeable') is True and c['governed_ok']: return 'MERGE','mergeable_governed_green'
  return 'NURTURE','awaiting_governed_merge_gate'

def pentapr(gh):
  ensure_labels(gh); now=dt.datetime.now(dt.timezone.utc)
  prs=gh.get(f'/repos/{gh.repo}/pulls?state=open&per_page=100&sort=created&direction=asc')
  for pr in prs:
    _,st=lifecycle_comment(gh,pr['number'])
    if not st:
      st={'first_seen_at':iso(now),'deadline_at':iso(now+dt.timedelta(hours=12)),'disposition':'NURTURE','reason':'first_seen','head_sha':pr['head']['sha']}
    disp,reason=classify(gh,pr); st.update({'disposition':disp,'reason':reason,'head_sha':pr['head']['sha'],'updated_at':iso(now)})
    set_labels(gh,pr['number'],disp); save_state(gh,pr['number'],st)
    print(f"PentaPR #{pr['number']} {disp} {reason} deadline={st['deadline_at']}")

def attempt_merge(gh,n):
  p=gh.get(f'/repos/{gh.repo}/pulls/{n}'); c=checks(gh,p['head']['sha'])
  if p.get('draft') or p.get('mergeable') is not True or c['failed'] or c['pending'] or not c['governed_ok']:
    return False,'not_currently_merge_eligible'
  r=gh.put(f'/repos/{gh.repo}/pulls/{n}/merge',{'merge_method':'squash','sha':p['head']['sha'],'commit_title':f"PentaMerge: {p['title']}"})
  return bool(r.get('merged')),r.get('message','merge_attempted')

def pentamerge(gh):
  prs=gh.get(f'/repos/{gh.repo}/pulls?state=open&per_page=100')
  for pr in prs:
    labels={x['name'] for x in gh.get(f"/repos/{gh.repo}/issues/{pr['number']}").get('labels',[])}
    if 'penta:merge' not in labels: continue
    ok,msg=attempt_merge(gh,pr['number']); print(f'PentaMerge #{pr["number"]} merged={ok} {msg}')

def pentacloser(gh):
  now=dt.datetime.now(dt.timezone.utc); prs=gh.get(f'/repos/{gh.repo}/pulls?state=open&per_page=100')
  for pr in prs:
    _,st=lifecycle_comment(gh,pr['number'])
    if not st: continue
    if now < parse_iso(st['deadline_at']): continue
    merged,msg=attempt_merge(gh,pr['number'])
    if merged: print(f'PentaCloser #{pr["number"]} terminal=MERGED'); continue
    gh.post(f"/repos/{gh.repo}/issues/{pr['number']}/comments",{'body':f"PentaCloser terminal disposition at the 12-hour hard limit. This PR did not satisfy current exact-head merge requirements and is being closed, not force-merged. Last PentaPR disposition: `{st.get('disposition')}`. Merge attempt: `{msg}`. History and branch provenance remain preserved."})
    gh.patch(f"/repos/{gh.repo}/pulls/{pr['number']}",{'state':'closed'})
    print(f'PentaCloser #{pr["number"]} terminal=CLOSED')

def main():
  ap=argparse.ArgumentParser(); ap.add_argument('mode',choices=['pr','merge','closer']); ap.add_argument('--repo',default=os.getenv('GITHUB_REPOSITORY')); a=ap.parse_args()
  if not a.repo: raise SystemExit('repo_required')
  gh=GH(a.repo)
  {'pr':pentapr,'merge':pentamerge,'closer':pentacloser}[a.mode](gh)
if __name__=='__main__': main()
