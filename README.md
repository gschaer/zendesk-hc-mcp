# Zendesk Help Center MCP Server

A read-only MCP (Model Context Protocol) server for querying public Zendesk Help Center APIs. Lets AI agents browse, search, and fetch documentation from any public Zendesk Help Center.

## Features

- Browse Help Center structure (categories, sections, articles)
- Fetch article content as clean markdown
- Search articles by keyword
- Browse community posts and comments
- Locale-aware (filter by language)
- HTTP response caching (7-day TTL via hishel)
- Works with any public Zendesk Help Center (no auth required)

## Installation

Requires Python 3.10+.

```bash
git clone <repo-url>
cd zendesk
uv sync
```

Or with pip:

```bash
pip install -e .
```

## Configuration

### Claude Code

Add a `.mcp.json` file to your project root (or any project that needs Zendesk HC access):

```json
{
  "mcpServers": {
    "zendesk-hc": {
      "command": "uv",
      "args": ["--directory", "/path/to/zendesk-hc-mcp", "run", "zendesk-hc-mcp"]
    }
  }
}
```

Replace `/path/to/zendesk-hc-mcp` with the **absolute path** to where you cloned this repo. Do not use `~` — tilde expansion does not work in MCP config.

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "zendesk-hc": {
      "command": "uv",
      "args": ["--directory", "/path/to/zendesk-hc-mcp", "run", "zendesk-hc-mcp"]
    }
  }
}
```

Note: `uv` must be on `PATH` for the MCP host process to find it.

## Available Tools

All tools take `subdomain` as the first parameter (e.g., `"support.zendesk.com"`). All tools accept `force_refresh=True` to bypass the cache. Most tools accept an optional `locale` parameter (e.g., `"en-us"`, `"ru"`) to filter by language.

### Structure Browsing

| Tool | Description |
|---|---|
| `list_categories(subdomain, locale?)` | Entry point: shows locales, categories, and section counts |
| `list_sections(subdomain, category_id?, locale?)` | Sections, optionally filtered by category |

### Content Retrieval

| Tool | Description |
|---|---|
| `get_article(subdomain, article_id)` | Single article with full markdown body |
| `get_articles(subdomain, article_ids)` | Batch fetch multiple articles concurrently |
| `get_section_articles(subdomain, section_id, locale?, include_body?, max_articles?)` | TOC by default; set `include_body=True` for full text |
| `search_articles(subdomain, query, locale?, limit?)` | Keyword search with snippets (no bodies) |

### Community

| Tool | Description |
|---|---|
| `list_community_topics(subdomain)` | Forum topics |
| `list_community_posts(subdomain, topic_id?, limit?)` | Posts with body previews and comment counts |
| `get_community_post(subdomain, post_id)` | Full post with comments |

## Usage Examples

**Discover a Help Center's structure:**
```
list_categories("support.zendesk.com")
```

**Browse sections in a category:**
```
list_sections("support.zendesk.com", category_id=360001006608)
```

**Fetch all articles in a section (TOC only):**
```
get_section_articles("support.zendesk.com", section_id=360000031847)
```

**Fetch articles with full content:**
```
get_section_articles("support.zendesk.com", section_id=360000031847, include_body=True, max_articles=5)
```

**Search for articles:**
```
search_articles("support.zendesk.com", query="API")
```

## Cache

Responses are cached for 7 days in `.cache/` (project-local) using hishel (SQLite-backed HTTP cache).

- Use `force_refresh=True` on any tool to bypass the cache
- Delete the `.cache/` directory to clear all cached data
- The `.cache/` directory is gitignored

Override the default TTL (in seconds) with the `ZENDESK_HC_CACHE_TTL` environment variable in your `.mcp.json`:

```json
{
  "mcpServers": {
    "zendesk-hc": {
      "command": "uv",
      "args": ["--directory", "/path/to/zendesk-hc-mcp", "run", "zendesk-hc-mcp"],
      "env": {
        "ZENDESK_HC_CACHE_TTL": "86400"
      }
    }
  }
}
```

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest -v

# Run the server (stdio mode)
uv run zendesk-hc-mcp
```

## Contributing

Contributions are welcome! To get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Install dev dependencies: `uv sync`
4. Make your changes following TDD (write tests first)
5. Run the test suite: `uv run pytest -v`
6. Ensure coverage stays above 90%: `uv run pytest --cov=zendesk_hc_mcp --cov-report=term-missing`
7. Submit a pull request

See [CLAUDE.md](CLAUDE.md) for architecture details and development conventions.

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by Zendesk, Inc. "Zendesk" is a registered trademark of Zendesk, Inc. This tool accesses the publicly available Zendesk Help Center API and is intended for lawful, read-only use.

## License

[MIT](LICENSE)
