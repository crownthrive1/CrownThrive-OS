import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pentarelease" / "decide.py"
POLICY = ROOT / ".pentarelease" / "policy.json"
SPEC = importlib.util.spec_from_file_location("pentarelease_decide", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _run_decision(monkeypatch, tmp_path, head_message, changed_file="scripts/pentarelease/decide.py"):
    output = tmp_path / "decision.json"

    def fake_sh(*args):
        if args[:3] == ("git", "tag", "--sort=-version:refname"):
            return "v3.49.0.3\nv3.49.0.2"
        if args[:4] == ("git", "log", "-1", "--pretty=%B"):
            return head_message
        if args[:3] == ("git", "diff", "--name-only"):
            return changed_file
        if args[:3] == ("git", "log", "--format=%s%n%b"):
            return head_message
        if args[:3] == ("git", "rev-list", "--count"):
            return "1"
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(MODULE, "sh", fake_sh)
    monkeypatch.setattr(
        sys,
        "argv",
        ["decide.py", "--policy", str(POLICY), "--output", str(output)],
    )
    MODULE.main()
    return json.loads(output.read_text(encoding="utf-8"))


def test_release_intelligence_sync_head_is_hold(monkeypatch, tmp_path):
    decision = _run_decision(
        monkeypatch,
        tmp_path,
        "PentaRelease release intelligence v3.49.0.3 (#1016)",
        "README.md",
    )
    assert decision["release"] is False
    assert decision["reason"] == "generated_release_commit_guard"
    assert decision["latest_tag"] == "v3.49.0.3"


def test_real_fix_after_sync_remains_release_eligible(monkeypatch, tmp_path):
    decision = _run_decision(
        monkeypatch,
        tmp_path,
        "fix(pentarelease): repair release provider readback",
    )
    assert decision["release"] is True
    assert decision["bump"] == "patch"
    assert decision["tag"] == "v3.49.1.0"
