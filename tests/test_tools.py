"""Tests for MCP tool functions."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from zendesk_hc_mcp.client import ZendeskHCClient
import zendesk_hc_mcp.tools as tools_mod

SUBDOMAIN = "test.zendesk.com"
BASE = f"https://{SUBDOMAIN}/api/v2"

LOCALES_RESPONSE = {
    "locales": ["en-us", "ru"],
    "default_locale": "en-us",
}

CATEGORIES_RESPONSE = {
    "categories": [
        {"id": 111, "name": "Getting Started", "locale": "en-us", "source_locale": "en-us"},
        {"id": 222, "name": "API Docs", "locale": "en-us", "source_locale": "en-us"},
    ],
    "page": 1, "page_count": 1, "per_page": 100, "count": 2,
}

SECTIONS_RESPONSE = {
    "sections": [
        {"id": 301, "name": "Getting Started Guide", "category_id": 111, "locale": "en-us"},
        {"id": 302, "name": "API Reference", "category_id": 222, "locale": "en-us"},
        {"id": 303, "name": "Billing FAQ", "category_id": 111, "locale": "en-us"},
    ],
    "page": 1, "page_count": 1, "count": 3, "per_page": 100,
}

ARTICLES_IN_SECTION = {
    "articles": [
        {"id": 1001, "title": "Quick Start", "section_id": 301, "body": "<p>Start here</p>"},
        {"id": 1002, "title": "Installation", "section_id": 301, "body": "<p>Install steps</p>"},
    ],
    "meta": {"has_more": False, "after_cursor": None},
}

ARTICLE_RESPONSE = {
    "article": {
        "id": 1001,
        "title": "Quick Start",
        "body": "<h2>Welcome</h2><p>This is the <strong>quick start</strong> guide.</p>",
        "section_id": 301,
        "html_url": "https://test.zendesk.com/hc/en-us/articles/1001",
        "updated_at": "2025-03-15T10:00:00Z",
        "locale": "en-us",
        "draft": False,
        "outdated": False,
        "label_names": ["getting-started", "api"],
    },
}

SEARCH_RESPONSE = {
    "results": [
        {"id": 1001, "title": "Quick Start", "snippet": "This is the <em>quick</em> start guide.", "section_id": 301, "label_names": ["getting-started"]},
        {"id": 1002, "title": "Installation", "snippet": "How to <em>install</em> the tool.", "section_id": 301, "label_names": []},
    ],
    "count": 2, "page": 1, "page_count": 1, "per_page": 10,
}


@pytest.fixture
def client(tmp_path):
    return ZendeskHCClient(cache_dir=tmp_path)


@pytest.fixture
def mock_client(client):
    with patch.object(tools_mod, "hc_client", client):
        yield client


# ── Structure browsing ───────────────────────────────────────────────────


class TestListCategoriesTool:
    @pytest.mark.asyncio
    async def test_output_format(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/locales").mock(
                return_value=httpx.Response(200, json=LOCALES_RESPONSE)
            )
            respx.get(f"{BASE}/help_center/categories").mock(
                return_value=httpx.Response(200, json=CATEGORIES_RESPONSE)
            )
            respx.get(f"{BASE}/help_center/sections").mock(
                return_value=httpx.Response(200, json=SECTIONS_RESPONSE)
            )
            result = await tools_mod.list_categories(SUBDOMAIN)

        assert "default_locale=en-us" in result
        assert "en-us, ru" in result
        assert "Getting Started" in result
        assert "API Docs" in result
        assert "id=111" in result
        assert "id=222" in result
        assert "2 sections" in result
        assert "1 section" in result

    @pytest.mark.asyncio
    async def test_includes_source_locale(self, mock_client):
        cats = {
            "categories": [{"id": 111, "name": "Docs", "locale": "en-us", "source_locale": "ru"}],
            "page": 1, "page_count": 1, "count": 1, "per_page": 100,
        }
        with respx.mock:
            respx.get(f"{BASE}/help_center/locales").mock(
                return_value=httpx.Response(200, json=LOCALES_RESPONSE)
            )
            respx.get(f"{BASE}/help_center/categories").mock(
                return_value=httpx.Response(200, json=cats)
            )
            respx.get(f"{BASE}/help_center/sections").mock(
                return_value=httpx.Response(200, json={"sections": [], "page": 1, "page_count": 1, "count": 0, "per_page": 100})
            )
            result = await tools_mod.list_categories(SUBDOMAIN)

        assert "source_locale=ru" in result

    @pytest.mark.asyncio
    async def test_locale_filter_passed_to_api(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/locales").mock(
                return_value=httpx.Response(200, json=LOCALES_RESPONSE)
            )
            cats_route = respx.get(f"{BASE}/help_center/ru/categories").mock(
                return_value=httpx.Response(200, json={
                    "categories": [], "page": 1, "page_count": 1, "count": 0, "per_page": 100,
                })
            )
            sections_route = respx.get(f"{BASE}/help_center/ru/sections").mock(
                return_value=httpx.Response(200, json={
                    "sections": [], "page": 1, "page_count": 1, "count": 0, "per_page": 100,
                })
            )
            await tools_mod.list_categories(SUBDOMAIN, locale="ru")

        assert cats_route.called
        assert sections_route.called


class TestListSectionsTool:
    @pytest.mark.asyncio
    async def test_all_sections(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/sections").mock(
                return_value=httpx.Response(200, json=SECTIONS_RESPONSE)
            )
            result = await tools_mod.list_sections(SUBDOMAIN)

        assert "Getting Started Guide" in result
        assert "API Reference" in result
        assert "id=301" in result

    @pytest.mark.asyncio
    async def test_filtered_by_category(self, mock_client):
        filtered = {
            "sections": [{"id": 301, "name": "Getting Started Guide", "category_id": 111, "locale": "en-us"}],
            "page": 1, "page_count": 1, "count": 1, "per_page": 100,
        }
        with respx.mock:
            respx.get(f"{BASE}/help_center/categories/111/sections").mock(
                return_value=httpx.Response(200, json=filtered)
            )
            result = await tools_mod.list_sections(SUBDOMAIN, category_id=111)

        assert "Getting Started Guide" in result
        assert "API Reference" not in result

    @pytest.mark.asyncio
    async def test_locale_filter(self, mock_client):
        with respx.mock:
            route = respx.get(f"{BASE}/help_center/ru/sections").mock(
                return_value=httpx.Response(200, json={
                    "sections": [], "page": 1, "page_count": 1, "count": 0, "per_page": 100,
                })
            )
            await tools_mod.list_sections(SUBDOMAIN, locale="ru")
        assert route.called


# ── Content retrieval ────────────────────────────────────────────────────


class TestGetArticleTool:
    @pytest.mark.asyncio
    async def test_returns_markdown_body(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/articles/1001").mock(
                return_value=httpx.Response(200, json=ARTICLE_RESPONSE)
            )
            result = await tools_mod.get_article(SUBDOMAIN, article_id=1001)

        assert "Quick Start" in result
        assert "## Welcome" in result or "Welcome" in result
        assert "quick start" in result
        assert "https://test.zendesk.com/hc/en-us/articles/1001" in result
        assert "getting-started" in result
        assert "api" in result

    @pytest.mark.asyncio
    async def test_draft_and_outdated_flags(self, mock_client):
        draft_article = {"article": {**ARTICLE_RESPONSE["article"], "draft": True, "outdated": True}}
        with respx.mock:
            respx.get(f"{BASE}/help_center/articles/1001").mock(
                return_value=httpx.Response(200, json=draft_article)
            )
            result = await tools_mod.get_article(SUBDOMAIN, article_id=1001)

        assert "[DRAFT]" in result
        assert "[OUTDATED]" in result


class TestGetArticlesBatch:
    @pytest.mark.asyncio
    async def test_multiple_articles(self, mock_client):
        article2 = {
            "article": {
                "id": 1002, "title": "Installation", "body": "<p>Install the tool.</p>",
                "section_id": 301, "html_url": "https://test.zendesk.com/hc/en-us/articles/1002",
                "updated_at": "2025-03-16T10:00:00Z", "locale": "en-us",
            },
        }
        with respx.mock:
            respx.get(f"{BASE}/help_center/articles/1001").mock(
                return_value=httpx.Response(200, json=ARTICLE_RESPONSE)
            )
            respx.get(f"{BASE}/help_center/articles/1002").mock(
                return_value=httpx.Response(200, json=article2)
            )
            result = await tools_mod.get_articles(SUBDOMAIN, article_ids=[1001, 1002])

        assert "Quick Start" in result
        assert "Installation" in result
        assert "Updated:" in result or "2025-03" in result

    @pytest.mark.asyncio
    async def test_partial_failure(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/articles/1001").mock(
                return_value=httpx.Response(200, json=ARTICLE_RESPONSE)
            )
            respx.get(f"{BASE}/help_center/articles/9999").mock(
                return_value=httpx.Response(404, json={"error": "Not found"})
            )
            result = await tools_mod.get_articles(SUBDOMAIN, article_ids=[1001, 9999])

        assert "Quick Start" in result
        assert "error" in result.lower() or "9999" in result


class TestGetSectionArticlesTool:
    @pytest.mark.asyncio
    async def test_toc_only_default(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/sections/301/articles").mock(
                return_value=httpx.Response(200, json=ARTICLES_IN_SECTION)
            )
            result = await tools_mod.get_section_articles(SUBDOMAIN, section_id=301)

        assert "Quick Start" in result
        assert "Installation" in result
        assert "id=1001" in result
        assert "Start here" not in result

    @pytest.mark.asyncio
    async def test_with_body(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/sections/301/articles").mock(
                return_value=httpx.Response(200, json=ARTICLES_IN_SECTION)
            )
            result = await tools_mod.get_section_articles(SUBDOMAIN, section_id=301, include_body=True)

        assert "Quick Start" in result
        assert "Start here" in result
        assert "Install steps" in result

    @pytest.mark.asyncio
    async def test_max_articles_respected(self, mock_client):
        many = {
            "articles": [{"id": i, "title": f"Article {i}", "section_id": 301, "body": f"<p>Body {i}</p>"} for i in range(1, 6)],
            "meta": {"has_more": False, "after_cursor": None},
        }
        with respx.mock:
            respx.get(f"{BASE}/help_center/sections/301/articles").mock(
                return_value=httpx.Response(200, json=many)
            )
            result = await tools_mod.get_section_articles(SUBDOMAIN, section_id=301, include_body=True, max_articles=2)

        assert "Body 1" in result
        assert "Body 2" in result
        assert "Body 3" not in result
        assert "5 articles" in result

    @pytest.mark.asyncio
    async def test_locale_filter(self, mock_client):
        with respx.mock:
            route = respx.get(f"{BASE}/help_center/ru/sections/301/articles").mock(
                return_value=httpx.Response(200, json={
                    "articles": [], "meta": {"has_more": False, "after_cursor": None},
                })
            )
            await tools_mod.get_section_articles(SUBDOMAIN, section_id=301, locale="ru")
        assert route.called


class TestSearchArticlesTool:
    @pytest.mark.asyncio
    async def test_returns_snippets_no_bodies(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/articles/search").mock(
                return_value=httpx.Response(200, json=SEARCH_RESPONSE)
            )
            result = await tools_mod.search_articles(SUBDOMAIN, query="quick")

        assert "Quick Start" in result
        assert "quick start guide" in result or "quick" in result
        assert "<em>" not in result

    @pytest.mark.asyncio
    async def test_total_results_shown(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/articles/search").mock(
                return_value=httpx.Response(200, json=SEARCH_RESPONSE)
            )
            result = await tools_mod.search_articles(SUBDOMAIN, query="quick")

        assert "2 results" in result

    @pytest.mark.asyncio
    async def test_labels_in_results(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/articles/search").mock(
                return_value=httpx.Response(200, json=SEARCH_RESPONSE)
            )
            result = await tools_mod.search_articles(SUBDOMAIN, query="quick")

        assert "getting-started" in result

    @pytest.mark.asyncio
    async def test_section_id_in_results(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/articles/search").mock(
                return_value=httpx.Response(200, json=SEARCH_RESPONSE)
            )
            result = await tools_mod.search_articles(SUBDOMAIN, query="quick")

        assert "section_id=301" in result


# ── Community ────────────────────────────────────────────────────────────


class TestCommunityTools:
    @pytest.mark.asyncio
    async def test_list_topics(self, mock_client):
        topics_resp = {
            "topics": [
                {"id": 501, "name": "General Discussion", "description": "Chat here"},
                {"id": 502, "name": "Feature Requests", "description": "Ideas"},
            ],
            "page": 1, "page_count": 1, "count": 2, "per_page": 100,
        }
        with respx.mock:
            respx.get(f"{BASE}/community/topics").mock(
                return_value=httpx.Response(200, json=topics_resp)
            )
            result = await tools_mod.list_community_topics(SUBDOMAIN)

        assert "General Discussion" in result
        assert "Feature Requests" in result

    @pytest.mark.asyncio
    async def test_list_posts_with_preview(self, mock_client):
        posts_resp = {
            "posts": [{
                "id": 601, "title": "Tax mapping issue",
                "details": "<p>I'm trying to map different tax rates depending on the booking date range.</p>",
                "comment_count": 3,
            }],
            "page": 1, "page_count": 1, "count": 1, "per_page": 10,
        }
        with respx.mock:
            respx.get(f"{BASE}/community/posts").mock(
                return_value=httpx.Response(200, json=posts_resp)
            )
            result = await tools_mod.list_community_posts(SUBDOMAIN)

        assert "Tax mapping issue" in result
        assert "3 comments" in result or "3 comment" in result
        assert "tax rates" in result.lower() or "map different" in result.lower()

    @pytest.mark.asyncio
    async def test_get_post_with_comments(self, mock_client):
        post_resp = {
            "post": {
                "id": 601, "title": "Tax mapping issue",
                "details": "<p>I'm trying to map <strong>different tax rates</strong>.</p>",
                "html_url": "https://test.zendesk.com/hc/en-us/community/posts/601",
                "created_at": "2025-01-10T08:00:00Z",
            },
        }
        comments_resp = {
            "comments": [
                {"id": 701, "body": "<p>Have you tried the API?</p>", "author_id": 100, "created_at": "2025-01-11T09:00:00Z"},
                {"id": 702, "body": "<p>This worked for me.</p>", "author_id": 200, "created_at": "2025-01-12T10:00:00Z"},
            ],
            "page": 1, "page_count": 1, "count": 2, "per_page": 100,
        }
        with respx.mock:
            respx.get(f"{BASE}/community/posts/601").mock(
                return_value=httpx.Response(200, json=post_resp)
            )
            respx.get(f"{BASE}/community/posts/601/comments").mock(
                return_value=httpx.Response(200, json=comments_resp)
            )
            result = await tools_mod.get_community_post(SUBDOMAIN, post_id=601)

        assert "Tax mapping issue" in result
        assert "different tax rates" in result
        assert "Have you tried the API?" in result
        assert "This worked for me." in result
        assert "https://test.zendesk.com/hc/en-us/community/posts/601" in result


# ── Edge cases ───────────────────────────────────────────────────────────


class TestEmptyResults:
    @pytest.mark.asyncio
    async def test_empty_categories(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/locales").mock(
                return_value=httpx.Response(200, json=LOCALES_RESPONSE)
            )
            respx.get(f"{BASE}/help_center/categories").mock(
                return_value=httpx.Response(200, json={
                    "categories": [], "page": 1, "page_count": 1, "count": 0, "per_page": 100,
                })
            )
            respx.get(f"{BASE}/help_center/sections").mock(
                return_value=httpx.Response(200, json={
                    "sections": [], "page": 1, "page_count": 1, "count": 0, "per_page": 100,
                })
            )
            result = await tools_mod.list_categories(SUBDOMAIN)
        assert "0 categories" in result or "no categories" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_search(self, mock_client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/articles/search").mock(
                return_value=httpx.Response(200, json={
                    "results": [], "count": 0, "page": 1, "page_count": 0, "per_page": 10,
                })
            )
            result = await tools_mod.search_articles(SUBDOMAIN, query="nonexistent")
        assert "0 results" in result
