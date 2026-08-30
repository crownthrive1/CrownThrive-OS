from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_function_tests.py"


class FunctionTestRunnerTests(unittest.TestCase):
    def run_module(self, source: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "test_sample.py"
            path.write_text(textwrap.dedent(source), encoding="utf-8")
            relative = path.relative_to(ROOT)
            return subprocess.run(
                [sys.executable, "-B", str(RUNNER), str(relative)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

    def test_valid_zero_argument_function_executes(self):
        result = self.run_module(
            """
            def test_runs():
                assert True
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("passed=1 failed=0", result.stdout)

    def test_parameterized_async_and_generator_tests_fail_discovery(self):
        result = self.run_module(
            """
            def test_runs():
                assert True

            def test_parameterized(value):
                assert value

            async def test_async():
                return None

            def test_generator():
                yield 1
            """
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("test_parameterized", result.stderr)
        self.assertIn("test_async", result.stderr)
        self.assertIn("test_generator", result.stderr)
        self.assertIn("passed=1 failed=3", result.stdout)

    def test_assertion_failure_propagates_nonzero(self):
        result = self.run_module(
            """
            def test_fails():
                assert False, "expected failure"
            """
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("test_fails", result.stderr)
        self.assertIn("passed=0 failed=1", result.stdout)


if __name__ == "__main__":
    unittest.main()
