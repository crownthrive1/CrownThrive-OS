import unittest

from scripts import penta_pr_metadata_converge_v2 as converge


class PentaPrMetadataConvergeV2Tests(unittest.TestCase):
    def issue(self, number, body, title="[PentaDevelopment] PR #42: test"):
        return {
            "number": number,
            "title": title,
            "body": body,
            "state": "open",
        }

    def test_recognizes_legacy_gate_awareness_metadata(self):
        item = self.issue(
            100,
            "Development PR: #42\n\n"
            "Automatically created by Penta PR Gate Awareness because every PR "
            "must carry an explicit Development linkage.",
        )
        self.assertTrue(converge.recognized_metadata_only(item, 42))

    def test_terminal_reference_wins_canonical_selection(self):
        old = self.issue(
            100,
            "<!-- penta-development-child:pr-42 -->\nDevelopment PR: #42",
        )
        terminal = self.issue(
            101,
            "Development PR: #42\n"
            "PentaPM created this bounded metadata/evidence unit",
        )
        pr = {"number": 42, "body": "Closes #101"}
        selected = converge.choose_canonical(pr, [old, terminal])
        self.assertEqual(selected["number"], 101)

    def test_old_child_marker_beats_unbound_metadata(self):
        unbound = self.issue(
            100,
            "Development PR: #42\n"
            "PentaPM created this bounded metadata/evidence unit",
        )
        child = self.issue(
            101,
            "<!-- penta-development-child:pr-42 -->\nDevelopment PR: #42",
        )
        selected = converge.choose_canonical({"number": 42, "body": ""}, [unbound, child])
        self.assertEqual(selected["number"], 101)

    def test_existing_engineering_terminal_reference_is_not_replaced(self):
        body = "Closes #900"
        terminal = converge.referenced_numbers(body, converge.TERMINAL_RE)
        self.assertEqual(terminal, [900])


if __name__ == "__main__":
    unittest.main()
