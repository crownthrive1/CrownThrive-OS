from runtime.penta_hold_remediation import CheckFailure
from scripts.penta_remediation_bridge import PentaCrawler, PentaFlows, PentaHelper


class FakeGH:
    repo = "crownthrive1/CrownThrive-OS"

    def __init__(self):
        self.gets = {}
        self.puts = []
        self.posts = []

    def get(self, path):
        return self.gets[path]

    def put(self, path, body):
        self.puts.append((path, body))
        return {"message": "Updating pull request branch."}

    def post(self, path, body):
        self.posts.append((path, body))
        return {}


def test_flows_fans_one_governed_gate_into_multiple_root_cause_domains():
    failure = CheckFailure(
        "Governed Merge Gate",
        "failure",
        "family-census: penta.immune child-member missing; Supabase migration-count drift and provider custody stale",
    )
    plans, escalations = PentaFlows().route(
        repo="crownthrive1/CrownThrive-OS",
        number=551,
        head_sha="a" * 40,
        failures=[failure],
        attempts={},
    )
    assert escalations == []
    assert {plan.route_id for plan in plans} == {"family-interoperability", "provider-convergence"}
    assert {plan.owner_penta for plan in plans} == {"PentaInterOps", "PentaBind"}
    assert len({plan.fingerprint for plan in plans}) == 2


def test_route_attempts_are_durable_by_exact_head_and_route():
    attempts = {}
    failure = CheckFailure("Penta Runtime Suite", "failure", "family-census mismatch")
    flow = PentaFlows()
    first, _ = flow.route(repo="crownthrive1/CrownThrive-OS", number=551, head_sha="a" * 40, failures=[failure], attempts=attempts)
    second, _ = flow.route(repo="crownthrive1/CrownThrive-OS", number=551, head_sha="a" * 40, failures=[failure], attempts=attempts)
    assert first[0].attempt == 1
    assert second[0].attempt == 2
    changed, _ = flow.route(repo="crownthrive1/CrownThrive-OS", number=551, head_sha="b" * 40, failures=[failure], attempts=attempts)
    assert changed[0].attempt == 1


def test_unclassified_failure_routes_to_pentatriage_without_arbitrary_edit():
    plans, escalations = PentaFlows().route(
        repo="crownthrive1/CrownThrive-OS",
        number=1,
        head_sha="a" * 40,
        failures=[CheckFailure("Novel Gate", "failure", "unknown failure")],
        attempts={},
    )
    assert plans == []
    assert escalations == [{"check": "Novel Gate", "reason": "unclassified", "owner": "PentaTriage"}]


def test_source_convergence_uses_expected_head_and_never_force_pushes():
    gh = FakeGH()
    helper = PentaHelper(gh)
    pull = {
        "number": 551,
        "head": {"sha": "h" * 40, "repo": {"full_name": gh.repo}},
        "base": {"sha": "o" * 40, "ref": "main", "repo": {"full_name": gh.repo}},
    }
    result = helper.converge_source(pull, current_base_sha="n" * 40)
    assert result["status"] == "DISPATCHED"
    assert gh.puts == [
        (f"/repos/{gh.repo}/pulls/551/update-branch", {"expected_head_sha": "h" * 40})
    ]


def test_cross_repository_pr_is_never_mutated_by_source_convergence():
    gh = FakeGH()
    helper = PentaHelper(gh)
    pull = {
        "number": 551,
        "head": {"sha": "h" * 40, "repo": {"full_name": "someone/fork"}},
        "base": {"sha": "o" * 40, "ref": "main", "repo": {"full_name": gh.repo}},
    }
    result = helper.converge_source(pull, current_base_sha="n" * 40)
    assert result == {"action": "source_convergence", "status": "HOLD", "reason": "fork_or_cross_repo"}
    assert gh.puts == []


def test_provider_refresh_dispatches_authoritative_control_plane_once_per_head_signal():
    gh = FakeGH()
    helper = PentaHelper(gh)
    pull = {"base": {"ref": "main"}}
    first = helper.refresh_provider_evidence(pull, already_dispatched=False)
    second = helper.refresh_provider_evidence(pull, already_dispatched=True)
    assert first["status"] == "DISPATCHED"
    assert second["status"] == "NOOP"
    assert gh.posts == [
        (f"/repos/{gh.repo}/actions/workflows/penta-provider-control-plane.yml/dispatches", {"ref": "main"})
    ]


def test_crawler_keeps_only_latest_check_context_and_failed_conclusions():
    gh = FakeGH()
    sha = "a" * 40
    gh.gets[f"/repos/{gh.repo}/pulls/551"] = {"state": "open", "head": {"sha": sha}}
    gh.gets[f"/repos/{gh.repo}/commits/{sha}/check-runs?per_page=100"] = {
        "check_runs": [
            {"id": 1, "name": "Penta Runtime Suite", "app": {"slug": "github-actions"}, "status": "completed", "conclusion": "failure", "output": {"summary": "old"}},
            {"id": 2, "name": "Penta Runtime Suite", "app": {"slug": "github-actions"}, "status": "completed", "conclusion": "success", "output": {}},
            {"id": 3, "name": "Governed Merge Gate", "app": {"slug": "github-actions"}, "status": "completed", "conclusion": "failure", "output": {"summary": "provider custody stale"}},
        ]
    }
    _, failures = PentaCrawler(gh).crawl(551)
    assert len(failures) == 1
    assert failures[0].name == "Governed Merge Gate"
