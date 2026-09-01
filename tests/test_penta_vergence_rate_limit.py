import importlib.util
import pathlib
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "penta_vergence_reconciler.py"
SPEC = importlib.util.spec_from_file_location("penta_vergence_reconciler", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def pr(*, mergeable=True):
    return {
        "number": 7,
        "title": "safe candidate",
        "body": "",
        "draft": False,
        "base": {"sha": "base"},
        "head": {"sha": "head"},
        "mergeable": mergeable,
    }


class RateLimitedChecks:
    def compare(self, base, head):
        return {"ahead_by": 1, "behind_by": 0}

    def checks(self, sha):
        raise module.GitHubRateLimit("GET", f"/commits/{sha}/check-runs", 403, "API rate limit exceeded", 9999999999)


class NonRateFailure:
    def compare(self, base, head):
        return {"ahead_by": 1, "behind_by": 0}

    def checks(self, sha):
        raise RuntimeError("provider returned a non-rate-limit authorization failure")


class OpenPrRateLimit:
    def open_prs(self):
        raise module.GitHubRateLimit("GET", "/pulls", 403, "API rate limit exceeded", 9999999999)


class CacheGitHub(module.GitHub):
    def __init__(self):
        super().__init__("crownthrive1/CrownThrive-OS", "test")
        self.calls = 0

    def request(self, method, path, body=None):
        self.calls += 1
        return {"check_runs": [{"name": "Governed Merge Gate", "status": "completed", "conclusion": "success"}]}


class PentaVergenceRateLimitTests(unittest.TestCase):
    def test_check_run_rate_limit_is_observe_only(self):
        decision = module.classify(RateLimitedChecks(), pr())
        self.assertEqual(decision.disposition, "OBSERVE_RATE_LIMIT")
        self.assertIsNone(decision.mutation)
        self.assertFalse(decision.provider_evidence["mutation_allowed"])
        self.assertEqual(decision.provider_evidence["authority_effect"], "none")

    def test_non_rate_limit_provider_failure_still_fails_closed(self):
        with self.assertRaises(RuntimeError):
            module.classify(NonRateFailure(), pr())

    def test_open_pr_rate_limit_returns_report_without_mutation(self):
        fake = OpenPrRateLimit()
        with mock.patch.object(module, "GitHub", return_value=fake):
            report = module.reconcile("crownthrive1/CrownThrive-OS", "token", True, 15)
        self.assertEqual(report["worker_state"], "OBSERVE_RATE_LIMIT")
        self.assertEqual(report["mutations"], 0)
        self.assertEqual(report["summary"]["OBSERVE_RATE_LIMIT"], 1)
        self.assertFalse(report["provider_evidence"]["mutation_allowed"])

    def test_check_reads_are_cached_per_exact_sha(self):
        gh = CacheGitHub()
        first = gh.checks("abc")
        second = gh.checks("abc")
        self.assertEqual(first, second)
        self.assertEqual(gh.calls, 1)


if __name__ == "__main__":
    unittest.main()
