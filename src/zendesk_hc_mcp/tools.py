"""MCP tool definitions for Zendesk Help Center."""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

from mcp.server.fastmcp import FastMCP

from zendesk_hc_mcp.client import ZendeskHCClient
from zendesk_hc_mcp.helpers import html_to_md, locale_path, pluralize, strip_em_tags, truncate

mcp = FastMCP("zendesk-hc")
hc_client = ZendeskHCClient()


@mcp.tool()
async def list_categories(
    subdomain: str,
    locale: str | None = None,
    force_refresh: bool = False,
) -> str:
    """Browse a Zendesk Help Center's structure: available locales, categories, and section counts.

    This is the recommended first call to understand what content a Help Center offers.

    Args:
        subdomain: Help Center hostname, e.g. "support.zendesk.com"
        locale: Optional locale filter, e.g. "en-us"
        force_refresh: Bypass cache and fetch fresh data
    """
    locales_task = hc_client.get(subdomain, "help_center/locales", force_refresh=force_refresh)
    cats_task = hc_client.get_all_offset_pages(
        subdomain, locale_path("help_center/categories", locale), "categories",
        force_refresh=force_refresh,
    )
    sections_task = hc_client.get_all_offset_pages(
        subdomain, locale_path("help_center/sections", locale), "sections",
        force_refresh=force_refresh,
    )
    locales_data, categories, sections = await asyncio.gather(locales_task, cats_task, sections_task)

    section_counts: Counter[int] = Counter()
    for s in sections:
        section_counts[s.get("category_id", 0)] += 1

    lines: list[str] = []

    if "error" not in locales_data:
        default = locales_data.get("default_locale", "?")
        all_locales = ", ".join(locales_data.get("locales", []))
        lines.append(f"{subdomain} | default_locale={default} | locales: {all_locales}")
    else:
        lines.append(subdomain)

    lines.append("")
    lines.append(f"{pluralize(len(categories), 'category')}:")

    for cat in categories:
        cat_id = cat["id"]
        name = cat.get("name", "Untitled")
        src_locale = cat.get("source_locale", "")
        sc = section_counts.get(cat_id, 0)
        parts = [f"id={cat_id}", name, pluralize(sc, "section")]
        if src_locale:
            parts.append(f"source_locale={src_locale}")
        lines.append(" | ".join(parts))

    return "\n".join(lines)


@mcp.tool()
async def list_sections(
    subdomain: str,
    category_id: int | None = None,
    locale: str | None = None,
    force_refresh: bool = False,
) -> str:
    """List sections in a Help Center, optionally filtered to a category.

    Use category IDs from list_categories. Then use section IDs with get_section_articles.

    Args:
        subdomain: Help Center hostname
        category_id: Optional category ID from list_categories
        locale: Optional locale filter
        force_refresh: Bypass cache and fetch fresh data
    """
    if category_id:
        base_path = f"help_center/categories/{category_id}/sections"
    else:
        base_path = "help_center/sections"

    sections = await hc_client.get_all_offset_pages(
        subdomain, locale_path(base_path, locale), "sections", force_refresh=force_refresh,
    )

    lines: list[str] = []
    header = f"{pluralize(len(sections), 'section')}"
    if category_id:
        header += f" in category_id={category_id}"
    lines.append(f"{header}:")

    for s in sections:
        sid = s["id"]
        name = s.get("name", "Untitled")
        lines.append(f"id={sid} | {name}")

    return "\n".join(lines)


@mcp.tool()
async def get_article(
    subdomain: str,
    article_id: int,
    force_refresh: bool = False,
) -> str:
    """Fetch a single article with its full content converted to markdown.

    Args:
        subdomain: Help Center hostname
        article_id: Article ID to fetch
        force_refresh: Bypass cache and fetch fresh data
    """
    data = await hc_client.get(
        subdomain, f"help_center/articles/{article_id}", force_refresh=force_refresh,
    )
    if "error" in data:
        return f"Error fetching article {article_id}: {data['error']}"

    article = data.get("article", data)
    title = article.get("title", "Untitled")
    body_md = html_to_md(article.get("body"))
    url = article.get("html_url", "")
    updated = article.get("updated_at", "")[:10]
    draft = article.get("draft", False)
    outdated = article.get("outdated", False)

    labels = article.get("label_names", [])

    header = f"Article: {title} (id={article_id})"
    if draft:
        header += " [DRAFT]"
    if outdated:
        header += " [OUTDATED]"

    lines = [
        header,
        f"Updated: {updated}",
        f"URL: {url}",
    ]
    if labels:
        lines.append(f"Labels: {', '.join(labels)}")
    lines.append("")
    lines.append(body_md)
    return "\n".join(lines)


