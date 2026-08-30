#!/usr/bin/env python3
import argparse, json, os, re, subprocess
from pathlib import Path


# Source-convergence PRs are generated PentaRelease bookkeeping, not a new
# product/runtime delta. GitHub squash merges these PRs using the canonical PR
# title as the commit subject. Keep these reserved prefixes in the decision
# engine itself so a policy edit cannot accidentally turn source convergence
# into another autonomous release and create an infinite release/projection loop.
GENERATED_SURFACE_MERGE_PREFIXES = (
    "PentaRelease comprehensive surface ",
    "PentaRelease surface ",
)


def sh(*args):
    return subprocess.check_output(args, text=True).strip()


def latest_release_tag(prefix="v"):
    tags = sh("git", "tag", "--sort=-version:refname").splitlines()
    for tag in tags:
        if re.fullmatch(rf"{re.escape(prefix)}\d+(?:\.\d+){{2,3}}", tag):
            return tag
    return ""


def parse_version(tag, prefix="v"):
    raw = tag[len(prefix):] if tag.startswith(prefix) else tag
    nums = [int(x) for x in raw.split('.')]
    if len(nums) not in (3, 4):
        raise ValueError(f"Unsupported version: {tag}")
    return nums


def bump(nums, level):
    if len(nums) == 4:
        a,b,c,d = nums
        if level == "major": return [a+1,0,0,0]
        if level == "minor": return [a,b+1,0,0]
        if level == "patch": return [a,b,c+1,0]
        return [a,b,c,d+1]
    a,b,c = nums
    if level == "major": return [a+1,0,0]
    if level == "minor": return [a,b+1,0]
    return [a,b,c+1]


def starts_any(path, prefixes):
    return any(path == p.rstrip('/') or path.startswith(p) for p in prefixes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--policy', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    policy = json.loads(Path(args.policy).read_text())
    prefix = policy.get('release_prefix','v')
    latest = latest_release_tag(prefix)
    if not latest:
        decision = {"decision":"hold","reason":"no_prior_release_tag","release":False}
        Path(args.output).write_text(json.dumps(decision, indent=2)+"\n")
        return

    head_msg = sh("git", "log", "-1", "--pretty=%B")
    generated_prefixes = tuple(policy.get('generated_commit_prefixes', [])) + GENERATED_SURFACE_MERGE_PREFIXES
    if any(head_msg.startswith(p) for p in generated_prefixes):
        decision = {"decision":"hold","reason":"generated_release_commit_guard","release":False,"latest_tag":latest}
        Path(args.output).write_text(json.dumps(decision, indent=2)+"\n")
        return

    files = [x for x in sh("git", "diff", "--name-only", f"{latest}..HEAD").splitlines() if x]
    commits = sh("git", "log", "--format=%s%n%b", f"{latest}..HEAD") if files else ""
    ignored = policy.get('ignored_paths', [])
    relevant = [f for f in files if not starts_any(f, ignored)]
    if len(relevant) < policy.get('minimum_release_relevant_changes',1):
        decision = {"decision":"hold","reason":"no_release_relevant_delta","release":False,"latest_tag":latest,"changed_files":files}
        Path(args.output).write_text(json.dumps(decision, indent=2)+"\n")
        return

    runtime = any(starts_any(f, policy.get('runtime_paths',[])) for f in relevant)
    integration = any(starts_any(f, policy.get('integration_paths',[])) for f in relevant)
    governed_docs = any(starts_any(f, policy.get('governed_docs_paths',[])) for f in relevant)
    docs_only = all(f.endswith(('.md','.mdx','.txt','.json','.yaml','.yml')) or f.startswith('docs/') for f in relevant)

    text = commits.lower()
    rules = policy['release_rules']
    level = 'evidence'
    why = []
    human_required = False
    if any(sig.lower() in text for sig in rules['breaking']['signals']):
        level='major'; why.append('breaking-change signal'); human_required=True
    elif any(sig.lower() in text for sig in rules['feature']['signals']) or runtime:
        level='minor'; why.append('new executable capability or runtime delta')
    elif any(sig.lower() in text for sig in rules['fix']['signals']):
        level='patch'; why.append('production fix/hardening delta')
    elif integration or governed_docs:
        level='evidence'; why.append('governed integration/version/evidence delta')
    elif docs_only and policy.get('docs_only_default') == 'hold':
        decision = {"decision":"hold","reason":"docs_only_non_governed","release":False,"latest_tag":latest,"changed_files":relevant}
        Path(args.output).write_text(json.dumps(decision, indent=2)+"\n")
        return
    else:
        level='evidence'; why.append('release-relevant bounded delta')

    if human_required and policy['gates'].get('d3_human_reserved', True):
        decision = {"decision":"hold","reason":"d3_breaking_change_requires_human_authority","release":False,"latest_tag":latest,"changed_files":relevant,"recommended_bump":level}
        Path(args.output).write_text(json.dumps(decision, indent=2)+"\n")
        return

    current = parse_version(latest,prefix)
    nxt = bump(current,level)
    version = '.'.join(map(str,nxt))
    tag = prefix + version
    scheme = 'crownthrive_extended' if len(nxt)==4 else 'semver'
    decision = {
      "decision":"release",
      "release":True,
      "latest_tag":latest,
      "version":version,
      "tag":tag,
      "version_scheme":scheme,
      "bump":level,
      "why":"; ".join(why),
      "changed_files":relevant,
      "commit_count": int(sh("git","rev-list","--count",f"{latest}..HEAD")),
      "target":"main"
    }
    Path(args.output).write_text(json.dumps(decision, indent=2)+"\n")

if __name__ == '__main__': main()
