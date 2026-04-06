"""Tests for ZendeskHCClient — HTTP, error handling, pagination."""

from __future__ import annotations

import httpx
import pytest
import respx

from zendesk_hc_mcp.client import ZendeskHCClient, _get_cache_ttl, DEFAULT_CACHE_TTL

SUBDOMAIN = "test.zendesk.com"
BASE = f"https://{SUBDOMAIN}/api/v2"

CATEGORIES_RESPONSE = {
    "categories": [
        {"id": 111, "name": "Getting Started", "locale": "en-us", "source_locale": "en-us"},
        {"id": 222, "name": "API Docs", "locale": "en-us", "source_locale": "en-us"},
    ],
    "page": 1,
    "page_count": 1,
    "per_page": 100,
    "count": 2,
}


@pytest.fixture
def client(tmp_path):
    return ZendeskHCClient(cache_dir=tmp_path)


# ── Cache TTL config ─────────────────────────────────────────────────────


class TestCacheTTL:
    def test_default_ttl(self, monkeypatch):
        monkeypatch.delenv("ZENDESK_HC_CACHE_TTL", raising=False)
        assert _get_cache_ttl() == DEFAULT_CACHE_TTL

    def test_custom_ttl(self, monkeypatch):
        monkeypatch.setenv("ZENDESK_HC_CACHE_TTL", "86400")
        assert _get_cache_ttl() == 86400

    def test_invalid_ttl_falls_back(self, monkeypatch):
        monkeypatch.setenv("ZENDESK_HC_CACHE_TTL", "not-a-number")
        assert _get_cache_ttl() == DEFAULT_CACHE_TTL


# ── Single GET ───────────────────────────────────────────────────────────


class TestClientGet:
    @pytest.mark.asyncio
    async def test_get_categories(self, client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/categories").mock(
                return_value=httpx.Response(200, json=CATEGORIES_RESPONSE)
            )
            data = await client.get(SUBDOMAIN, "help_center/categories")
        assert data["categories"][0]["name"] == "Getting Started"
        assert len(data["categories"]) == 2

    @pytest.mark.asyncio
    async def test_http_404_error(self, client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/articles/99999").mock(
                return_value=httpx.Response(404, json={"error": "RecordNotFound"})
            )
            data = await client.get(SUBDOMAIN, "help_center/articles/99999")
        assert "error" in data
        assert "404" in data["error"]

    @pytest.mark.asyncio
    async def test_http_500_error(self, client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/categories").mock(
                return_value=httpx.Response(500, text="Internal Server Error")
            )
            data = await client.get(SUBDOMAIN, "help_center/categories")
        assert "error" in data
        assert "500" in data["error"]

    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/categories").mock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            data = await client.get(SUBDOMAIN, "help_center/categories")
        assert "error" in data
        assert "connect" in data["error"].lower() or "connection" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_subdomain_with_protocol(self, client):
        with pytest.raises(ValueError, match="protocol"):
            await client.get("https://test.zendesk.com", "help_center/categories")

    @pytest.mark.asyncio
    async def test_get_with_params(self, client):
        with respx.mock:
            route = respx.get(f"{BASE}/help_center/categories").mock(
                return_value=httpx.Response(200, json=CATEGORIES_RESPONSE)
            )
            await client.get(SUBDOMAIN, "help_center/categories", params={"page": 2})
        assert route.called
        assert "page=2" in str(route.calls[0].request.url)

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, client):
        with respx.mock:
            respx.get(f"{BASE}/help_center/categories").mock(
                return_value=httpx.Response(200, text="<html>Maintenance</html>",
                                           headers={"content-type": "text/html"})
            )
            data = await client.get(SUBDOMAIN, "help_center/categories")
        assert "error" in data
        assert "Invalid JSON" in data["error"]

    @pytest.mark.asyncio
    async def test_force_refresh_uses_nocache_client(self, client):
        with respx.mock:
            route = respx.get(f"{BASE}/help_center/locales").mock(
                return_value=httpx.Response(200, json={"locales": ["en-us"], "default_locale": "en-us"})
            )
            await client.get(SUBDOMAIN, "help_center/locales")
            await client.get(SUBDOMAIN, "help_center/locales", force_refresh=True)
        assert route.call_count == 2


