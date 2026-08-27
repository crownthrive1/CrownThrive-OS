#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


class LineageError(RuntimeError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ReleaseBaseline:
    latest_tag: str
    latest_tag_sha: str
    source_baseline_sha: str
    resolution: str


def sh(*args):
    return subprocess.check_output(args, text=True).strip()


def git_commit(ref):
    try:
        value = sh("git", "rev-parse", "--verify", f"{ref}^{{commit}}")
    except subprocess.CalledProcessError as exc:
        raise LineageError("release_lineage_commit_unresolvable") from exc
    if not SHA1_RE.fullmatch(value):
        raise LineageError("release_lineage_commit_invalid")
    return value


def is_ancestor(ancestor, descendant):
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise LineageError("release_lineage_ancestry_unverifiable")


def latest_release_tag(prefix="v"):
    tags = sh("git", "tag", "--sort=-version:refname").splitlines()
    for tag in tags:
        if re.fullmatch(rf"{re.escape(prefix)}\d+(?:\.\d+){{2,3}}", tag):
            return tag
    return ""


def parse_version(tag, prefix="v"):
    raw = tag[len(prefix) :] if tag.startswith(prefix) else tag
    nums = [int(x) for x in raw.split(".")]
    if len(nums) not in (3, 4):
        raise ValueError(f"Unsupported version: {tag}")
    return nums


def bump(nums, level):
    if len(nums) == 4:
        a, b, c, d = nums
        if level == "major":
            return [a + 1, 0, 0, 0]
        if level == "minor":
            return [a, b + 1, 0, 0]
        if level == "patch":
            return [a, b, c + 1, 0]
        return [a, b, c, d + 1]
    a, b, c = nums
    if level == "major":
        return [a + 1, 0, 0]
    if level == "minor":
        return [a, b + 1, 0]
    return [a, b, c + 1]


def starts_any(path, prefixes):
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes)


def _expanded_lineage_paths(policy, key, version):
    values = policy.get("lineage", {}).get(key, [])
    if not isinstance(values, list) or not values or not all(isinstance(value, str) for value in values):
        raise LineageError("release_lineage_policy_invalid")
    try:
        return [value.format(version=version) for value in values]
    except (KeyError, ValueError) as exc:
        raise LineageError("release_lineage_policy_invalid") from exc


def _path_allowed(path, allowed):
    return any(path.startswith(rule) if rule.endswith("/") else path == rule for rule in allowed)


def _release_manifest(tag, policy, version):
    template = policy.get("lineage", {}).get("generated_release_manifest")
    if not isinstance(template, str) or not template:
        raise LineageError("release_lineage_policy_invalid")
    try:
        path = template.format(version=version)
    except (KeyError, ValueError) as exc:
        raise LineageError("release_lineage_policy_invalid") from exc
    try:
        manifest = json.loads(sh("git", "show", f"{tag}:{path}"))
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise LineageError("divergent_latest_tag_manifest_invalid") from exc
    if not isinstance(manifest, dict):
        raise LineageError("divergent_latest_tag_manifest_invalid")
    if manifest.get("tag") != tag or str(manifest.get("version")) != version:
        raise LineageError("divergent_latest_tag_manifest_identity_mismatch")
    decision = manifest.get("decision")
    if decision is not None and not isinstance(decision, dict):
        raise LineageError("divergent_latest_tag_manifest_decision_invalid")
    if isinstance(decision, dict) and decision.get("tag") not in (None, tag):
        raise LineageError("divergent_latest_tag_manifest_identity_mismatch")
    return manifest


def _recorded_source_head(manifest):
    values = []
    if manifest.get("source_head_sha") is not None:
        values.append(manifest["source_head_sha"])
    decision = manifest.get("decision")
    if isinstance(decision, dict) and decision.get("source_head_sha") is not None:
        values.append(decision["source_head_sha"])
    if not values:
        return ""
    if not all(isinstance(value, str) and SHA1_RE.fullmatch(value) for value in values):
        raise LineageError("divergent_latest_tag_source_head_invalid")
    if len(set(values)) != 1:
        raise LineageError("divergent_latest_tag_source_head_inconsistent")
    return values[0]


