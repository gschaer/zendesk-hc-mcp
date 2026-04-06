"""Tests for helper functions."""

from __future__ import annotations

from zendesk_hc_mcp.helpers import html_to_md, locale_path, pluralize, strip_em_tags, truncate


class TestHtmlToMd:
    def test_simple_paragraph(self):
        assert html_to_md("<p>Hello world</p>") == "Hello world"

    def test_heading(self):
        result = html_to_md("<h2>Title</h2>")
        assert "## Title" in result

    def test_unordered_list(self):
        html = "<ul><li>One</li><li>Two</li></ul>"
        result = html_to_md(html)
        assert "* One" in result or "- One" in result
        assert "* Two" in result or "- Two" in result

    def test_link_preserved(self):
        html = '<p>See <a href="https://example.com">docs</a></p>'
        result = html_to_md(html)
        assert "[docs]" in result
        assert "https://example.com" in result

    def test_nested_html(self):
        html = "<div><p>Text with <strong>bold</strong> and <em>italic</em></p></div>"
        result = html_to_md(html)
        assert "bold" in result
        assert "italic" in result

    def test_empty_string(self):
        assert html_to_md("") == ""

    def test_none_returns_empty(self):
        assert html_to_md(None) == ""

    def test_plain_text_passthrough(self):
        assert html_to_md("Just plain text") == "Just plain text"

    def test_code_block(self):
        html = "<pre><code>print('hello')</code></pre>"
        result = html_to_md(html)
        assert "print('hello')" in result


class TestLocalePath:
    def test_no_locale(self):
        assert locale_path("help_center/categories", None) == "help_center/categories"

    def test_with_locale(self):
        assert locale_path("help_center/categories", "en-us") == "help_center/en-us/categories"

    def test_with_locale_nested(self):
        assert locale_path("help_center/categories/111/sections", "ru") == "help_center/ru/categories/111/sections"


class TestStripEmTags:
    def test_strips_em(self):
        assert strip_em_tags("the <em>quick</em> fox") == "the quick fox"

    def test_no_em(self):
        assert strip_em_tags("plain text") == "plain text"


class TestTruncate:
    def test_short_text(self):
        assert truncate("short", 200) == "short"

    def test_long_text_breaks_at_word(self):
        text = "a " * 150
        result = truncate(text.strip(), 200)
        assert result.endswith("...")
        assert len(result) <= 203

    def test_no_space_in_cut(self):
        text = "x" * 300
        result = truncate(text, 200)
        assert result == "x" * 200 + "..."


class TestPluralize:
    def test_singular(self):
        assert pluralize(1, "article") == "1 article"

    def test_plural(self):
        assert pluralize(5, "article") == "5 articles"

    def test_zero(self):
        assert pluralize(0, "section") == "0 sections"

    def test_category_ies(self):
        assert pluralize(3, "category") == "3 categories"

    def test_category_singular(self):
        assert pluralize(1, "category") == "1 category"
