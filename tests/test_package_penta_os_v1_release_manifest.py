import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


packager = load_module(
    "penta_os_v15_release_manifest_packager",
    ROOT / "scripts/package_penta_os_v1.py",
)


class PentaOSV15ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(
            (ROOT / "releases/penta-os-v1.5.0/MANIFEST.json").read_text(encoding="utf-8")
        )

    def assert_tamper_fails(self, manifest, message="release manifest"):
        with self.assertRaisesRegex(packager.PackageError, message):
            packager.validate_release_manifest(manifest)

    def test_current_release_manifest_satisfies_exact_contract(self):
        packager.validate_release_manifest(self.manifest)

    def test_identity_and_lifecycle_tampering_fail_closed(self):
        protected_fields = (
            "schema",
            "release_id",
            "component_id",
            "canonical_name",
            "version",
            "version_scheme",
            "compatibility_line",
            "supersedes",
            "tag",
            "release_state",
            "certification_state",
            "lifecycle_intent",
        )
        for field in protected_fields:
            with self.subTest(field=field):
                tampered = copy.deepcopy(self.manifest)
                tampered[field] = "tampered"
                self.assert_tamper_fails(tampered, field)

    def test_target_ref_must_be_present_and_null(self):
        for value in ("main", "0" * 40):
            with self.subTest(value=value):
                tampered = copy.deepcopy(self.manifest)
                tampered["target_ref"] = value
                self.assert_tamper_fails(tampered, "target_ref must remain null")
        missing = copy.deepcopy(self.manifest)
        del missing["target_ref"]
        self.assert_tamper_fails(missing, "target_ref must remain null")

    def test_source_repository_and_refs_are_exact(self):
        protected_fields = (
            "repository",
            "exact_commit_sha_required",
            "registry_ref",
            "software_manifest_ref",
            "package_builder_ref",
        )
        for field in protected_fields:
            with self.subTest(field=field):
                tampered = copy.deepcopy(self.manifest)
                tampered["source"][field] = "tampered"
                self.assert_tamper_fails(tampered, "source repository/ref contract drift")
        extra = copy.deepcopy(self.manifest)
        extra["source"]["unreviewed_ref"] = "README.md"
        self.assert_tamper_fails(extra, "source repository/ref contract drift")

    def test_expected_artifact_names_are_exact(self):
        fixtures = []
        renamed = copy.deepcopy(self.manifest)
        renamed["expected_artifacts"][0] = "tampered.zip"
        fixtures.append(renamed)
        missing = copy.deepcopy(self.manifest)
        missing["expected_artifacts"].pop()
        fixtures.append(missing)
        extra = copy.deepcopy(self.manifest)
        extra["expected_artifacts"].append("unreviewed.asset")
        fixtures.append(extra)
        reordered = copy.deepcopy(self.manifest)
        reordered["expected_artifacts"].reverse()
        fixtures.append(reordered)
        for index, tampered in enumerate(fixtures):
            with self.subTest(index=index):
                self.assert_tamper_fails(tampered, "exact five governed artifact names")

    def test_provider_readback_must_remain_held_with_requirements(self):
        advanced = copy.deepcopy(self.manifest)
        advanced["provider_readback"]["state"] = "PASS"
        self.assert_tamper_fails(advanced, "provider_readback.state must remain HOLD")

        empty = copy.deepcopy(self.manifest)
        empty["provider_readback"]["required"] = []
        self.assert_tamper_fails(empty, "provider_readback.required")

    def test_certification_receipt_must_remain_unproduced_and_bound(self):
        produced = copy.deepcopy(self.manifest)
        produced["certification_receipt"]["state"] = "PRODUCED"
        self.assert_tamper_fails(
            produced, "certification_receipt.state must remain NOT_PRODUCED"
        )

        embedded = copy.deepcopy(self.manifest)
        embedded["certification_receipt"]["separate_from_deterministic_archives"] = False
        self.assert_tamper_fails(embedded, "must remain separate")

        empty = copy.deepcopy(self.manifest)
        empty["certification_receipt"]["required_bindings"] = []
        self.assert_tamper_fails(empty, "certification_receipt.required_bindings")

    def test_release_blockers_must_be_nonempty_unique_strings(self):
        for blockers in ([], [""], ["duplicate", "duplicate"], [7]):
            with self.subTest(blockers=blockers):
                tampered = copy.deepcopy(self.manifest)
                tampered["release_blockers"] = blockers
                self.assert_tamper_fails(tampered, "release_blockers")


if __name__ == "__main__":
    unittest.main()
