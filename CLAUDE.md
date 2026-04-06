# Zendesk HC MCP Server

## Project Overview

MCP server that provides read-only access to public Zendesk Help Center APIs. No authentication required — works with any public HC.

## Development

- **Run tests:** `uv run pytest -v`
- **Run server:** `uv run zendesk-hc-mcp` (stdio transport, will hang waiting for input — that's expected)
- **Add dependency:** `uv add <package>` (dev: `uv add --dev <package>`)

## Architecture

```
src/zendesk_hc_mcp/
  __init__.py    — package root, exports main()
  helpers.py     — pure functions: html_to_md, pluralize, locale_path, etc.
  client.py      — ZendeskHCClient (HTTP + hishel caching + pagination)
  tools.py       — 9 MCP tool functions + FastMCP instance + global hc_client
  server.py      — entry point: imports tools, calls mcp.run()

tests/
  test_helpers.py — pure function tests (no mocking needed)
  test_client.py  — HTTP client tests (respx-mocked)
  test_tools.py   — MCP tool output tests (respx-mocked, patches hc_client)

doc/oas.yaml     — Zendesk Help Center OpenAPI spec (reference only)
```

### Key design decisions

- `helpers.py` has zero I/O — all pure functions, independently testable
- `client.py` has no MCP dependency — just httpx + hishel
- `tools.py` owns the `FastMCP` instance and the global `hc_client`
- `server.py` is a thin entry point that imports tools (which registers them) and runs
- All tools return error strings (not exceptions) so the agent always gets a usable message

### Caching

Uses hishel `FilterPolicy` (SQLite-backed) with 7-day TTL. Cache at `.cache/` (project-local, gitignored).
All tools accept `force_refresh=True` which uses a separate non-cached httpx client.

### Pagination

- Articles: cursor-based (`page[size]`, `meta.after_cursor`, `meta.has_more`)
- Everything else: offset-based (`page`, `per_page`, `page_count`)

## Testing

All development follows TDD. Tests use `respx` to mock httpx requests — no network calls.

### Running tests

```bash
# All tests
uv run pytest -v

# Just helpers
uv run pytest tests/test_helpers.py -v

# Just client
uv run pytest tests/test_client.py -v

# Just tools
uv run pytest tests/test_tools.py -v

# With coverage
uv run pytest --cov=zendesk_hc_mcp --cov-report=term-missing -v
```