# ── Cursor pagination ────────────────────────────────────────────────────


class TestCursorPagination:
    @pytest.mark.asyncio
    async def test_two_pages(self, client):
        page1 = {
            "articles": [{"id": 1, "title": "A1"}, {"id": 2, "title": "A2"}],
            "meta": {"has_more": True, "after_cursor": "cursor_abc"},
            "links": {"next": "..."},
        }
        page2 = {
            "articles": [{"id": 3, "title": "A3"}],
            "meta": {"has_more": False, "after_cursor": None},
            "links": {},
        }
        with respx.mock:
            route = respx.get(f"{BASE}/help_center/sections/100/articles")
            route.side_effect = [
                httpx.Response(200, json=page1),
                httpx.Response(200, json=page2),
            ]
            items = await client.get_all_cursor_pages(
                SUBDOMAIN, "help_center/sections/100/articles", "articles"
            )
        assert len(items) == 3
        assert items[2]["title"] == "A3"

    @pytest.mark.asyncio
    async def test_pagination_cap(self, client):
        def make_page(cursor_num: int):
            return httpx.Response(
                200,
                json={
                    "articles": [{"id": cursor_num, "title": f"A{cursor_num}"}],
                    "meta": {"has_more": True, "after_cursor": f"cursor_{cursor_num + 1}"},
                },
            )

        with respx.mock:
            route = respx.get(f"{BASE}/help_center/sections/100/articles")
            route.side_effect = [make_page(i) for i in range(25)]
            items = await client.get_all_cursor_pages(
                SUBDOMAIN, "help_center/sections/100/articles", "articles"
            )
        assert len(items) == 20


# ── Offset pagination ────────────────────────────────────────────────────


class TestOffsetPagination:
    @pytest.mark.asyncio
    async def test_two_pages(self, client):
        page1 = {
            "sections": [{"id": 1, "name": "S1"}, {"id": 2, "name": "S2"}],
            "page": 1, "page_count": 2, "count": 3, "per_page": 2,
        }
        page2 = {
            "sections": [{"id": 3, "name": "S3"}],
            "page": 2, "page_count": 2, "count": 3, "per_page": 2,
        }
        with respx.mock:
            route = respx.get(f"{BASE}/help_center/sections")
            route.side_effect = [
                httpx.Response(200, json=page1),
                httpx.Response(200, json=page2),
            ]
            items = await client.get_all_offset_pages(
                SUBDOMAIN, "help_center/sections", "sections"
            )
        assert len(items) == 3
        assert items[2]["name"] == "S3"

    @pytest.mark.asyncio
    async def test_single_page(self, client):
        page1 = {
            "categories": [{"id": 1, "name": "C1"}],
            "page": 1, "page_count": 1, "count": 1, "per_page": 100,
        }
        with respx.mock:
            route = respx.get(f"{BASE}/help_center/categories")
            route.mock(return_value=httpx.Response(200, json=page1))
            items = await client.get_all_offset_pages(
                SUBDOMAIN, "help_center/categories", "categories"
            )
        assert len(items) == 1
        assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_search_pagination(self, client):
        page1 = {
            "results": [{"id": 1, "title": "R1"}],
            "page": 1, "page_count": 2, "count": 2, "per_page": 1,
        }
        page2 = {
            "results": [{"id": 2, "title": "R2"}],
            "page": 2, "page_count": 2, "count": 2, "per_page": 1,
        }
        with respx.mock:
            route = respx.get(f"{BASE}/help_center/articles/search")
            route.side_effect = [
                httpx.Response(200, json=page1),
                httpx.Response(200, json=page2),
            ]
            items = await client.get_all_offset_pages(
                SUBDOMAIN, "help_center/articles/search", "results",
                params={"query": "test"},
            )
        assert len(items) == 2
