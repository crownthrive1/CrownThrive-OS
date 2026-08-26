#!/usr/bin/env python3
"""Validate and migrate the audience-aware PentaDocs MDX page standard.

The implementation is intentionally standard-library only.  It treats fenced
code as examples rather than live MDX, derives a deterministic audience/profile
from the current navigation location, and never infers runtime, legal, rights,
provider, or production state from a page being present in navigation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable


STANDARD_VERSION = "1.0.0"
PROFILE_SCHEMA = "crownthrive.pentadocs.page-profiles/v1"
PROFILE_PATH = Path("data/documentation/pentadocs-page-profiles.v1.json")
UNLISTED_DISPOSITIONS_PATH = Path(
    "developers/manifests/pentadocs-unlisted-page-dispositions.v1.json"
)
LEGACY_ORIENTATION_MARKER = "{/* pentadocs:audience-orientation:v1 */}"
ORIENTATION_MARKER = "{/* pentadocs:audience-orientation:v2 */}"
ORIENTATION_INPUT_SCHEMA = "crownthrive.pentadocs.audience-orientation-input/v2"
ORIENTATION_MODE_MANAGED = "managed_v2"
ORIENTATION_MODE_CUSTOM = "custom"
ORIENTATION_MODE_REDIRECT = "redirect_exempt"
ORIENTATION_END_MARKER = "{/* /pentadocs:audience-orientation:v2 */}"
HISTORICAL_BOUNDARY = "dated context, not current operating authority"
NON_CERTIFICATION_BOUNDARY = (
    "Documentation state is editorial posture only; it does not certify runtime, "
    "deployment, legal, rights, financial, provider, production, release, security, "
    "or operational status."
)
UNRESOLVED_REASON = (
    "no explicit page-level editorial acceptance state was declared in the migrated source"
)
UNRESOLVED_EVIDENCE = "an accepted governing source or accountable-owner attestation"
UNRESOLVED_REVIEW_ROLE = "PentaDocs governance"
UNRESOLVED_REVIEW_TRIGGER = "next material edit or source reconciliation"

REQUIRED_FRONTMATTER = (
    "title",
    "description",
    "standard_version",
    "primary_audience",
    "page_type",
    "content_state",
)

ALLOWED_AUDIENCES = {
    "executive",
    "public",
    "operator",
    "developer",
    "rights_support",
    "historical",
}

ALLOWED_PAGE_TYPES = {
    "orientation",
    "doctrine",
    "registry",
    "reference",
    "status",
    "workflow",
    "runbook",
    "standard",
    "support",
    "how_to",
    "policy",
    "legal",
    "developer",
    "changelog",
    "historical_record",
    "redirect",
}

ALLOWED_CONTENT_STATES = {
    "current",
    "current_with_holds",
    "candidate",
    "historical",
    "superseded",
    "unresolved",
}

UNLISTED_DISPOSITION_CATEGORIES = {
    "historical_change_evidence",
    "certification_evidence",
    "generated_build_evidence",
    "specialist_reconciliation_evidence",
    "operational_reference_direct_link",
}

# These are source/disposition classifications, never operational promotions.
# Explicit valid frontmatter remains authoritative over every migration default.
UNLISTED_PROFILE_OVERRIDES: dict[str, tuple[str, str, str]] = {
    "developers/runbooks/chlom-agentic-foundry-production-activation": (
        "operator",
        "runbook",
        "unresolved",
    ),
    "commerce/thriveevergreen-production-fabric": (
        "historical",
        "historical_record",
        "superseded",
    ),
    "developers/thriveevergreen-production-v2": (
        "historical",
        "historical_record",
        "superseded",
    ),
    "developers/crown-credits-production-v1": (
        "historical",
        "historical_record",
        "superseded",
    ),
    "technology/ct-p299-machine-hard-exit-and-phase3-bootstrap": (
        "historical",
        "historical_record",
        "historical",
    ),
    "commerce/production-hybrid-commerce-convergence-2026-08-23": (
        "historical",
        "historical_record",
        "historical",
    ),
    "chlom/insights/inside-chlom-architecture-for-support-technical": (
        "rights_support",
        "support",
        "unresolved",
    ),
    "security/chlom-wallet-continuity-penta-v2-threat-model": (
        "developer",
        "policy",
        "unresolved",
    ),
}

ROLE_LINKS: dict[str, tuple[tuple[str, str], ...]] = {
    "executive": (
        ("Current operational state", "/start-here/current-operational-state"),
        ("Governance stack", "/governance/governance-stack"),
        ("Source authority hierarchy", "/knowledge/source-authority-hierarchy"),
        ("Operating principles", "/start-here/operating-principles"),
    ),
    "public": (
        ("Start here", "/start-here/orientation"),
        ("Ecosystem map", "/ecosystem/map"),
        ("Current operational state", "/start-here/current-operational-state"),
        ("Source authority hierarchy", "/knowledge/source-authority-hierarchy"),
    ),
    "operator": (
        ("Operating principles", "/start-here/operating-principles"),
        ("Permissions and approvals", "/automation/permissions-and-approval-gates"),
        ("Evidence and proof standard", "/standards/evidence-claims-and-proof-standard"),
        ("Source authority hierarchy", "/knowledge/source-authority-hierarchy"),
    ),
    "developer": (
        ("Developer platform", "/developers/overview"),
        ("API integration standards", "/technology/api-integration-standards"),
        ("Product release workflow", "/workflows/product-release"),
        ("Source authority hierarchy", "/knowledge/source-authority-hierarchy"),
    ),
    "rights_support": (
        ("Support operating model", "/support/support-operating-model"),
        ("Rights and AI provenance", "/governance/rights-and-ai-provenance"),
        ("Evidence and proof standard", "/standards/evidence-claims-and-proof-standard"),
        ("Source authority hierarchy", "/knowledge/source-authority-hierarchy"),
    ),
    "historical": (
        ("Current operational state", "/start-here/current-operational-state"),
        ("Source authority hierarchy", "/knowledge/source-authority-hierarchy"),
        ("Historical context boundary", "/knowledge/historical-context-boundary"),
        ("Governance stack", "/governance/governance-stack"),
    ),
}

UNRESOLVED_GOVERNING_LINKS: tuple[tuple[str, str], ...] = (
    (
        "Documentation source governance",
        "/standards/documentation-source-of-truth-and-autonomous-governance",
    ),
    ("Institutional record standard", "/standards/record-and-format-standard"),
)

CALLOUT_BY_AUDIENCE = {
    "executive": "Info",
    "public": "Info",
    "operator": "Note",
    "developer": "Note",
    "rights_support": "Info",
    "historical": "Warning",
}

ALLOWED_ORIENTATION_CALLOUTS = {"Info", "Note", "Warning"}

AUDIENCE_LABEL = {
    "executive": "executive and governance readers",
    "public": "public and community readers",
    "operator": "operators and administrators",
    "developer": "builders and integrators",
    "rights_support": "support, rights, and licensing readers",
    "historical": "governance reviewers and researchers",
}

PAGE_TYPE_LABEL = {
    "orientation": "orientation",
    "doctrine": "doctrine page",
    "registry": "registry",
    "reference": "reference",
    "status": "status record",
    "workflow": "workflow",
    "runbook": "runbook",
    "standard": "standard",
    "support": "support page",
    "how_to": "how-to guide",
    "policy": "policy page",
    "legal": "legal and rights reference",
    "developer": "developer reference",
    "changelog": "dated change record",
    "historical_record": "historical record",
    "redirect": "compatibility redirect",
}

FENCE_START_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(?:[^`~].*)?$")
H1_RE = re.compile(r"^[ \t]{0,3}#(?!#)[ \t]+\S")
H1_REWRITE_RE = re.compile(r"^([ \t]{0,3})#([ \t]+)")
ATX_HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+\S")
CARDGROUP_RE = re.compile(r"(<\s*/?\s*)CardGroup(\b)")
FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_.:-]+)\s*:\s*(.*?)\s*$")
MARKDOWN_LINK_RE = re.compile(
    r"(?<!!)\[[^\]]+\]\(\s*(?:<([^>]+)>|([^\s)]+))",
    flags=re.MULTILINE,
)
HREF_RE = re.compile(r"\bhref\s*=\s*[\"']([^\"']+)[\"']")
DECORATIVE_IMAGE_MARKER = "{/* pentadocs:decorative-image */}"
MARKDOWN_IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\(\s*(?:<[^>]+>|[^\s)]+)"
    r"(?:\s+[\"'][^\"']*[\"'])?\s*\)",
    flags=re.MULTILINE,
)
JSX_IMAGE_RE = re.compile(r"<(?P<tag>img|Image)\b(?P<attrs>[^>]*)>", flags=re.DOTALL)
MEDIA_REVIEW_RE = re.compile(r"<(?:Video|Embed|iframe)\b", flags=re.IGNORECASE)

# Only tags with documented paired-block semantics are balanced.  Generic JSX
# and HTML are deliberately outside this gate.  Icon, Badge, Color, Image, and
# Tree.* leaf forms are allowed to self-close and are not treated as paired
# blocks.
KNOWN_PAIRED_MINTLIFY_COMPONENTS = frozenset(
    {
        "Accordion",
        "AccordionGroup",
        "Card",
        "Check",
        "CodeGroup",
        "Columns",
        "Danger",
        "Expandable",
        "FileTree",
        "Frame",
        "Info",
        "Note",
        "ParamField",
        "Prompt",
        "RequestExample",
        "ResponseExample",
        "ResponseField",
        "Step",
        "Steps",
        "Tab",
        "Tabs",
        "Tip",
        "Update",
        "Warning",
    }
)
MINTLIFY_TAG_RE = re.compile(
    r"<\s*(?P<closing>/)?\s*(?P<tag>[A-Za-z][A-Za-z0-9.]*)\b"
    r"(?P<attrs>[^>]*)>",
    flags=re.DOTALL,
)
INLINE_CODE_RE = re.compile(r"(?P<ticks>`+)(?P<content>.*?)(?P=ticks)", flags=re.DOTALL)
MDX_COMMENT_RE = re.compile(r"\{/\*.*?\*/\}", flags=re.DOTALL)


@dataclass(frozen=True)
class Frontmatter:
    raw: str
    values: dict[str, str]
    duplicate_keys: tuple[str, ...]


@dataclass(frozen=True)
class PageProfile:
    route: str
    path: str
    navigation_context: tuple[str, ...]
    primary_audience: str
    page_type: str
    content_state: str
    orientation_component: str
    role_links: tuple[str, ...]
    orientation_mode: str = ORIENTATION_MODE_MANAGED
    orientation_input_sha256: str | None = None
    orientation_render_sha256: str | None = None
    governance_scope: str = "navigation"
    disposition: str | None = None
    redirect_to: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "route": self.route,
            "path": self.path,
            "navigation_context": list(self.navigation_context),
            "primary_audience": self.primary_audience,
            "page_type": self.page_type,
            "content_state": self.content_state,
            "orientation_component": self.orientation_component,
            "role_links": list(self.role_links),
            "orientation_mode": self.orientation_mode,
            "governance_scope": self.governance_scope,
        }
        if self.orientation_input_sha256 is not None:
            result["orientation_input_sha256"] = self.orientation_input_sha256
        if self.orientation_render_sha256 is not None:
            result["orientation_render_sha256"] = self.orientation_render_sha256
        if self.disposition is not None:
            result["disposition"] = self.disposition
        if self.redirect_to is not None:
            result["redirect_to"] = self.redirect_to
        return result


def split_frontmatter(text: str) -> tuple[str, str] | None:
    if not text.startswith("---\n"):
        return None
    closing = text.find("\n---", 4)
    if closing == -1:
        return None
    return text[4:closing], text[closing + 4 :].lstrip("\r\n")


def decode_scalar(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
        if value[0] == "\"":
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                return value[1:-1]
            return str(decoded)
        return value[1:-1].replace("''", "'")
    return value


def parse_frontmatter(raw: str) -> Frontmatter:
    values: dict[str, str] = {}
    seen: Counter[str] = Counter()
    for line in raw.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#"):
            continue
        match = FRONTMATTER_KEY_RE.match(line)
        if not match:
            continue
        key = match.group(1)
        seen[key] += 1
        values[key] = decode_scalar(match.group(2))
    return Frontmatter(
        raw=raw,
        values=values,
        duplicate_keys=tuple(sorted(key for key, count in seen.items() if count > 1)),
    )


def iter_navigation_pages(
    node: Any, context: tuple[str, ...] = ()
) -> Iterable[tuple[str, tuple[str, ...]]]:
    if isinstance(node, str):
        yield node.strip("/"), context
        return
    if isinstance(node, list):
        for item in node:
            yield from iter_navigation_pages(item, context)
        return
    if not isinstance(node, dict):
        return

    label = node.get("tab") or node.get("group")
    next_context = context + ((str(label),) if label else ())
    for key in ("pages", "groups", "tabs", "dropdowns", "products", "versions", "languages"):
        if key in node:
            yield from iter_navigation_pages(node[key], next_context)


def navigation_pages(docs: dict[str, Any]) -> list[tuple[str, tuple[str, ...]]]:
    navigation = docs.get("navigation", {})
    if not isinstance(navigation, dict):
        return []
    if navigation.get("groups"):
        primary: Any = navigation["groups"]
    elif navigation.get("pages"):
        primary = navigation["pages"]
    else:
        primary = navigation
    return list(iter_navigation_pages(primary))


def load_governed_unlisted_pages(
    root: Path,
    navigated_routes: set[str],
) -> list[tuple[str, tuple[str, ...], str]]:
    path = root / UNLISTED_DISPOSITIONS_PATH
    if not path.is_file():
        raise ValueError(
            f"missing governed unlisted-page disposition manifest: {UNLISTED_DISPOSITIONS_PATH}"
        )
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {UNLISTED_DISPOSITIONS_PATH}: {exc}") from exc
    if manifest.get("schema_version") != "1.0.0":
        raise ValueError(f"{UNLISTED_DISPOSITIONS_PATH}: schema_version must remain 1.0.0")
    dispositions = manifest.get("dispositions")
    if not isinstance(dispositions, dict) or set(dispositions) != UNLISTED_DISPOSITION_CATEGORIES:
        raise ValueError(f"{UNLISTED_DISPOSITIONS_PATH}: disposition categories drifted")

    records: list[tuple[str, tuple[str, ...], str]] = []
    seen: set[str] = set()
    for category in sorted(UNLISTED_DISPOSITION_CATEGORIES):
        paths = dispositions.get(category)
        if not isinstance(paths, list) or any(not isinstance(item, str) for item in paths):
            raise ValueError(
                f"{UNLISTED_DISPOSITIONS_PATH}: {category} must be a string list"
            )
        for item in paths:
            clean = item.strip("/")
            suffix = Path(clean).suffix
            route = clean[: -len(suffix)] if suffix in {".md", ".mdx"} else clean
            if route in seen:
                raise ValueError(f"duplicate governed unlisted route: {route}")
            if route in navigated_routes:
                raise ValueError(f"governed unlisted route is also navigated: {route}")
            seen.add(route)
            records.append(
                (
                    route,
                    ("Governed unlisted", category.replace("_", " ")),
                    category,
                )
            )
    return records


def route_to_path(root: Path, route: str) -> Path:
    clean = route.split("#", 1)[0].split("?", 1)[0].strip("/")
    candidate = root / clean
    if candidate.suffix not in {".md", ".mdx"}:
        candidate = candidate.with_suffix(".mdx")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"navigation route escapes repository root: {route}")
    return candidate


def redirect_map(docs: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in docs.get("redirects", []):
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        destination = item.get("destination")
        if isinstance(source, str) and isinstance(destination, str):
            result[source.strip("/")] = destination
    return result


def transform_outside_fences(text: str, transform: Callable[[str], str]) -> str:
    lines = text.splitlines(keepends=True)
    in_fence = False
    fence_char = ""
    fence_length = 0
    output: list[str] = []

    for line in lines:
        logical = line.rstrip("\r\n")
        stripped = logical.lstrip(" \t")
        if not in_fence:
            match = FENCE_START_RE.match(logical)
            if match:
                token = match.group(1)
                in_fence = True
                fence_char = token[0]
                fence_length = len(token)
                output.append(line)
                continue
            output.append(transform(line))
            continue

        closing = re.match(rf"^[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*$", stripped)
        output.append(line)
        if closing:
            in_fence = False
            fence_char = ""
            fence_length = 0
    return "".join(output)


def outside_fence_text(text: str) -> str:
    return _mask_fences(text)


def _mask_fences(text: str) -> str:
    lines = text.splitlines(keepends=True)
    in_fence = False
    fence_char = ""
    fence_length = 0
    output: list[str] = []
    for line in lines:
        logical = line.rstrip("\r\n")
        stripped = logical.lstrip(" \t")
        if not in_fence:
            match = FENCE_START_RE.match(logical)
            if match:
                token = match.group(1)
                in_fence = True
                fence_char = token[0]
                fence_length = len(token)
                output.append("\n" if line.endswith("\n") else "")
            else:
                output.append(line)
            continue
        closing = re.match(rf"^[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*$", stripped)
        output.append("\n" if line.endswith("\n") else "")
        if closing:
            in_fence = False
            fence_char = ""
            fence_length = 0
    return "".join(output)


def _mask_match_preserve_newlines(match: re.Match[str]) -> str:
    return "".join("\n" if character == "\n" else " " for character in match.group(0))


def mask_inline_code(text: str) -> str:
    """Mask inline code without disturbing line numbers used by diagnostics."""

    return INLINE_CODE_RE.sub(_mask_match_preserve_newlines, text)


def unclosed_fence_opening_lines(text: str) -> list[int]:
    """Return opening line numbers for unterminated Markdown code fences."""

    in_fence = False
    fence_char = ""
    fence_length = 0
    opening_line = 0
    for number, line in enumerate(text.splitlines(), start=1):
        if not in_fence:
            match = FENCE_START_RE.match(line)
            if match is None:
                continue
            token = match.group(1)
            in_fence = True
            fence_char = token[0]
            fence_length = len(token)
            opening_line = number
            continue
        if re.match(
            rf"^[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*$",
            line,
        ):
            in_fence = False
            fence_char = ""
            fence_length = 0
            opening_line = 0
    return [opening_line] if in_fence else []


def heading_level_skips(body: str) -> list[tuple[int, int, int]]:
    """Return ATX heading jumps, treating frontmatter title as implicit H1."""

    visible = outside_fence_text(body)
    previous_level = 1
    skips: list[tuple[int, int, int]] = []
    for number, line in enumerate(visible.splitlines(), start=1):
        match = ATX_HEADING_RE.match(line)
        if match is None:
            continue
        level = len(match.group(1))
        if level > previous_level + 1:
            skips.append((number, previous_level, level))
        previous_level = level
    return skips


def validate_known_component_balance(body: str) -> tuple[list[str], int]:
    """Balance only known paired Mintlify blocks outside code examples."""

    visible = mask_inline_code(outside_fence_text(body))
    visible = MDX_COMMENT_RE.sub(_mask_match_preserve_newlines, visible)
    stack: list[tuple[str, int]] = []
    errors: list[str] = []
    checked = 0
    for match in MINTLIFY_TAG_RE.finditer(visible):
        tag = match.group("tag")
        if tag not in KNOWN_PAIRED_MINTLIFY_COMPONENTS:
            # Includes governed self-closing Icon/Badge/Color/Image and Tree.*
            # forms, plus generic JSX which this conservative parser ignores.
            continue
        checked += 1
        line = visible.count("\n", 0, match.start()) + 1
        closing = bool(match.group("closing"))
        self_closing = match.group("attrs").rstrip().endswith("/")
        if self_closing:
            errors.append(f"line {line}: paired Mintlify component <{tag}> cannot self-close")
            continue
        if not closing:
            stack.append((tag, line))
            continue
        if not stack:
            errors.append(f"line {line}: closing </{tag}> has no opening component")
            continue
        open_tag, open_line = stack[-1]
        if open_tag != tag:
            errors.append(
                f"line {line}: closing </{tag}> crosses <{open_tag}> opened at line {open_line}"
            )
            # Recover at the matching opener when possible so one defect does
            # not manufacture an error for every later sibling.
            matching_index = next(
                (index for index in range(len(stack) - 1, -1, -1) if stack[index][0] == tag),
                None,
            )
            if matching_index is not None:
                del stack[matching_index:]
            continue
        stack.pop()
    errors.extend(
        f"line {line}: paired Mintlify component <{tag}> is not closed"
        for tag, line in stack
    )
    return errors, checked


_ALT_ATTRIBUTE_RE = re.compile(
    r"\balt\s*=\s*(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|\{(?P<expr>[^}]*)\})",
    flags=re.DOTALL,
)
_PRESENTATION_ROLE_RE = re.compile(
    r"\brole\s*=\s*[\"']presentation[\"']",
    flags=re.IGNORECASE,
)
_ARIA_HIDDEN_RE = re.compile(
    r"\baria-hidden\s*=\s*(?:[\"']true[\"']|\{\s*true\s*\})",
    flags=re.IGNORECASE,
)


def validate_image_accessibility(body: str) -> tuple[list[str], dict[str, int]]:
    """Validate auditable image alternatives outside fenced examples.

    Video, Embed, and iframe transcript/caption quality remains a human-review
    obligation.  The scanner reports those occurrences but does not claim a
    reliable proximity or semantic-caption guarantee.
    """

    visible = mask_inline_code(outside_fence_text(body))
    errors: list[str] = []
    facts = {
        "markdown_images": 0,
        "jsx_images": 0,
        "media_human_review_occurrences": len(MEDIA_REVIEW_RE.findall(visible)),
    }
    for match in MARKDOWN_IMAGE_RE.finditer(visible):
        facts["markdown_images"] += 1
        alt = normalize_orientation_scalar(match.group("alt"))
        if alt:
            continue
        preceding = visible[: match.start()].rstrip()
        if preceding.endswith(DECORATIVE_IMAGE_MARKER):
            continue
        line = visible.count("\n", 0, match.start()) + 1
        errors.append(
            f"line {line}: Markdown image requires non-empty alt text or immediate "
            f"{DECORATIVE_IMAGE_MARKER}"
        )

    for match in JSX_IMAGE_RE.finditer(visible):
        facts["jsx_images"] += 1
        attrs = match.group("attrs")
        alt_match = _ALT_ATTRIBUTE_RE.search(attrs)
        line = visible.count("\n", 0, match.start()) + 1
        if alt_match is None:
            errors.append(f"line {line}: <{match.group('tag')}> requires an alt attribute")
            continue
        literal_alt = alt_match.group("double")
        if literal_alt is None:
            literal_alt = alt_match.group("single")
        if literal_alt is None or normalize_orientation_scalar(literal_alt):
            continue
        if _PRESENTATION_ROLE_RE.search(attrs) or _ARIA_HIDDEN_RE.search(attrs):
            continue
        errors.append(
            f"line {line}: empty image alt is allowed only with role=\"presentation\" "
            "or aria-hidden=\"true\""
        )
    return errors, facts


def validate_mdx_structure(body: str) -> tuple[list[str], dict[str, int]]:
    """Run conservative fence, heading, component, and accessibility checks."""

    errors: list[str] = []
    fence_lines = unclosed_fence_opening_lines(body)
    errors.extend(f"line {line}: Markdown code fence is not closed" for line in fence_lines)

    skips = heading_level_skips(body)
    errors.extend(
        f"line {line}: heading level skips from H{previous} to H{current}"
        for line, previous, current in skips
    )

    component_errors, component_tags = validate_known_component_balance(body)
    errors.extend(component_errors)
    image_errors, image_facts = validate_image_accessibility(body)
    errors.extend(image_errors)
    return errors, {
        "unclosed_fences": len(fence_lines),
        "heading_level_skips": len(skips),
        "component_balance_errors": len(component_errors),
        "known_component_tags_checked": component_tags,
        "image_accessibility_errors": len(image_errors),
        **image_facts,
    }


def body_h1_lines(body: str) -> list[int]:
    visible = outside_fence_text(body)
    return [
        number
        for number, line in enumerate(visible.splitlines(), start=1)
        if H1_RE.match(line)
    ]


def has_cardgroup(body: str) -> bool:
    return bool(CARDGROUP_RE.search(outside_fence_text(body)))


def migrate_cardgroups(body: str) -> str:
    return transform_outside_fences(body, lambda line: CARDGROUP_RE.sub(r"\1Columns\2", line))


def demote_body_h1(body: str) -> str:
    return transform_outside_fences(body, lambda line: H1_REWRITE_RE.sub(r"\1##\2", line, count=1) if H1_RE.match(line.rstrip("\r\n")) else line)


def internal_targets(body: str) -> list[str]:
    visible = outside_fence_text(body)
    targets: list[str] = []
    for match in MARKDOWN_LINK_RE.finditer(visible):
        targets.append((match.group(1) or match.group(2)).strip())
    targets.extend(match.group(1).strip() for match in HREF_RE.finditer(visible))
    return targets


def is_external_or_anchor(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(("https://", "http://", "mailto:", "tel:", "#"))


def bool_field(values: dict[str, str], key: str) -> bool:
    return values.get(key, "").strip().lower() == "true"


def infer_page_type(
    route: str,
    context: tuple[str, ...],
    redirects: dict[str, str],
    disposition: str | None = None,
) -> str:
    lower = route.lower()
    context_text = " / ".join(context).lower()
    name = Path(lower).name
    if route in redirects:
        return "redirect"
    if disposition == "historical_change_evidence":
        return "changelog" if lower.startswith("changelog/") else "historical_record"
    if disposition == "generated_build_evidence":
        return "historical_record"
    if disposition == "certification_evidence" and re.search(
        r"(?:^|-)20\d{2}-\d{2}-\d{2}(?:$|-)", name
    ):
        return "historical_record"
    if route in {"index", "quickstart", "start-here/orientation"}:
        return "orientation"
    if route == "start-here/current-operational-state" or "current-state" in name:
        return "status"
    if lower.startswith("changelog/"):
        return "changelog"
    if "historical roadmaps" in context_text:
        return "historical_record"
    if lower.startswith("runbooks/"):
        return "runbook"
    if lower.startswith("workflows/"):
        return "workflow"
    if lower.startswith("standards/"):
        return "standard"
    if lower.startswith("doctrine/"):
        return "doctrine"
    if lower.startswith("developers/"):
        return "developer"
    if lower.startswith("governance/"):
        return "policy"
    if lower.startswith("support/"):
        if any(token in name for token in ("legal", "copyright", "dmca", "license", "licensing", "privacy", "terms")):
            return "legal"
        return "support"
    if "registry" in name or "register" in name or lower.startswith("portfolio/"):
        return "registry"
    if lower.startswith("automation/"):
        return "workflow"
    return "reference"


def infer_audience(
    route: str,
    context: tuple[str, ...],
    page_type: str,
    disposition: str | None = None,
) -> str:
    lower = route.lower()
    tab = context[0].lower() if context else ""
    name = Path(lower).name
    if disposition in {"historical_change_evidence", "generated_build_evidence"}:
        return "historical"
    if disposition == "certification_evidence":
        if re.search(r"(?:^|-)20\d{2}-\d{2}-\d{2}(?:$|-)", name):
            return "historical"
        return "operator"
    if page_type in {"changelog", "historical_record"}:
        return "historical"
    if page_type == "redirect":
        return "public"
    if lower.startswith("chlom/"):
        if any(
            token in name
            for token in (
                "rights",
                "licens",
                "evidence",
                "compliance",
                "remed",
                "dla",
                "dail",
            )
        ):
            return "rights_support"
        if any(
            token in name
            for token in (
                "api",
                "mcp",
                "protocol",
                "fingerprint",
                "module",
            )
        ):
            return "developer"
        return "executive"
    if tab == "developers" or lower.startswith(("developers/", "technology/")):
        return "developer"
    if tab == "support & licensing" or lower.startswith("support/"):
        return "rights_support"
    if lower.startswith("commerce/"):
        return "operator"
    if lower.startswith("commercial/"):
        return "operator"
    if lower.startswith(
        (
            "platforms/",
            "revenue/",
            "governance/",
            "doctrine/",
            "ecosystem/",
            "portfolio/",
        )
    ):
        return "executive"
    if lower.startswith(
        (
            "knowledge/",
            "standards/",
            "automation/",
            "workflows/",
            "runbooks/",
            "security/",
            "control-plane/",
        )
    ):
        return "operator"
    if lower.startswith("institutional/"):
        return "executive"
    return "public"


def infer_content_state(
    route: str,
    page_type: str,
    values: dict[str, str],
    disposition: str | None = None,
) -> str:
    if page_type == "redirect":
        return "superseded"
    if disposition in {"historical_change_evidence", "generated_build_evidence"}:
        return "historical"
    if disposition == "certification_evidence" and page_type == "historical_record":
        return "historical"
    if page_type in {"changelog", "historical_record"}:
        return "historical"
    if route == "start-here/current-operational-state":
        return "current_with_holds"
    if bool_field(values, "deprecated"):
        return "superseded"
    # Navigation is not evidence that the described system is operationally current.
    return "unresolved"


def route_identity(route: str) -> str:
    clean = route.split("#", 1)[0].split("?", 1)[0].strip("/")
    suffix = Path(clean).suffix
    return clean[: -len(suffix)] if suffix in {".md", ".mdx"} else clean


def target_exists(root: Path, target: str) -> bool:
    if not target.startswith("/") or target.startswith("//"):
        return False
    try:
        return route_to_path(root, target).is_file()
    except ValueError:
        return False


def managed_link_records(
    root: Path | None,
    route: str,
    audience: str,
    content_state: str,
) -> tuple[tuple[str, str], ...]:
    """Choose two stable, distinct, existing, non-self governing links."""

    candidates = (
        UNRESOLVED_GOVERNING_LINKS + ROLE_LINKS.get(audience, ROLE_LINKS["public"])
        if content_state == "unresolved"
        else ROLE_LINKS.get(audience, ROLE_LINKS["public"])
    )
    self_route = route_identity(route)
    selected: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, target in candidates:
        identity = route_identity(target)
        if identity == self_route or identity in seen:
            continue
        if root is not None and not target_exists(root, target):
            continue
        seen.add(identity)
        selected.append((label, target))
        if len(selected) == 2:
            break
    if len(selected) != 2:
        raise ValueError(
            f"cannot resolve two existing non-self audience links for {route}: "
            f"audience={audience}, content_state={content_state}"
        )
    return tuple(selected)


def is_historical_profile(profile: PageProfile) -> bool:
    return (
        profile.primary_audience == "historical"
        or profile.page_type in {"changelog", "historical_record"}
        or profile.content_state in {"historical", "superseded"}
    )


def profile_for_page(
    route: str,
    context: tuple[str, ...],
    values: dict[str, str],
    redirects: dict[str, str],
    disposition: str | None = None,
    root: Path | None = None,
) -> PageProfile:
    override = UNLISTED_PROFILE_OVERRIDES.get(route) if disposition else None
    inferred_type = (
        override[1] if override else infer_page_type(route, context, redirects, disposition)
    )
    page_type = values.get("page_type") or inferred_type
    inferred_audience = (
        override[0] if override else infer_audience(route, context, page_type, disposition)
    )
    audience = values.get("primary_audience") or inferred_audience
    inferred_state = (
        override[2]
        if override
        else infer_content_state(route, page_type, values, disposition)
    )
    content_state = values.get("content_state") or inferred_state
    redirect_to = values.get("redirect_to") or redirects.get(route)
    component = CALLOUT_BY_AUDIENCE.get(audience, "Info")
    preliminary = PageProfile(
        route=route,
        path=f"{route}.mdx" if Path(route).suffix not in {".md", ".mdx"} else route,
        navigation_context=context,
        primary_audience=audience,
        page_type=page_type,
        content_state=content_state,
        orientation_component=component,
        role_links=(),
        orientation_mode=(
            ORIENTATION_MODE_REDIRECT if page_type == "redirect" else ORIENTATION_MODE_MANAGED
        ),
        governance_scope="governed_unlisted" if disposition else "navigation",
        disposition=disposition,
        redirect_to=redirect_to if page_type == "redirect" else None,
    )
    if page_type == "redirect":
        return preliminary
    if is_historical_profile(preliminary):
        preliminary = replace(preliminary, orientation_component="Warning")
    links = managed_link_records(root, route, audience, content_state)
    return replace(preliminary, role_links=tuple(target for _label, target in links))


def orientation_block_v1(profile: PageProfile) -> str:
    """Render the frozen legacy generator for exact migration recognition only."""

    if profile.page_type == "redirect":
        return ""
    component = CALLOUT_BY_AUDIENCE.get(profile.primary_audience, "Info")
    label = AUDIENCE_LABEL[profile.primary_audience]
    links = ROLE_LINKS[profile.primary_audience]
    first = f"[{links[0][0]}]({links[0][1]})"
    second = f"[{links[1][0]}]({links[1][1]})"
    if profile.primary_audience == "historical":
        message = (
            f"**Audience:** {label}. This page is {HISTORICAL_BOUNDARY}. "
            f"Confirm present guidance in {first} and use {second} to evaluate source precedence."
        )
    else:
        page_label = PAGE_TYPE_LABEL.get(profile.page_type, "page")
        focus = {
            "executive": "its documented scope, decisions, and institutional relationships",
            "public": "the documented topic and its CrownThrive relationships",
            "operator": "the documented controls, responsibilities, and handoffs",
            "developer": "the documented interfaces, constraints, and integration context",
            "rights_support": "the documented support, rights, licensing, or policy context",
        }[profile.primary_audience]
        message = (
            f"**Audience:** {label}. Use this {page_label} to understand {focus}. "
            f"Continue with {first} or {second}."
        )
    return "\n".join(
        (
            LEGACY_ORIENTATION_MARKER,
            f"<{component}>",
            f"  {message}",
            f"</{component}>",
        )
    )


_ORIENTATION_ESCAPE = str.maketrans(
    {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "{": "&#123;",
        "}": "&#125;",
        "\\": "&#92;",
        "`": "&#96;",
        "*": "&#42;",
        "_": "&#95;",
        "[": "&#91;",
        "]": "&#93;",
        "(": "&#40;",
        ")": "&#41;",
        "!": "&#33;",
        "|": "&#124;",
        "#": "&#35;",
        "$": "&#36;",
        "~": "&#126;",
    }
)


def normalize_orientation_scalar(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    if any(ord(character) < 32 and character not in "\n\t" for character in normalized):
        raise ValueError("orientation input contains a control character")
    return " ".join(normalized.split())


def escape_orientation_text(value: str) -> str:
    return normalize_orientation_scalar(value).translate(_ORIENTATION_ESCAPE)


def link_records_for_profile(profile: PageProfile) -> tuple[tuple[str, str], ...]:
    label_by_target = {
        target: label
        for candidates in tuple(ROLE_LINKS.values()) + (UNRESOLVED_GOVERNING_LINKS,)
        for label, target in candidates
    }
    return tuple((label_by_target[target], target) for target in profile.role_links)


def orientation_input_sha256(
    profile: PageProfile,
    title: str,
    description: str,
    links: tuple[tuple[str, str], ...],
) -> str:
    payload = {
        "schema": ORIENTATION_INPUT_SCHEMA,
        "title": normalize_orientation_scalar(title),
        "description": normalize_orientation_scalar(description),
        "primary_audience": profile.primary_audience,
        "page_type": profile.page_type,
        "content_state": profile.content_state,
        "links": [
            {
                "label": normalize_orientation_scalar(label),
                "target": target,
            }
            for label, target in links
        ],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def page_specific_lines(profile: PageProfile, title: str, description: str) -> tuple[str, ...]:
    lines = (
        f"  **Audience:** {AUDIENCE_LABEL[profile.primary_audience]} (`{profile.primary_audience}`).",
        f"  **This page:** {escape_orientation_text(title)} — {escape_orientation_text(description)}",
        (
            f"  **Documentation state:** `{profile.content_state}` for page type "
            f"`{profile.page_type}`. {NON_CERTIFICATION_BOUNDARY}"
            + (
                f" This page is {HISTORICAL_BOUNDARY}."
                if is_historical_profile(profile)
                else ""
            )
        ),
    )
    if profile.content_state == "unresolved":
        lines += (
            f"  **Unresolved reason:** {UNRESOLVED_REASON}.",
            f"  **Evidence needed:** {UNRESOLVED_EVIDENCE}.",
            f"  **Review role:** {UNRESOLVED_REVIEW_ROLE}.",
            f"  **Review trigger:** {UNRESOLVED_REVIEW_TRIGGER}.",
        )
    return lines


def orientation_block(
    profile: PageProfile,
    title: str,
    description: str,
    links: tuple[tuple[str, str], ...] | None = None,
) -> str:
    if profile.page_type == "redirect":
        return ""
    link_records = links or link_records_for_profile(profile)
    if len(link_records) != 2 or len({target for _label, target in link_records}) != 2:
        raise ValueError(f"managed orientation for {profile.route} requires two distinct links")
    first = f"[{link_records[0][0]}]({link_records[0][1]})"
    second = f"[{link_records[1][0]}]({link_records[1][1]})"
    lines: list[str] = [
        ORIENTATION_MARKER,
        f"<{profile.orientation_component}>",
    ]
    for line in page_specific_lines(profile, title, description):
        lines.extend((line, ""))
    lines.extend(
        (
            f"  **Related guidance:** {first} and {second}.",
            f"</{profile.orientation_component}>",
            ORIENTATION_END_MARKER,
        )
    )
    return "\n".join(lines)


@dataclass(frozen=True)
class OrientationBlock:
    marker: str
    component: str
    content: str
    rendered: str
    start: int
    end: int


_TOP_ORIENTATION_RE = re.compile(
    rf"\A(?P<leading>[ \t\r\n]*)(?P<marker>{re.escape(LEGACY_ORIENTATION_MARKER)}|"
    rf"{re.escape(ORIENTATION_MARKER)})\n"
    r"<(?P<component>Info|Note|Warning)>\n"
    r"(?P<content>.*?)\n"
    r"</(?P=component)>"
    rf"(?P<end_marker>\n{re.escape(ORIENTATION_END_MARKER)})?",
    flags=re.DOTALL,
)
_LABELED_LINK_RE = re.compile(
    r"(?<!!)\[([^\]]+)\]\(\s*(?:<([^>]+)>|([^\s)]+))\s*\)",
    flags=re.MULTILINE,
)


def extract_top_orientation(body: str) -> OrientationBlock | None:
    match = _TOP_ORIENTATION_RE.match(body)
    if match is None:
        return None
    rendered = match.group(0)[len(match.group("leading")) :]
    return OrientationBlock(
        marker=match.group("marker"),
        component=match.group("component"),
        content=match.group("content"),
        rendered=rendered,
        start=len(match.group("leading")),
        end=match.end(),
    )


def orientation_link_records(block: str) -> tuple[tuple[str, str], ...]:
    records: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in _LABELED_LINK_RE.finditer(block):
        label = normalize_orientation_scalar(match.group(1))
        target = (match.group(2) or match.group(3)).strip()
        identity = route_identity(target) if target.startswith("/") else target
        if identity in seen:
            continue
        seen.add(identity)
        records.append((label, target))
    return tuple(records)


def valid_orientation_link_records(
    root: Path,
    route: str,
    block: str,
    redirect_routes: set[str] | None = None,
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...], tuple[str, ...]]:
    valid: list[tuple[str, str]] = []
    self_links: list[str] = []
    invalid: list[str] = []
    self_route = route_identity(route)
    for label, target in orientation_link_records(block):
        if is_external_or_anchor(target):
            continue
        if not target.startswith("/") or target.startswith("//"):
            invalid.append(target)
            continue
        if route_identity(target) == self_route:
            self_links.append(target)
            continue
        if route_identity(target) in (redirect_routes or set()):
            invalid.append(target)
            continue
        if not target_exists(root, target):
            invalid.append(target)
            continue
        valid.append((label, target))
    return tuple(valid), tuple(self_links), tuple(invalid)


def finalize_orientation_profile(
    profile: PageProfile,
    title: str,
    description: str,
    block: OrientationBlock | None,
    mode: str,
    links: tuple[tuple[str, str], ...],
) -> PageProfile:
    if profile.page_type == "redirect":
        return replace(
            profile,
            orientation_mode=ORIENTATION_MODE_REDIRECT,
            orientation_input_sha256=None,
            orientation_render_sha256=None,
            role_links=(),
        )
    selected = links[:2]
    return replace(
        profile,
        orientation_mode=mode,
        role_links=tuple(target for _label, target in selected),
        orientation_input_sha256=orientation_input_sha256(
            profile,
            title,
            description,
            selected,
        ),
        orientation_render_sha256=(
            hashlib.sha256(block.rendered.encode("utf-8")).hexdigest()
            if block is not None
            else None
        ),
    )


def is_exact_managed_orientation(block: str, values: dict[str, str]) -> bool:
    extracted = extract_top_orientation(block)
    if extracted is None or extracted.marker != ORIENTATION_MARKER:
        return False
    required = ("title", "description", "primary_audience", "page_type", "content_state")
    if any(not values.get(key) for key in required):
        return False
    if values["primary_audience"] not in ALLOWED_AUDIENCES:
        return False
    link_records = orientation_link_records(extracted.rendered)
    if len(link_records) != 2:
        return False
    profile = PageProfile(
        route="managed-orientation-normalization",
        path="managed-orientation-normalization.mdx",
        navigation_context=(),
        primary_audience=values["primary_audience"],
        page_type=values["page_type"],
        content_state=values["content_state"],
        orientation_component=extracted.component,
        role_links=tuple(target for _label, target in link_records),
    )
    expected_component = (
        "Warning"
        if is_historical_profile(profile)
        else CALLOUT_BY_AUDIENCE.get(profile.primary_audience, "Info")
    )
    profile = replace(profile, orientation_component=expected_component)
    expected = orientation_block(
        profile,
        values["title"],
        values["description"],
        link_records,
    )
    return extracted.rendered == expected


def _replace_or_append_labeled_line(content: str, label: str, line: str) -> str:
    pattern = re.compile(rf"^[ \t]*\*\*{re.escape(label)}:\*\*.*$", flags=re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(line, content, count=1)
    return content.rstrip() + "\n\n" + line


def _unlink_self_references(content: str, route: str) -> str:
    self_route = route_identity(route)

    def markdown_replacement(match: re.Match[str]) -> str:
        target = (match.group(2) or match.group(3)).strip()
        return match.group(1) if target.startswith("/") and route_identity(target) == self_route else match.group(0)

    content = _LABELED_LINK_RE.sub(markdown_replacement, content)
    href_re = re.compile(r"\s+href\s*=\s*([\"'])([^\"']+)\1")

    def href_replacement(match: re.Match[str]) -> str:
        target = match.group(2)
        return "" if target.startswith("/") and route_identity(target) == self_route else match.group(0)

    return href_re.sub(href_replacement, content)


def upgrade_custom_orientation(
    root: Path,
    body: str,
    block: OrientationBlock,
    profile: PageProfile,
    title: str,
    description: str,
    redirect_routes: set[str] | None = None,
) -> str:
    """Add the v2 machine labels while retaining tailored custom prose."""

    content = _unlink_self_references(block.content, profile.route)
    specific = page_specific_lines(profile, title, description)
    if "**Audience:**" not in content:
        content = specific[0] + "\n\n" + content.lstrip()
    content = _replace_or_append_labeled_line(content, "This page", specific[1])
    content = _replace_or_append_labeled_line(content, "Documentation state", specific[2])
    if profile.content_state == "unresolved":
        unresolved_lines = specific[3:]
        for label, line in zip(
            ("Unresolved reason", "Evidence needed", "Review role", "Review trigger"),
            unresolved_lines,
        ):
            content = _replace_or_append_labeled_line(content, label, line)

    component = "Warning" if is_historical_profile(profile) else block.component
    candidate = "\n".join(
        (
            ORIENTATION_MARKER,
            f"<{component}>",
            content.rstrip(),
            f"</{component}>",
            ORIENTATION_END_MARKER,
        )
    )
    valid, _self_links, _invalid = valid_orientation_link_records(
        root, profile.route, candidate, redirect_routes
    )
    if len(valid) < 2:
        managed = link_records_for_profile(profile)
        first = f"[{managed[0][0]}]({managed[0][1]})"
        second = f"[{managed[1][0]}]({managed[1][1]})"
        content = (
            content.rstrip()
            + "\n\n"
            + f"  **Related guidance:** {first} and {second}."
        )
        candidate = "\n".join(
            (
                ORIENTATION_MARKER,
                f"<{component}>",
                content,
                f"</{component}>",
                ORIENTATION_END_MARKER,
            )
        )
    return body[: block.start] + candidate + body[block.end :]


def strip_generated_custom_orientation_supplement(
    body: str,
    values: dict[str, str],
) -> str:
    """Remove only deterministic v2 lines while retaining custom source prose."""

    block = extract_top_orientation(body)
    required = ("title", "description", "primary_audience", "page_type", "content_state")
    if (
        block is None
        or block.marker != ORIENTATION_MARKER
        or any(not values.get(key) for key in required)
        or values["primary_audience"] not in ALLOWED_AUDIENCES
    ):
        return body
    profile = PageProfile(
        route="custom-orientation-normalization",
        path="custom-orientation-normalization.mdx",
        navigation_context=(),
        primary_audience=values["primary_audience"],
        page_type=values["page_type"],
        content_state=values["content_state"],
        orientation_component=block.component,
        role_links=(),
        orientation_mode=ORIENTATION_MODE_CUSTOM,
    )
    generated_lines = set(page_specific_lines(profile, values["title"], values["description"]))
    allowed_generated_targets = {
        target
        for candidates in tuple(ROLE_LINKS.values()) + (UNRESOLVED_GOVERNING_LINKS,)
        for _label, target in candidates
    }

    lines = block.content.splitlines()
    kept: list[str] = []
    skip_following_blank = False
    for line in lines:
        stripped = line.rstrip()
        targets = [target for _label, target in orientation_link_records(line)]
        is_generated_related = (
            stripped.lstrip().startswith("**Related guidance:**")
            and len(targets) == 2
            and set(targets).issubset(allowed_generated_targets)
        )
        if stripped in generated_lines or is_generated_related:
            if kept and not kept[-1].strip():
                kept.pop()
            skip_following_blank = True
            continue
        if skip_following_blank and not line.strip():
            skip_following_blank = False
            continue
        skip_following_blank = False
        kept.append(line)
    content = "\n".join(kept).strip("\n")
    rendered = "\n".join(
        (
            ORIENTATION_MARKER,
            f"<{block.component}>",
            content,
            f"</{block.component}>",
            ORIENTATION_END_MARKER,
        )
    )
    return body[: block.start] + rendered + body[block.end :]


def add_frontmatter_fields(raw: str, additions: dict[str, str]) -> str:
    existing = parse_frontmatter(raw).values
    lines = raw.splitlines()
    changed = False
    for key, value in additions.items():
        if key in existing:
            continue
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        changed = True
    if not changed:
        return raw
    return "\n".join(lines)


def load_orientation_profile_records(root: Path) -> dict[str, dict[str, Any]]:
    path = root / PROFILE_PATH
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid PentaDocs page profile manifest: {exc}") from exc
    profiles = payload.get("profiles", [])
    if not isinstance(profiles, list):
        raise ValueError(f"{PROFILE_PATH}: profiles must be a list")
    records: dict[str, dict[str, Any]] = {}
    for item in profiles:
        if not isinstance(item, dict) or not isinstance(item.get("route"), str):
            continue
        records[item["route"]] = item
    return records


def migrate_page(
    root: Path,
    route: str,
    context: tuple[str, ...],
    text: str,
    redirects: dict[str, str],
    disposition: str | None = None,
    prior_profile: dict[str, Any] | None = None,
) -> tuple[str, PageProfile]:
    parsed = split_frontmatter(text)
    if parsed is None:
        raise ValueError(f"missing or malformed frontmatter: {route}")
    frontmatter_raw, body = parsed
    frontmatter = parse_frontmatter(frontmatter_raw)
    profile = profile_for_page(
        route,
        context,
        frontmatter.values,
        redirects,
        disposition,
        root,
    )
    additions = {
        "standard_version": STANDARD_VERSION,
        "primary_audience": profile.primary_audience,
        "page_type": profile.page_type,
        "content_state": profile.content_state,
    }
    if profile.page_type == "redirect" and profile.redirect_to:
        additions["redirect_to"] = profile.redirect_to
    new_frontmatter = add_frontmatter_fields(frontmatter_raw, additions)

    new_body = migrate_cardgroups(body)
    if profile.page_type != "redirect":
        new_body = demote_body_h1(new_body)
        title = frontmatter.values["title"]
        description = frontmatter.values["description"]
        existing = extract_top_orientation(new_body)
        visible = outside_fence_text(new_body)
        if existing is None and (
            ORIENTATION_MARKER in visible or LEGACY_ORIENTATION_MARKER in visible
        ):
            raise ValueError(
                f"audience orientation is not a recognized first body block: {route}"
            )

        links = link_records_for_profile(profile)
        expected_v2 = orientation_block(profile, title, description, links)
        expected_v1 = orientation_block_v1(profile)
        prior_mode = (prior_profile or {}).get("orientation_mode")
        if existing is None:
            mode = ORIENTATION_MODE_MANAGED
            new_body = expected_v2 + "\n\n" + new_body.lstrip("\r\n")
        elif prior_mode == ORIENTATION_MODE_CUSTOM:
            mode = ORIENTATION_MODE_CUSTOM
            new_body = upgrade_custom_orientation(
                root,
                new_body,
                existing,
                profile,
                title,
                description,
                set(redirects),
            )
        elif existing.marker == LEGACY_ORIENTATION_MARKER:
            if existing.rendered == expected_v1:
                mode = ORIENTATION_MODE_MANAGED
                new_body = (
                    new_body[: existing.start]
                    + expected_v2
                    + new_body[existing.end :]
                )
            else:
                # This is the one bootstrap registration path: unknown legacy
                # prose is retained as custom rather than overwritten by the
                # exact generated-v1 replacement.
                mode = ORIENTATION_MODE_CUSTOM
                new_body = upgrade_custom_orientation(
                    root,
                    new_body,
                    existing,
                    profile,
                    title,
                    description,
                    set(redirects),
                )
        else:
            actual_render_sha = hashlib.sha256(existing.rendered.encode("utf-8")).hexdigest()
            prior_render_sha = (prior_profile or {}).get("orientation_render_sha256")
            if prior_mode == ORIENTATION_MODE_MANAGED and prior_render_sha not in {
                None,
                actual_render_sha,
            }:
                raise ValueError(
                    f"managed v2 orientation was edited without a custom profile override: {route}"
                )
            if existing.rendered == expected_v2 or prior_mode == ORIENTATION_MODE_MANAGED:
                mode = ORIENTATION_MODE_MANAGED
                new_body = (
                    new_body[: existing.start]
                    + expected_v2
                    + new_body[existing.end :]
                )
            else:
                mode = ORIENTATION_MODE_CUSTOM
                new_body = upgrade_custom_orientation(
                    root,
                    new_body,
                    existing,
                    profile,
                    title,
                    description,
                    set(redirects),
                )
    else:
        mode = ORIENTATION_MODE_REDIRECT

    updated = f"---\n{new_frontmatter}\n---\n\n{new_body.rstrip()}\n"
    updated_parsed = split_frontmatter(updated)
    assert updated_parsed is not None
    updated_profile = profile_for_page(
        route,
        context,
        parse_frontmatter(updated_parsed[0]).values,
        redirects,
        disposition,
        root,
    )
    if updated_profile.page_type != "redirect":
        updated_block = extract_top_orientation(updated_parsed[1])
        if updated_block is None:
            raise AssertionError(f"migration did not produce an orientation block: {route}")
        valid_links, _self_links, _invalid_links = valid_orientation_link_records(
            root,
            route,
            updated_block.rendered,
        )
        updated_profile = finalize_orientation_profile(
            updated_profile,
            parse_frontmatter(updated_parsed[0]).values["title"],
            parse_frontmatter(updated_parsed[0]).values["description"],
            updated_block,
            mode,
            valid_links,
        )
    return updated, updated_profile


def validate_internal_links(root: Path, path: Path, body: str) -> list[str]:
    errors: list[str] = []
    for target in internal_targets(body):
        if is_external_or_anchor(target):
            continue
        if target.startswith("//"):
            errors.append(
                f"{path.relative_to(root)}: protocol-relative link is not allowed: {target}"
            )
            continue
        if target.startswith(("/", "{")):
            if target.startswith("{"):
                errors.append(f"{path.relative_to(root)}: dynamic internal link is not auditable: {target}")
                continue
        else:
            errors.append(f"{path.relative_to(root)}: internal link must be root-relative: {target}")
            continue
        route = target.split("#", 1)[0].split("?", 1)[0]
        if route.endswith((".md", ".mdx")):
            errors.append(f"{path.relative_to(root)}: internal documentation link must omit file extension: {target}")
    return errors


def validate_orientation(
    root: Path,
    path: Path,
    body: str,
    profile: PageProfile,
    values: dict[str, str],
    orientation_mode: str,
    redirect_routes: set[str] | None = None,
) -> tuple[list[str], PageProfile, dict[str, Any]]:
    facts: dict[str, Any] = {
        "present": False,
        "valid": False,
        "mode": orientation_mode,
        "generic_v1": False,
        "self_links": 0,
        "invalid_links": 0,
    }
    if profile.page_type == "redirect":
        return [], finalize_orientation_profile(
            profile,
            values.get("title", ""),
            values.get("description", ""),
            None,
            ORIENTATION_MODE_REDIRECT,
            (),
        ), facts

    errors: list[str] = []
    relative = path.relative_to(root)
    visible = outside_fence_text(body)
    v1_count = visible.count(LEGACY_ORIENTATION_MARKER)
    v2_count = visible.count(ORIENTATION_MARKER)
    facts["generic_v1"] = v1_count > 0
    if v1_count:
        errors.append(f"{relative}: generic or custom v1 audience orientation remains; migrate to v2")
    if v2_count != 1:
        errors.append(f"{relative}: expected exactly one v2 audience orientation marker")

    block = extract_top_orientation(body)
    if block is None or block.marker != ORIENTATION_MARKER:
        errors.append(f"{relative}: v2 audience orientation must be the first body block")
        return errors, finalize_orientation_profile(
            profile,
            values.get("title", ""),
            values.get("description", ""),
            block,
            orientation_mode,
            (),
        ), facts
    facts["present"] = True
    if ORIENTATION_END_MARKER not in block.rendered:
        errors.append(f"{relative}: v2 audience orientation lacks its closing boundary marker")

    title = values.get("title", "")
    description = values.get("description", "")
    valid_links, self_links, invalid_links = valid_orientation_link_records(
        root,
        profile.route,
        block.rendered,
        redirect_routes,
    )
    all_targets = internal_targets(block.rendered)
    self_targets = {
        target
        for target in all_targets
        if target.startswith("/") and route_identity(target) == route_identity(profile.route)
    }
    facts["self_links"] = len(set(self_links) | self_targets)
    facts["invalid_links"] = len(invalid_links)
    if facts["self_links"]:
        errors.append(f"{relative}: audience orientation contains a self-link")
    if invalid_links:
        errors.append(
            f"{relative}: audience orientation contains missing or non-root-relative links "
            f"{list(invalid_links)}"
        )
    if len(valid_links) < 2:
        errors.append(
            f"{relative}: audience orientation requires two distinct existing non-self governing links"
        )

    specific = page_specific_lines(profile, title, description)
    if "**Audience:**" not in block.content:
        errors.append(f"{relative}: audience orientation lacks the Audience label")
    if specific[1] not in block.content:
        errors.append(f"{relative}: audience orientation This page label drifted from title/description")
    if specific[2] not in block.content:
        errors.append(f"{relative}: audience orientation Documentation state label or boundary drifted")
    if profile.content_state == "unresolved":
        for label, expected_line in zip(
            ("Unresolved reason", "Evidence needed", "Review role", "Review trigger"),
            specific[3:],
        ):
            if expected_line not in block.content:
                errors.append(
                    f"{relative}: unresolved authority explanation lacks governed {label} text"
                )
    if is_historical_profile(profile):
        if block.component != "Warning" or HISTORICAL_BOUNDARY not in block.content:
            errors.append(
                f"{relative}: historical or superseded page lacks explicit non-current authority boundary"
            )

    if orientation_mode == ORIENTATION_MODE_MANAGED:
        expected_links = link_records_for_profile(profile)
        expected = orientation_block(profile, title, description, expected_links)
        if block.rendered != expected:
            errors.append(f"{relative}: managed v2 audience orientation drifted from deterministic inputs")
        links_for_profile = expected_links
    elif orientation_mode == ORIENTATION_MODE_CUSTOM:
        links_for_profile = valid_links
    else:
        errors.append(f"{relative}: invalid orientation_mode {orientation_mode!r}")
        links_for_profile = valid_links

    finalized = finalize_orientation_profile(
        profile,
        title,
        description,
        block,
        orientation_mode,
        links_for_profile,
    )
    facts["valid"] = not errors
    return errors, finalized, facts


_UNRESOLVED_AUTHORITY_SIGNAL_RE = re.compile(
    r"\bcanonical\b|\b(?:effective|as[- ]of)\b|\bControlled[ -]Test\b|"
    r"^[ \t]{0,3}#{2,6}[ \t]+Current\b",
    flags=re.IGNORECASE | re.MULTILINE,
)


def validate_unresolved_authority_gate(
    root: Path,
    path: Path,
    body: str,
    profile: PageProfile,
) -> list[str]:
    if profile.page_type == "redirect" or profile.content_state != "unresolved":
        return []
    visible = outside_fence_text(body)
    if _UNRESOLVED_AUTHORITY_SIGNAL_RE.search(visible) is None:
        return []
    labels = ("Unresolved reason", "Evidence needed", "Review role", "Review trigger")
    if all(f"**{label}:**" in visible for label in labels):
        return []
    return [
        f"{path.relative_to(root)}: unresolved page contains current/canonical/effective tokens "
        "without a structured page-authority explanation"
    ]


def validate_redirect(
    root: Path,
    path: Path,
    values: dict[str, str],
    profile: PageProfile,
    redirects: dict[str, str],
) -> list[str]:
    if profile.page_type != "redirect":
        return []
    errors: list[str] = []
    relative = path.relative_to(root)
    if not bool_field(values, "deprecated"):
        errors.append(f"{relative}: typed redirect must set deprecated: true")
    if not bool_field(values, "noindex"):
        errors.append(f"{relative}: typed redirect must set noindex: true")
    if values.get("content_state") != "superseded":
        errors.append(f"{relative}: typed redirect must set content_state: superseded")
    target = values.get("redirect_to", "")
    if not target.startswith("/") or target.startswith("//"):
        errors.append(f"{relative}: typed redirect requires a root-relative redirect_to")
    expected = redirects.get(profile.route)
    if expected is None:
        errors.append(f"{relative}: typed redirect is absent from docs.json redirects")
    elif target != expected:
        errors.append(
            f"{relative}: redirect_to {target!r} does not match docs.json destination {expected!r}"
        )
    canonical_route = target.strip("/")
    if canonical_route == profile.route:
        errors.append(f"{relative}: typed redirect cannot target itself")
    elif canonical_route in redirects:
        errors.append(f"{relative}: typed redirect cannot target another redirect source")
    return errors


def validate_profile_frontmatter(root: Path, path: Path, values: dict[str, str]) -> list[str]:
    relative = path.relative_to(root)
    errors: list[str] = []
    for key in REQUIRED_FRONTMATTER:
        if not values.get(key):
            errors.append(f"{relative}: missing frontmatter field {key}")
    if values.get("standard_version") != STANDARD_VERSION:
        errors.append(f"{relative}: standard_version must be {STANDARD_VERSION}")
    if values.get("primary_audience") not in ALLOWED_AUDIENCES:
        errors.append(f"{relative}: invalid primary_audience")
    if values.get("page_type") not in ALLOWED_PAGE_TYPES:
        errors.append(f"{relative}: invalid page_type")
    if values.get("content_state") not in ALLOWED_CONTENT_STATES:
        errors.append(f"{relative}: invalid content_state")
    return errors


def build_profile_manifest(profiles: Iterable[PageProfile]) -> dict[str, Any]:
    profile_list = sorted(profiles, key=lambda item: item.route)
    records = [profile.as_dict() for profile in profile_list]
    navigation_count = sum(record["governance_scope"] == "navigation" for record in records)
    unlisted_count = sum(
        record["governance_scope"] == "governed_unlisted" for record in records
    )
    nonredirect = [
        profile for profile in profile_list if profile.page_type != "redirect"
    ]
    input_counts = Counter(
        profile.orientation_input_sha256
        for profile in nonredirect
        if profile.orientation_input_sha256 is not None
    )
    render_counts = Counter(
        profile.orientation_render_sha256
        for profile in nonredirect
        if profile.orientation_render_sha256 is not None
    )
    input_collision_groups = sum(count > 1 for count in input_counts.values())
    input_collision_excess = sum(
        count - 1 for count in input_counts.values() if count > 1
    )
    render_collision_groups = sum(count > 1 for count in render_counts.values())
    render_collision_excess = sum(
        count - 1 for count in render_counts.values() if count > 1
    )
    page_specific_count = sum(
        profile.orientation_input_sha256 is not None
        and profile.orientation_render_sha256 is not None
        and profile.orientation_mode in {ORIENTATION_MODE_MANAGED, ORIENTATION_MODE_CUSTOM}
        for profile in nonredirect
    )
    return {
        "schema": PROFILE_SCHEMA,
        "schema_version": "1.0.0",
        "standard_version": STANDARD_VERSION,
        "navigation_source": "docs.json",
        "governed_unlisted_source": UNLISTED_DISPOSITIONS_PATH.as_posix(),
        "navigation_page_count": navigation_count,
        "governed_unlisted_page_count": unlisted_count,
        "governed_page_count": len(records),
        "content_state_semantics": "editorial_projection_posture_only_not_runtime_legal_rights_provider_or_production_certification",
        "orientation_contract": {
            "version": "2.0.0",
            "marker": ORIENTATION_MARKER,
            "closing_marker": ORIENTATION_END_MARKER,
            "input_schema": ORIENTATION_INPUT_SCHEMA,
            "required_labels": ["Audience", "This page", "Documentation state"],
            "non_certification_boundary": NON_CERTIFICATION_BOUNDARY,
            "historical_boundary": HISTORICAL_BOUNDARY,
            "minimum_existing_nonself_links": 2,
            "modes": [
                ORIENTATION_MODE_MANAGED,
                ORIENTATION_MODE_CUSTOM,
                ORIENTATION_MODE_REDIRECT,
            ],
        },
        "orientation_metrics": {
            "orientation_required_page_count": len(nonredirect),
            "managed_v2_page_count": sum(
                profile.orientation_mode == ORIENTATION_MODE_MANAGED
                for profile in nonredirect
            ),
            "custom_page_count": sum(
                profile.orientation_mode == ORIENTATION_MODE_CUSTOM
                for profile in nonredirect
            ),
            "page_specific_orientation_count": page_specific_count,
            "page_specific_orientation_rate": (
                round(page_specific_count / len(nonredirect), 6) if nonredirect else 1.0
            ),
            "generic_v1_page_count": 0,
            "self_link_page_count": sum(
                any(
                    route_identity(target) == route_identity(profile.route)
                    for target in profile.role_links
                )
                for profile in nonredirect
            ),
            "invalid_link_page_count": 0,
            "input_collision_groups": input_collision_groups,
            "input_collision_excess": input_collision_excess,
            "render_collision_groups": render_collision_groups,
            "render_collision_excess": render_collision_excess,
        },
        "profiles": records,
    }


def validate_profile_manifest(
    root: Path, expected_profiles: list[PageProfile]
) -> list[str]:
    errors: list[str] = []
    path = root / PROFILE_PATH
    if not path.is_file():
        return [f"missing PentaDocs page profile manifest: {PROFILE_PATH}"]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid PentaDocs page profile manifest: {exc}"]
    expected = build_profile_manifest(expected_profiles)
    for key in (
        "schema",
        "schema_version",
        "standard_version",
        "navigation_source",
        "governed_unlisted_source",
        "navigation_page_count",
        "governed_unlisted_page_count",
        "governed_page_count",
        "content_state_semantics",
        "orientation_contract",
        "orientation_metrics",
    ):
        if manifest.get(key) != expected[key]:
            errors.append(
                f"{PROFILE_PATH}: {key}={manifest.get(key)!r}, expected {expected[key]!r}"
            )
    if manifest.get("profiles") != expected["profiles"]:
        errors.append(f"{PROFILE_PATH}: page profiles drifted from docs.json and MDX metadata")
    return errors


def load_docs(root: Path) -> dict[str, Any]:
    path = root / "docs.json"
    if not path.is_file():
        raise ValueError("missing docs.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid docs.json: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("docs.json root must be an object")
    return data


def validate_repository(root: Path) -> tuple[list[str], dict[str, Any]]:
    root = root.resolve()
    errors: list[str] = []
    stats = {
        "navigation_pages": 0,
        "governed_unlisted_pages": 0,
        "governed_pages": 0,
        "standard_pages": 0,
        "redirect_pages": 0,
        "historical_pages": 0,
        "orientation_pages": 0,
        "managed_orientation_pages": 0,
        "custom_orientation_pages": 0,
        "valid_page_specific_orientation_pages": 0,
        "generic_v1_orientation_pages": 0,
        "orientation_self_link_pages": 0,
        "orientation_invalid_link_pages": 0,
        "orientation_input_collision_groups": 0,
        "orientation_input_collision_excess": 0,
        "orientation_render_collision_groups": 0,
        "orientation_render_collision_excess": 0,
        "page_specific_orientation_rate": 0.0,
        "unclosed_fence_pages": 0,
        "heading_level_skip_pages": 0,
        "component_balance_error_pages": 0,
        "known_component_tags_checked": 0,
        "image_accessibility_error_pages": 0,
        "markdown_images_checked": 0,
        "jsx_images_checked": 0,
        "media_accessibility_human_review_pages": 0,
        "media_accessibility_human_review_occurrences": 0,
        "media_accessibility_review_policy": (
            "human_review_required_for_video_embed_iframe_transcript_caption_or_accessibility_note"
        ),
    }
    try:
        docs = load_docs(root)
    except ValueError as exc:
        return [str(exc)], stats
    navigation = navigation_pages(docs)
    stats["navigation_pages"] = len(navigation)
    duplicates = sorted(
        route
        for route, count in Counter(route for route, _ in navigation).items()
        if count > 1
    )
    for route in duplicates:
        errors.append(f"duplicate PentaDocs navigation route: {route}")

    redirects = redirect_map(docs)
    navigated_routes = {route for route, _context in navigation}
    try:
        unlisted = load_governed_unlisted_pages(root, navigated_routes)
    except ValueError as exc:
        errors.append(str(exc))
        unlisted = []
    stats["governed_unlisted_pages"] = len(unlisted)
    governed_pages = [
        (route, context, None) for route, context in navigation
    ] + unlisted
    stats["governed_pages"] = len(governed_pages)
    profiles: list[PageProfile] = []
    try:
        profile_records = load_orientation_profile_records(root)
    except ValueError as exc:
        errors.append(str(exc))
        profile_records = {}
    for route, context, disposition in governed_pages:
        if route.startswith(("http://", "https://", "mailto:")):
            continue
        try:
            path = route_to_path(root, route)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            scope = "navigation" if disposition is None else f"unlisted {disposition}"
            errors.append(
                f"{scope} page is missing: {route} -> {path.relative_to(root)}"
            )
            continue
        text = path.read_text(encoding="utf-8")
        parsed = split_frontmatter(text)
        if parsed is None:
            errors.append(f"{path.relative_to(root)}: missing or malformed frontmatter")
            continue
        frontmatter_raw, body = parsed
        frontmatter = parse_frontmatter(frontmatter_raw)
        if frontmatter.duplicate_keys:
            errors.append(
                f"{path.relative_to(root)}: duplicate frontmatter keys {list(frontmatter.duplicate_keys)}"
            )
        values = frontmatter.values
        profile = profile_for_page(route, context, values, redirects, disposition, root)

        errors.extend(validate_profile_frontmatter(root, path, values))

        if has_cardgroup(body):
            errors.append(
                f"{path.relative_to(root)}: deprecated CardGroup remains outside a fenced example; use Columns"
            )
        if profile.page_type != "redirect":
            h1_lines = body_h1_lines(body)
            if h1_lines:
                errors.append(
                    f"{path.relative_to(root)}: body H1 remains outside fenced code at lines {h1_lines}; frontmatter title owns H1"
                )
        structural_errors, structural_facts = validate_mdx_structure(body)
        errors.extend(
            f"{path.relative_to(root)}: {error}" for error in structural_errors
        )
        stats["unclosed_fence_pages"] += structural_facts["unclosed_fences"] > 0
        stats["heading_level_skip_pages"] += structural_facts["heading_level_skips"] > 0
        stats["component_balance_error_pages"] += (
            structural_facts["component_balance_errors"] > 0
        )
        stats["known_component_tags_checked"] += structural_facts[
            "known_component_tags_checked"
        ]
        stats["image_accessibility_error_pages"] += (
            structural_facts["image_accessibility_errors"] > 0
        )
        stats["markdown_images_checked"] += structural_facts["markdown_images"]
        stats["jsx_images_checked"] += structural_facts["jsx_images"]
        stats["media_accessibility_human_review_pages"] += (
            structural_facts["media_human_review_occurrences"] > 0
        )
        stats["media_accessibility_human_review_occurrences"] += structural_facts[
            "media_human_review_occurrences"
        ]
        errors.extend(validate_internal_links(root, path, body))
        prior_mode = profile_records.get(route, {}).get(
            "orientation_mode",
            ORIENTATION_MODE_MANAGED,
        )
        orientation_errors, profile, orientation_facts = validate_orientation(
            root,
            path,
            body,
            profile,
            values,
            prior_mode,
            set(redirects),
        )
        errors.extend(orientation_errors)
        errors.extend(validate_unresolved_authority_gate(root, path, body, profile))
        errors.extend(validate_redirect(root, path, values, profile, redirects))
        profiles.append(profile)

        stats["standard_pages"] += values.get("standard_version") == STANDARD_VERSION
        stats["redirect_pages"] += profile.page_type == "redirect"
        stats["historical_pages"] += profile.page_type in {"changelog", "historical_record"}
        if profile.page_type != "redirect":
            stats["orientation_pages"] += orientation_facts["present"]
            stats["managed_orientation_pages"] += (
                orientation_facts["mode"] == ORIENTATION_MODE_MANAGED
            )
            stats["custom_orientation_pages"] += (
                orientation_facts["mode"] == ORIENTATION_MODE_CUSTOM
            )
            stats["valid_page_specific_orientation_pages"] += orientation_facts["valid"]
            stats["generic_v1_orientation_pages"] += orientation_facts["generic_v1"]
            stats["orientation_self_link_pages"] += orientation_facts["self_links"] > 0
            stats["orientation_invalid_link_pages"] += orientation_facts["invalid_links"] > 0

    orientation_required = stats["governed_pages"] - stats["redirect_pages"]
    if orientation_required:
        stats["page_specific_orientation_rate"] = round(
            stats["valid_page_specific_orientation_pages"] / orientation_required,
            6,
        )
    input_counts = Counter(
        profile.orientation_input_sha256
        for profile in profiles
        if profile.orientation_input_sha256 is not None
    )
    render_counts = Counter(
        profile.orientation_render_sha256
        for profile in profiles
        if profile.orientation_render_sha256 is not None
    )
    stats["orientation_input_collision_groups"] = sum(
        count > 1 for count in input_counts.values()
    )
    stats["orientation_input_collision_excess"] = sum(
        count - 1 for count in input_counts.values() if count > 1
    )
    stats["orientation_render_collision_groups"] = sum(
        count > 1 for count in render_counts.values()
    )
    stats["orientation_render_collision_excess"] = sum(
        count - 1 for count in render_counts.values() if count > 1
    )
    if stats["orientation_input_collision_groups"]:
        errors.append("PentaDocs orientation input hashes collide across governed pages")
    if stats["orientation_render_collision_groups"]:
        errors.append("PentaDocs rendered orientations collide across governed pages")
    if orientation_required and stats["page_specific_orientation_rate"] != 1.0:
        errors.append(
            "PentaDocs page-specific orientation rate must be 1.0, found "
            f"{stats['page_specific_orientation_rate']}"
        )

    errors.extend(validate_profile_manifest(root, profiles))
    return errors, stats


def apply_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    docs = load_docs(root)
    navigation = navigation_pages(docs)
    navigated_routes = {route for route, _context in navigation}
    unlisted = load_governed_unlisted_pages(root, navigated_routes)
    governed_pages = [
        (route, context, None) for route, context in navigation
    ] + unlisted
    redirects = redirect_map(docs)
    prior_profiles = load_orientation_profile_records(root)
    changed_paths: list[str] = []
    profiles: list[PageProfile] = []
    sources: list[tuple[str, tuple[str, ...], str | None, Path, str]] = []

    for route, context, disposition in governed_pages:
        if route.startswith(("http://", "https://", "mailto:")):
            continue
        path = route_to_path(root, route)
        if not path.is_file():
            raise ValueError(f"navigation page is missing: {route} -> {path.relative_to(root)}")
        original = path.read_text(encoding="utf-8")
        parsed = split_frontmatter(original)
        if parsed is None:
            raise ValueError(f"missing or malformed frontmatter: {path.relative_to(root)}")
        values = parse_frontmatter(parsed[0]).values
        missing_source_fields = [key for key in ("title", "description") if not values.get(key)]
        if missing_source_fields:
            raise ValueError(
                f"missing source-derived frontmatter fields {missing_source_fields}: "
                f"{path.relative_to(root)}"
            )
        sources.append((route, context, disposition, path, original))

    # Write only after every governed source has passed structural preflight so
    # a malformed late unlisted page cannot leave a partial corpus migration.
    for route, context, disposition, path, original in sources:
        updated, profile = migrate_page(
            root,
            route,
            context,
            original,
            redirects,
            disposition,
            prior_profiles.get(route),
        )
        profiles.append(profile)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_paths.append(path.relative_to(root).as_posix())

    manifest = build_profile_manifest(profiles)
    profile_path = root / PROFILE_PATH
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    rendered_manifest = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if not profile_path.is_file() or profile_path.read_text(encoding="utf-8") != rendered_manifest:
        profile_path.write_text(rendered_manifest, encoding="utf-8")
        changed_paths.append(PROFILE_PATH.as_posix())

    return {
        "schema": "crownthrive.pentadocs.quality-apply/v1",
        "status": "APPLIED",
        "standard_version": STANDARD_VERSION,
        "navigation_pages": len(navigation),
        "governed_unlisted_pages": len(unlisted),
        "governed_pages": len(governed_pages),
        "changed_files": len(changed_paths),
        "changed_paths": sorted(changed_paths),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of scripts/.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Validate without writing (default)")
    mode.add_argument("--apply", action="store_true", help="Apply the deterministic migration")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if args.apply:
        try:
            receipt = apply_repository(root)
        except (OSError, UnicodeError, ValueError) as exc:
            print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
            return 1
        print(json.dumps(receipt, sort_keys=True))

    errors, stats = validate_repository(root)
    receipt = {
        "schema": "crownthrive.pentadocs.quality-validation/v1",
        "status": "FAIL" if errors else "PASS",
        "standard_version": STANDARD_VERSION,
        **stats,
        "error_count": len(errors),
    }
    print(json.dumps(receipt, sort_keys=True))
    for error in errors:
        print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