def _legacy_generated_parent_allowed(policy, tag, tag_sha, parent):
    lineage = policy.get("lineage", {})
    if lineage.get("allow_legacy_generated_release_parent") is not True:
        return False
    entries = lineage.get("legacy_generated_release_parent_allowlist")
    if not isinstance(entries, list):
        raise LineageError("release_lineage_policy_invalid")
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("tag"), str)
            or not isinstance(entry.get("tag_sha"), str)
            or not SHA1_RE.fullmatch(entry["tag_sha"])
            or not isinstance(entry.get("source_head_sha"), str)
            or not SHA1_RE.fullmatch(entry["source_head_sha"])
        ):
            raise LineageError("release_lineage_policy_invalid")
    for entry in entries:
        if entry["tag"] != tag:
            continue
        if entry.get("tag_sha") != tag_sha or entry.get("source_head_sha") != parent:
            raise LineageError("divergent_latest_tag_legacy_lineage_mismatch")
        return True
    return False


def resolve_release_baseline(tag, policy, head_ref="HEAD"):
    """Resolve the exact prior source revision represented by the latest release.

    A normal tag already contained in the target history is safe as the comparison
    base. A divergent tag is accepted only when it is a single generated package
    commit whose parent is explicitly recorded (new contract) or can be recovered
    under the bounded legacy rule. Every other divergent shape remains HOLD.
    """

    if policy.get("lineage", {}).get("fail_closed_on_divergent_latest_tag") is not True:
        raise LineageError("release_lineage_policy_invalid")

    tag_sha = git_commit(tag)
    head_sha = git_commit(head_ref)
    if is_ancestor(tag_sha, head_sha):
        return ReleaseBaseline(tag, tag_sha, tag_sha, "tag_commit")

    version = tag[len(policy.get("release_prefix", "v")) :]
    prefixes = policy.get("generated_commit_prefixes", [])
    if not isinstance(prefixes, list) or not all(isinstance(prefix, str) for prefix in prefixes):
        raise LineageError("release_lineage_policy_invalid")
    subject = sh("git", "show", "-s", "--format=%s", tag_sha)
    if not prefixes or not any(subject.startswith(prefix) for prefix in prefixes):
        raise LineageError("divergent_latest_tag_not_generated_release")

    parent_row = sh("git", "rev-list", "--parents", "-n", "1", tag_sha).split()
    parents = parent_row[1:]
    if len(parents) != 1:
        raise LineageError("divergent_latest_tag_not_single_parent")
    parent = parents[0]

    changed = [
        path
        for path in sh("git", "diff", "--name-only", f"{parent}..{tag_sha}").splitlines()
        if path
    ]
    allowed = _expanded_lineage_paths(policy, "allowed_generated_release_paths", version)
    required = set(_expanded_lineage_paths(policy, "required_generated_release_files", version))
    if not changed or any(not _path_allowed(path, allowed) for path in changed):
        raise LineageError("divergent_latest_tag_changed_untrusted_paths")
    if not required.issubset(set(changed)):
        raise LineageError("divergent_latest_tag_missing_required_package_files")

    manifest = _release_manifest(tag, policy, version)
    recorded_source = _recorded_source_head(manifest)
    if recorded_source:
        if recorded_source != parent:
            raise LineageError("divergent_latest_tag_source_head_parent_mismatch")
        resolution = "generated_release_recorded_source"
    elif _legacy_generated_parent_allowed(policy, tag, tag_sha, parent):
        resolution = "generated_release_parent_legacy"
    else:
        raise LineageError("divergent_latest_tag_source_head_missing")

    if not is_ancestor(parent, head_sha):
        raise LineageError("divergent_latest_tag_source_not_in_target_history")
    return ReleaseBaseline(tag, tag_sha, parent, resolution)


