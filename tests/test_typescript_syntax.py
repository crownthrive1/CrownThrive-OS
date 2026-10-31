"""Exercise the real Node syntax gate without executing endpoint code."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check_typescript_syntax.mjs"


class TypeScriptSyntaxTests(unittest.TestCase):
    def check_source(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.ts"
            path.write_text(source, encoding="utf-8")
            return subprocess.run(
                ["node", str(CHECKER), str(path)],
                capture_output=True, text=True, timeout=20,
            )

    def test_valid_typescript_is_not_executed_or_imported(self):
        result = self.check_source('''
import { unavailable } from "npm:nonexistent-validation-fixture";
interface Payload { value: number }
const payload: Payload = { value: 1 };
throw new Error("SOURCE_MUST_NOT_EXECUTE");
Deno.serve(() => new Response(String(payload.value)));
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_source_fails_closed(self):
        for source in (
            "const value: = 1;",  # malformed TypeScript
            "const value = ;",  # malformed JavaScript
            "const duplicate = 1; const duplicate = 2;",  # binding error
            "enum Value { First }",  # non-erasable TypeScript
        ):
            with self.subTest(source=source):
                result = self.check_source(source)
                self.assertNotEqual(result.returncode, 0)

    def test_real_ingest_source_passes_without_execution(self):
        result = subprocess.run(
            ["node", str(CHECKER), str(ROOT / "supabase/functions/pentafabric-ingest/index.ts")],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_source_fails_closed(self):
        result = subprocess.run(
            ["node", str(CHECKER)], capture_output=True, text=True, timeout=20,
        )
        self.assertNotEqual(result.returncode, 0)
