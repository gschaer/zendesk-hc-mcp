"""Async HTTP client for Zendesk Help Center API with hishel caching."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"
DEFAULT_CACHE_TTL = 7 * 24 * 3600  # 7 days in seconds

def _get_cache_ttl() -> int:
    """Read cache TTL from ZENDESK_HC_CACHE_TTL env var (in seconds), or use default."""
    val = os.environ.get("ZENDESK_HC_CACHE_TTL")
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return DEFAULT_CACHE_TTL
MAX_CURSOR_PAGES = 20
MAX_OFFSET_PAGES = 10


class ZendeskHCClient:
    """Async HTTP client for Zendesk Help Center API with hishel caching."""

    def __init__(self, cache_dir: Path = CACHE_DIR) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._storage = None

        try:
            import hishel
            from hishel.httpx import AsyncCacheTransport

            self._storage = hishel.AsyncSqliteStorage(
                database_path=self._cache_dir / "cache.db",
                default_ttl=_get_cache_ttl(),
            )
            policy = hishel.FilterPolicy()
            transport = AsyncCacheTransport(
                next_transport=httpx.AsyncHTTPTransport(),
                storage=self._storage,
                policy=policy,
            )
            self._client = httpx.AsyncClient(
                transport=transport, follow_redirects=True, timeout=30.0,
            )
            self._nocache_client = httpx.AsyncClient(
                follow_redirects=True, timeout=30.0,
            )
        except Exception:
            self._client = httpx.AsyncClient(
                follow_redirects=True, timeout=30.0,
            )
            self._nocache_client = self._client

    @staticmethod
    def _validate_subdomain(subdomain: str) -> None:
        if subdomain.startswith(("http://", "https://")):
            raise ValueError(
                f"Subdomain should not include protocol prefix: {subdomain!r}. "
                "Use just the hostname, e.g. 'support.example.com'"
            )

    async def get(
        self,
        subdomain: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """GET a single API endpoint. Returns parsed JSON or an error dict."""
        self._validate_subdomain(subdomain)
        url = f"https://{subdomain}/api/v2/{path}"

        client = self._nocache_client if force_refresh else self._client

        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code} from {subdomain}: {exc.response.text[:200]}"}
        except httpx.ConnectError:
            return {"error": f"Connection failed to {subdomain}. Check the subdomain is correct and reachable."}
        except (json.JSONDecodeError, ValueError):
            return {"error": f"Invalid JSON response from {subdomain} for {path}"}
        except httpx.RequestError as exc:
            return {"error": f"Request error for {subdomain}: {exc}"}

    async def get_all_cursor_pages(
        self,
        subdomain: str,
        path: str,
        collection_key: str,
        *,
        params: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Auto-paginate cursor-based endpoints (articles). Returns all items."""
        all_items: list[dict[str, Any]] = []
        request_params = dict(params or {})
        request_params.setdefault("page[size]", 50)

        for _ in range(MAX_CURSOR_PAGES):
            data = await self.get(subdomain, path, params=request_params, force_refresh=force_refresh)
            if "error" in data:
                break
            all_items.extend(data.get(collection_key, []))
            meta = data.get("meta", {})
            if not meta.get("has_more"):
                break
            request_params["page[after]"] = meta["after_cursor"]

        return all_items

    async def get_all_offset_pages(
        self,
        subdomain: str,
        path: str,
        collection_key: str,
        *,
        params: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Auto-paginate offset-based endpoints. Returns all items."""
        all_items: list[dict[str, Any]] = []
        request_params = dict(params or {})
        request_params.setdefault("per_page", 100)

        for page_num in range(1, MAX_OFFSET_PAGES + 1):
            request_params["page"] = page_num
            data = await self.get(subdomain, path, params=request_params, force_refresh=force_refresh)
            if "error" in data:
                break
            all_items.extend(data.get(collection_key, []))
            page_count = data.get("page_count", 1)
            if page_num >= page_count:
                break

        return all_items
