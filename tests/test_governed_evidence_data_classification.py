from pathlib import Path
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("preflight_v2", SCRIPTS / "governed_current_pr_preflight_v2.py")
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_registered_help_center_transport_is_exact_neutral():
    policy = module.load_json(module.MANIFEST)
    contract = module.evidence_contract()
    for path in contract["registered_neutral_paths"]:
        assert module.deterministic_domains(path, policy, contract) == {"institutional_general"}


def test_material_data_vectors_do_not_become_neutral():
    policy = module.load_json(module.MANIFEST)
    contract = module.evidence_contract()
    cases = {
        "data/payments-ledger.json": "finance",
        "data/royalty-rates.json": "finance",
        "data/token-registry.json": "blockchain",
        "data/wallet-state.json": "blockchain",
        "data/license-grants.json": "rights",
        "data/rights-chain.json": "rights",
        "data/customer-records.json": "privacy",
        "data/privacy-export.json": "privacy",
        "data/localization-map.json": "localization",
        "data/country-routing.json": "localization",
    }
    for path, expected in cases.items():
        assert expected in module.deterministic_domains(path, policy, contract)


def test_unknown_data_and_name_spoof_fail_closed():
    policy = module.load_json(module.MANIFEST)
    contract = module.evidence_contract()
    fallback = set(module.CONSERVATIVE_FALLBACK_DOMAINS)
    assert module.deterministic_domains("data/unregistered.json", policy, contract) == fallback
    assert module.deterministic_domains(
        "data/help_center_article_manifest.v1.bundle.json.backup", policy, contract
    ) == fallback
