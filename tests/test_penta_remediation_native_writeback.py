from pathlib import Path
import unittest


class PentaRemediationNativeWritebackTests(unittest.TestCase):
    def test_worker_preserves_pentapm_secret_but_uses_native_token_for_writeback(self) -> None:
        workflow = Path(".github/workflows/penta-remediation-worker-execution.yml").read_text(encoding="utf-8")
        wrapper = Path("scripts/penta_remediation_worker_execute_native.py").read_text(encoding="utf-8")
        self.assertIn('PENTA_PM_GITHUB_TOKEN: ${{ secrets.PENTA_PM_GITHUB_TOKEN }}', workflow)
        self.assertIn('GITHUB_TOKEN: ${{ github.token }}', workflow)
        self.assertIn('GH_TOKEN: ${{ github.token }}', workflow)
        self.assertIn('penta_remediation_worker_execute_native.py', workflow)
        self.assertIn('os.environ["PENTA_PM_GITHUB_TOKEN"] = native', wrapper)
        self.assertIn('return worker.main()', wrapper)


if __name__ == "__main__":
    unittest.main()
