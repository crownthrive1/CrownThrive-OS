from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "pentarelease" / "enrich_release_intelligence.py"
MINTIGNORE = ROOT / ".mintignore"
LATEST = ROOT / "pentarelease" / "latest.mdx"


def test_pentadocs_release_markers_are_mdx_safe() -> None:
    source = GENERATOR.read_text(encoding="utf-8")
    assert 'RELEASE_START = "{/* pentarelease:comprehensive-release:start */}"' in source
    assert 'RELEASE_END = "{/* pentarelease:comprehensive-release:end */}"' in source
    assert 'START = "<!-- pentarelease:managed-release-surface:start -->"' in source
    assert 'END = "<!-- pentarelease:managed-release-surface:end -->"' in source


def test_github_only_surfaces_are_excluded_from_mintlify_parser() -> None:
    ignored = {line.strip() for line in MINTIGNORE.read_text(encoding="utf-8").splitlines()}
    for path in {"ABOUT_ME.md", "CODE_OF_CONDUCT.md", "FAQ.md", "PARTNERS.md"}:
        assert path in ignored


def test_current_latest_release_page_has_no_html_comprehensive_marker() -> None:
    latest = LATEST.read_text(encoding="utf-8")
    assert "{/* pentarelease:comprehensive-release:start */}" in latest
    assert "{/* pentarelease:comprehensive-release:end */}" in latest
    assert "<!-- pentarelease:comprehensive-release:" not in latest
    assert "v3.49.1.0" in latest
    assert "c1243dd4f79f8973d709f320599de3f8d12568529cf95c0642dd7ee1a5421c70" in latest
