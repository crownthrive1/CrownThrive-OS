#!/usr/bin/env python3
"""Fail closed when the governed PentaDocs visual/mobile contract regresses."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs.json"
STYLE = ROOT / "style.css"

EXPECTED_THEME = "maple"
EXPECTED_NAME = "PentaDocs"
EXPECTED_COLORS = {
    "primary": "#7A1731",
    "light": "#D4AF37",
    "dark": "#4A0D1E",
}
EXPECTED_LOGO = {
    "light": "/logo/light.svg",
    "dark": "/logo/dark.svg",
}
EXPECTED_BACKGROUND = {
    "decoration": "gradient",
    "color": {"light": "#FCFBF9", "dark": "#09090B"},
}


def _get(mapping: Any, *path: str) -> Any:
    value = mapping
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def validate_repository(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    docs_path = root / DOCS.name
    style_path = root / STYLE.name

    if not docs_path.is_file():
        return ["missing docs.json"]
    try:
        config = json.loads(docs_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"invalid docs.json: {exc}"]

    exact_values = {
        "theme": (config.get("theme"), EXPECTED_THEME),
        "name": (config.get("name"), EXPECTED_NAME),
        "colors": (config.get("colors"), EXPECTED_COLORS),
        "logo": (config.get("logo"), EXPECTED_LOGO),
        "favicon": (config.get("favicon"), "/favicon.svg"),
        "fonts.family": (_get(config, "fonts", "family"), "Inter"),
        "icons.library": (_get(config, "icons", "library"), "fontawesome"),
        "appearance.default": (_get(config, "appearance", "default"), "system"),
        "appearance.strict": (_get(config, "appearance", "strict"), False),
        "interaction.drilldown": (_get(config, "interaction", "drilldown"), False),
        "styling.eyebrows": (_get(config, "styling", "eyebrows"), "section"),
        "styling.codeblocks": (_get(config, "styling", "codeblocks"), "system"),
        "background": (config.get("background"), EXPECTED_BACKGROUND),
    }
    for label, (actual, expected) in exact_values.items():
        if actual != expected:
            errors.append(f"{label} drifted: expected {expected!r}, observed {actual!r}")

    navbar = config.get("navbar")
    if not isinstance(navbar, dict):
        errors.append("navbar must remain configured")
    else:
        links = navbar.get("links")
        if not isinstance(links, list):
            errors.append("navbar.links must remain a list")
        else:
            required_links = {
                ("Ecosystem", "/ecosystem/map"),
                ("Pentas", "/pentas"),
                ("Developers", "/developers/overview"),
                ("CHLOM", "/chlom/overview"),
                ("Support", "mailto:contact@crownthrive.com"),
            }
            observed_links = {
                (item.get("label"), item.get("href"))
                for item in links
                if isinstance(item, dict)
            }
            missing = sorted(required_links - observed_links)
            if missing:
                errors.append(f"navbar lost required routes: {missing}")
        primary = navbar.get("primary")
        if primary != {
            "type": "button",
            "label": "Current State",
            "href": "/start-here/current-operational-state",
        }:
            errors.append("navbar primary action drifted")

    contextual = config.get("contextual")
    if contextual != {
        "options": ["copy", "view", "chatgpt", "mcp"],
        "display": "toc",
    }:
        errors.append("contextual tools drifted")

    for asset in (root / "logo/light.svg", root / "logo/dark.svg", root / "favicon.svg"):
        if not asset.is_file():
            errors.append(f"missing brand asset: {asset.relative_to(root)}")

    if not style_path.is_file():
        errors.append("missing style.css mobile-containment boundary")
        return errors

    try:
        css = style_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"style.css is not UTF-8: {exc}")
        return errors

    required_fragments = {
        "contract marker": "ct.pentadocs.presentation-contract.v2",
        "mobile breakpoint": "@media (max-width: 1023.98px)",
        "desktop sidebar selector": "#sidebar",
        "desktop article selector": "#content-area",
        "mobile trigger selector": "#mobile-nav",
        "mobile drawer selector": "#mobile-nav-content",
        "mobile trigger flow boundary": "position: relative !important",
        "sidebar paint removal": "transform: translateX(-200vw) !important",
        "drawer opacity boundary": "background-color: var(--ct-docs-surface) !important",
        "dark drawer opacity boundary": "background-color: var(--ct-docs-surface-dark) !important",
        "drawer scroll boundary": "overflow-y: auto !important",
        "drawer isolation": "contain: layout paint",
        "viewport overflow boundary": "overflow-x: clip",
    }
    for label, fragment in required_fragments.items():
        if fragment not in css:
            errors.append(f"style.css lost {label}: {fragment!r}")

    prohibited_patterns = {
        "transparent mobile drawer": re.compile(
            r"#mobile-nav-content\s*\{[^}]*background(?:-color)?\s*:\s*transparent",
            re.IGNORECASE | re.DOTALL,
        ),
        "fixed breadcrumb slab": re.compile(
            r"#mobile-nav\s*\{[^}]*position\s*:\s*fixed",
            re.IGNORECASE | re.DOTALL,
        ),
        "mobile desktop sidebar display": re.compile(
            r"@media\s*\(max-width:\s*1023\.98px\)[\s\S]*?#sidebar\s*\{[^}]*display\s*:\s*(?:block|flex|grid)",
            re.IGNORECASE,
        ),
    }
    for label, pattern in prohibited_patterns.items():
        if pattern.search(css):
            errors.append(f"style.css reintroduced {label}")

    return errors


def main() -> int:
    errors = validate_repository(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"PentaDocs presentation contract FAILED with {len(errors)} error(s).")
        return 1

    print(
        json.dumps(
            {
                "status": "PASS",
                "contract": "ct.pentadocs.presentation-contract.v2",
                "theme": EXPECTED_THEME,
                "brand_palette": EXPECTED_COLORS,
                "mobile_sidebar": "removed_below_1024px",
                "mobile_trigger": "bounded_normal_flow",
                "mobile_drawer": "opaque_isolated_scrollable",
                "anti_rollback": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
