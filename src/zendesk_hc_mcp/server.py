"""Entry point for the Zendesk Help Center MCP server."""

from __future__ import annotations

from zendesk_hc_mcp.tools import mcp  # noqa: F401 — registers all tools on import


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