@mcp.tool()
async def get_articles(
    subdomain: str,
    article_ids: list[int],
    force_refresh: bool = False,
) -> str:
    """Batch fetch multiple articles with full markdown bodies (concurrent requests).

    Args:
        subdomain: Help Center hostname
        article_ids: List of article IDs to fetch
        force_refresh: Bypass cache and fetch fresh data
    """
    async def fetch_one(aid: int) -> tuple[int, dict[str, Any]]:
        data = await hc_client.get(
            subdomain, f"help_center/articles/{aid}", force_refresh=force_refresh,
        )
        return aid, data

    results = await asyncio.gather(*(fetch_one(aid) for aid in article_ids))

    lines: list[str] = []
    for aid, data in results:
        if "error" in data:
            lines.append(f"=== Article {aid} ===")
            lines.append(f"Error: {data['error']}")
            lines.append("")
            continue

        article = data.get("article", data)
        title = article.get("title", "Untitled")
        body_md = html_to_md(article.get("body"))
        url = article.get("html_url", "")
        updated = article.get("updated_at", "")[:10]
        labels = article.get("label_names", [])

        lines.append(f"=== {title} (id={aid}) ===")
        meta = f"Updated: {updated} | URL: {url}"
        if labels:
            meta += f" | Labels: {', '.join(labels)}"
        lines.append(meta)
        lines.append("")
        lines.append(body_md)
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def get_section_articles(
    subdomain: str,
    section_id: int,
    locale: str | None = None,
    include_body: bool = False,
    max_articles: int = 10,
    force_refresh: bool = False,
) -> str:
    """Fetch articles in a section. Returns TOC by default; set include_body=True for full text.

    Use section IDs from list_sections. Use article IDs from the TOC with get_article or get_articles.

    Args:
        subdomain: Help Center hostname
        section_id: Section ID from list_sections
        locale: Optional locale filter
        include_body: If True, include full markdown article bodies
        max_articles: Max articles to include bodies for (default 10)
        force_refresh: Bypass cache and fetch fresh data
    """
    articles = await hc_client.get_all_cursor_pages(
        subdomain,
        locale_path(f"help_center/sections/{section_id}/articles", locale),
        "articles",
        force_refresh=force_refresh,
    )

    total = len(articles)
    lines: list[str] = []

    if include_body:
        show = articles[:max_articles]
        header = f"Section section_id={section_id} | {pluralize(total, 'article')}"
        if total > max_articles:
            header += f" (showing {max_articles})"
        lines.append(header)
        lines.append("")

        lines.append("=== TOC ===")
        for i, a in enumerate(show, 1):
            lines.append(f"{i}. {a.get('title', 'Untitled')} (id={a['id']})")
        lines.append("")

        for i, a in enumerate(show, 1):
            title = a.get("title", "Untitled")
            body_md = html_to_md(a.get("body"))
            lines.append(f"=== {i}. {title} ===")
            lines.append(body_md)
            lines.append("")
    else:
        lines.append(f"Section section_id={section_id} | {pluralize(total, 'article')}:")
        lines.append("")
        for a in articles:
            lines.append(f"id={a['id']} | {a.get('title', 'Untitled')}")

    return "\n".join(lines)


@mcp.tool()
async def search_articles(
    subdomain: str,
    query: str,
    locale: str | None = None,
    limit: int = 10,
    force_refresh: bool = False,
) -> str:
    """Search articles by keyword. Returns titles and snippets (no full bodies).

    Args:
        subdomain: Help Center hostname
        query: Search query string
        locale: Optional locale filter
        limit: Max results to return (default 10)
        force_refresh: Bypass cache and fetch fresh data
    """
    params: dict[str, Any] = {"query": query, "per_page": min(limit, 100)}
    if locale:
        params["locale"] = locale

    data = await hc_client.get(
        subdomain, "help_center/articles/search", params=params, force_refresh=force_refresh,
    )
    if "error" in data:
        return f"Error searching: {data['error']}"

    results = data.get("results", [])
    total = data.get("count", len(results))
    showing = min(len(results), limit)

    lines: list[str] = [f"{pluralize(total, 'result')} for \"{query}\" (showing {showing}):"]
    lines.append("")

    for r in results[:limit]:
        title = r.get("title", "Untitled")
        rid = r.get("id", "?")
        sid = r.get("section_id", "")
        labels = r.get("label_names", [])
        snippet = strip_em_tags(r.get("snippet", ""))
        parts = [f"id={rid}", title]
        if sid:
            parts.append(f"section_id={sid}")
        if labels:
            parts.append(f"labels: {', '.join(labels)}")
        lines.append(" | ".join(parts))
        if snippet:
            lines.append(f"  {snippet}")

    return "\n".join(lines)


