"""Pure helper functions — no I/O, no dependencies on client or MCP."""

from __future__ import annotations

import re

from markdownify import markdownify


def html_to_md(html: str | None) -> str:
    """Convert HTML to markdown. Returns empty string for None/empty input."""
    if not html:
        return ""
    return markdownify(html, strip=["img"], heading_style="ATX").strip()


def strip_em_tags(text: str) -> str:
    """Remove <em> tags from search snippets."""
    return re.sub(r"</?em>", "", text)


def truncate(text: str, max_chars: int = 200) -> str:
    """Truncate text to max_chars, adding ellipsis if needed."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "..."


def pluralize(count: int, singular: str) -> str:
    if count == 1:
        return f"1 {singular}"
    if singular.endswith("y") and not singular.endswith(("ay", "ey", "oy", "uy")):
        return f"{count} {singular[:-1]}ies"
    return f"{count} {singular}s"


def locale_path(base_path: str, locale: str | None) -> str:
    """Insert locale into the Help Center API path if provided.

    Zendesk HC endpoints accept an optional locale segment:
    /api/v2/help_center/{locale}/categories
    """
    if locale:
        parts = base_path.split("/", 1)
        if len(parts) == 2:
            return f"{parts[0]}/{locale}/{parts[1]}"
    return base_path
