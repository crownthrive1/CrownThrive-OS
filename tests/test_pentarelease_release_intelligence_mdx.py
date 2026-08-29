import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pentarelease" / "enrich_release_intelligence.py"
SPEC = importlib.util.spec_from_file_location("pentarelease_release_intelligence", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_dimension_summary_is_deterministic_and_mdx_safe():
    summary = MODULE.dimension_summary(
        {
            "story_alignment": 20,
            "brand_safety": 20,
            "identity_fit": 20,
            "legacy_impact": 20,
            "community_value": 20,
        }
    )
    assert summary == (
        "brand_safety=20, community_value=20, identity_fit=20, "
        "legacy_impact=20, story_alignment=20"
    )
    assert "{" not in summary
    assert "}" not in summary


def test_current_release_faq_does_not_embed_raw_json_expression():
    faq = (Path(__file__).resolve().parents[1] / "pentarelease" / "faq.mdx").read_text(encoding="utf-8")
    cie_line = next(line for line in faq.splitlines() if line.startswith("PASS —") and "Dimension scores:" in line)
    assert "Dimension scores: `" in cie_line
    assert '{"brand_safety"' not in cie_line