def _lineage_fields(baseline, source_head_sha):
    return {
        "latest_tag": baseline.latest_tag,
        "latest_tag_sha": baseline.latest_tag_sha,
        "source_baseline_sha": baseline.source_baseline_sha,
        "source_head_sha": source_head_sha,
        "lineage_resolution": baseline.resolution,
    }


def build_decision(policy):
    prefix = policy.get("release_prefix", "v")
    latest = latest_release_tag(prefix)
    if not latest:
        return {"decision": "hold", "reason": "no_prior_release_tag", "release": False}

    source_head_sha = git_commit("HEAD")
    head_msg = sh("git", "log", "-1", "--pretty=%B")
    if any(head_msg.startswith(p) for p in policy.get("generated_commit_prefixes", [])):
        return {
            "decision": "hold",
            "reason": "generated_release_commit_guard",
            "release": False,
            "latest_tag": latest,
            "source_head_sha": source_head_sha,
        }

    try:
        baseline = resolve_release_baseline(latest, policy, source_head_sha)
    except LineageError as exc:
        return {
            "decision": "hold",
            "reason": exc.reason,
            "release": False,
            "latest_tag": latest,
            "source_head_sha": source_head_sha,
        }
    lineage = _lineage_fields(baseline, source_head_sha)
    comparison_range = f"{baseline.source_baseline_sha}..{source_head_sha}"

    files = [path for path in sh("git", "diff", "--name-only", comparison_range).splitlines() if path]
    commits = sh("git", "log", "--format=%s%n%b", comparison_range) if files else ""
    ignored = policy.get("ignored_paths", [])
    relevant = [path for path in files if not starts_any(path, ignored)]
    if len(relevant) < policy.get("minimum_release_relevant_changes", 1):
        return {
            "decision": "hold",
            "reason": "no_release_relevant_delta",
            "release": False,
            **lineage,
            "changed_files": files,
        }

    runtime = any(starts_any(path, policy.get("runtime_paths", [])) for path in relevant)
    integration = any(starts_any(path, policy.get("integration_paths", [])) for path in relevant)
    governed_docs = any(starts_any(path, policy.get("governed_docs_paths", [])) for path in relevant)
    docs_only = all(
        path.endswith((".md", ".mdx", ".txt", ".json", ".yaml", ".yml")) or path.startswith("docs/")
        for path in relevant
    )

    text = commits.lower()
    rules = policy["release_rules"]
    level = "evidence"
    why = []
    human_required = False
    if any(signal.lower() in text for signal in rules["breaking"]["signals"]):
        level = "major"
        why.append("breaking-change signal")
        human_required = True
    elif any(signal.lower() in text for signal in rules["feature"]["signals"]) or runtime:
        level = "minor"
        why.append("new executable capability or runtime delta")
    elif any(signal.lower() in text for signal in rules["fix"]["signals"]):
        level = "patch"
        why.append("production fix/hardening delta")
    elif integration or governed_docs:
        level = "evidence"
        why.append("governed integration/version/evidence delta")
    elif docs_only and policy.get("docs_only_default") == "hold":
        return {
            "decision": "hold",
            "reason": "docs_only_non_governed",
            "release": False,
            **lineage,
            "changed_files": relevant,
        }
    else:
        level = "evidence"
        why.append("release-relevant bounded delta")

    if human_required and policy["gates"].get("d3_human_reserved", True):
        return {
            "decision": "hold",
            "reason": "d3_breaking_change_requires_human_authority",
            "release": False,
            **lineage,
            "changed_files": relevant,
            "recommended_bump": level,
        }

    current = parse_version(latest, prefix)
    nxt = bump(current, level)
    version = ".".join(map(str, nxt))
    tag = prefix + version
    scheme = "crownthrive_extended" if len(nxt) == 4 else "semver"
    return {
        "decision": "release",
        "release": True,
        **lineage,
        "version": version,
        "tag": tag,
        "version_scheme": scheme,
        "bump": level,
        "why": "; ".join(why),
        "changed_files": relevant,
        "commit_count": int(sh("git", "rev-list", "--count", comparison_range)),
        "target": "main",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    decision = build_decision(policy)
    Path(args.output).write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