@mcp.tool()
async def list_community_topics(
    subdomain: str,
    force_refresh: bool = False,
) -> str:
    """List community/forum topics in a Help Center.

    Args:
        subdomain: Help Center hostname
        force_refresh: Bypass cache and fetch fresh data
    """
    topics = await hc_client.get_all_offset_pages(
        subdomain, "community/topics", "topics", force_refresh=force_refresh,
    )

    lines: list[str] = [f"{pluralize(len(topics), 'topic')}:"]
    for t in topics:
        name = t.get("name", "Untitled")
        desc = t.get("description", "")
        tid = t["id"]
        parts = [f"id={tid}", name]
        if desc:
            parts.append(desc)
        lines.append(" | ".join(parts))

    return "\n".join(lines)


@mcp.tool()
async def list_community_posts(
    subdomain: str,
    topic_id: int | None = None,
    limit: int = 10,
    force_refresh: bool = False,
) -> str:
    """List community posts with body previews and comment counts.

    Args:
        subdomain: Help Center hostname
        topic_id: Optional topic ID to filter posts
        limit: Max posts to return (default 10)
        force_refresh: Bypass cache and fetch fresh data
    """
    if topic_id:
        path = f"community/topics/{topic_id}/posts"
    else:
        path = "community/posts"

    data = await hc_client.get(
        subdomain, path, params={"per_page": min(limit, 100)}, force_refresh=force_refresh,
    )
    if "error" in data:
        return f"Error fetching posts: {data['error']}"

    posts = data.get("posts", [])
    total = data.get("count", len(posts))

    lines: list[str] = [f"{pluralize(total, 'post')} (showing {min(len(posts), limit)}):"]
    lines.append("")

    for p in posts[:limit]:
        title = p.get("title", "Untitled")
        pid = p["id"]
        cc = p.get("comment_count", 0)
        details_text = html_to_md(p.get("details"))
        preview = truncate(details_text, 200)
        lines.append(f"id={pid} | {title} | {pluralize(cc, 'comment')}")
        if preview:
            lines.append(f"  Preview: {preview}")

    return "\n".join(lines)


@mcp.tool()
async def get_community_post(
    subdomain: str,
    post_id: int,
    force_refresh: bool = False,
) -> str:
    """Fetch a community post with its full body and comments.

    Args:
        subdomain: Help Center hostname
        post_id: Post ID to fetch
        force_refresh: Bypass cache and fetch fresh data
    """
    post_task = hc_client.get(subdomain, f"community/posts/{post_id}", force_refresh=force_refresh)
    comments_task = hc_client.get_all_offset_pages(
        subdomain, f"community/posts/{post_id}/comments", "comments",
        force_refresh=force_refresh,
    )
    post_data, comments = await asyncio.gather(post_task, comments_task)

    if "error" in post_data:
        return f"Error fetching post {post_id}: {post_data['error']}"

    post = post_data.get("post", post_data)
    title = post.get("title", "Untitled")
    body_md = html_to_md(post.get("details"))
    url = post.get("html_url", "")
    created = post.get("created_at", "")[:10]

    lines = [
        f"Post: {title} (id={post_id})",
        f"Created: {created}",
        f"URL: {url}",
        "",
        body_md,
    ]

    if comments:
        lines.append("")
        lines.append(f"--- {pluralize(min(len(comments), 20), 'comment')} ---")
        for c in comments[:20]:
            comment_body = html_to_md(c.get("body"))
            comment_date = c.get("created_at", "")[:10]
            lines.append("")
            lines.append(f"[{comment_date}]")
            lines.append(comment_body)

    return "\n".join(lines)
