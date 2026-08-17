"""Tests for new roadmap features:
- get_pagination_urls()
- get_schemas()
- analyze()
- Selectors.generate_regex()
- scrapling.integrations.scrapy
"""

import re
import pytest

from scrapling.parser import Selector, Selectors


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def paginated_html():
    return """
    <html>
    <head>
        <link rel="next" href="/page/2">
        <link rel="prev" href="/page/0">
    </head>
    <body>
        <nav class="pagination">
            <a href="/page/1">1</a>
            <a href="/page/2">2</a>
            <a href="/page/3">next</a>
        </nav>
    </body>
    </html>
    """


@pytest.fixture
def schema_html():
    return """
    <html>
    <head>
        <meta property="og:title" content="My Page">
        <meta property="og:url" content="https://example.com">
        <meta name="twitter:card" content="summary">
        <meta name="twitter:title" content="My Page Tweet">
        <script type="application/ld+json">
            {"@context": "https://schema.org", "@type": "Product", "name": "Widget"}
        </script>
    </head>
    <body>
        <div itemscope itemtype="https://schema.org/Person">
            <span itemprop="name">Alice</span>
            <a itemprop="url" href="https://alice.example.com">Profile</a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def analyze_html():
    return """
    <html lang="en">
    <head>
        <title>Test Page</title>
        <meta name="description" content="A test page">
        <meta name="keywords" content="foo, bar, baz">
        <meta name="author" content="Alice">
        <meta charset="UTF-8">
        <link rel="canonical" href="https://example.com/test">
        <link rel="alternate" type="application/rss+xml" href="/rss.xml">
        <meta property="og:title" content="OG Title">
        <meta name="twitter:card" content="summary">
        <script type="application/ld+json">{"@type": "Article"}</script>
    </head>
    <body>
        <p>Hello <a href="/internal">internal link</a></p>
        <p><a href="https://external.example.com/page">external link</a></p>
        <img src="/img/photo.jpg" alt="photo">
        <time datetime="2024-01-15">Jan 15</time>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# get_pagination_urls
# ---------------------------------------------------------------------------

class TestGetPaginationUrls:
    def test_link_rel_next(self, paginated_html):
        page = Selector(paginated_html, url="https://example.com/page/1")
        urls = page.get_pagination_urls()
        assert any("/page/2" in u for u in urls)

    def test_link_rel_prev(self, paginated_html):
        page = Selector(paginated_html, url="https://example.com/page/1")
        urls = page.get_pagination_urls()
        assert any("/page/0" in u for u in urls)

    def test_anchor_next_text(self, paginated_html):
        page = Selector(paginated_html, url="https://example.com/page/1")
        urls = page.get_pagination_urls()
        assert any("/page/3" in u for u in urls)

    def test_pagination_nav_class(self, paginated_html):
        page = Selector(paginated_html, url="https://example.com/page/1")
        urls = page.get_pagination_urls()
        assert len(urls) > 0

    def test_no_duplicates(self, paginated_html):
        page = Selector(paginated_html, url="https://example.com/page/1")
        urls = page.get_pagination_urls()
        assert len(urls) == len(set(urls))

    def test_query_string_pagination(self):
        html = "<html><body><p>content</p></body></html>"
        page = Selector(html, url="https://example.com/products?page=3")
        urls = page.get_pagination_urls()
        assert any("page=4" in u for u in urls)

    def test_empty_page_returns_list(self):
        page = Selector("<html><body></body></html>")
        assert isinstance(page.get_pagination_urls(), list)

    def test_text_node_returns_empty(self):
        page = Selector("<html><body><p>hi</p></body></html>")
        text_node = page.css("p::text")[0]
        assert text_node.get_pagination_urls() == []

    def test_returns_absolute_urls_when_base_set(self, paginated_html):
        page = Selector(paginated_html, url="https://example.com/page/1")
        for url in page.get_pagination_urls():
            assert url.startswith("https://"), f"Expected absolute URL, got: {url}"

    def test_aria_label_anchor(self):
        html = """<html><body>
            <a href="/page/5" aria-label="next">&#x203A;</a>
        </body></html>"""
        page = Selector(html, url="https://example.com/page/4")
        urls = page.get_pagination_urls()
        assert any("/page/5" in u for u in urls)


# ---------------------------------------------------------------------------
# get_schemas
# ---------------------------------------------------------------------------

class TestGetSchemas:
    def test_json_ld_present(self, schema_html):
        page = Selector(schema_html)
        schemas = page.get_schemas()
        assert "json_ld" in schemas
        assert schemas["json_ld"][0]["@type"] == "Product"

    def test_open_graph(self, schema_html):
        page = Selector(schema_html)
        schemas = page.get_schemas()
        assert "open_graph" in schemas
        assert schemas["open_graph"]["title"] == "My Page"

    def test_twitter_card(self, schema_html):
        page = Selector(schema_html)
        schemas = page.get_schemas()
        assert "twitter_card" in schemas
        assert schemas["twitter_card"]["card"] == "summary"

    def test_microdata(self, schema_html):
        page = Selector(schema_html)
        schemas = page.get_schemas()
        assert "microdata" in schemas
        item = schemas["microdata"][0]
        assert "Alice" in str(item)

    def test_empty_page_returns_empty_dict(self):
        page = Selector("<html><body></body></html>")
        assert page.get_schemas() == {}

    def test_invalid_json_ld_ignored(self):
        html = """<html><head>
            <script type="application/ld+json">NOT JSON</script>
        </head><body></body></html>"""
        page = Selector(html)
        # Should not raise; invalid block is silently skipped
        schemas = page.get_schemas()
        assert "json_ld" not in schemas

    def test_text_node_returns_empty(self):
        page = Selector("<html><body><p>hi</p></body></html>")
        text_node = page.css("p::text")[0]
        assert text_node.get_schemas() == {}

    def test_multiple_json_ld_blocks(self):
        html = """<html><head>
            <script type="application/ld+json">{"@type": "A"}</script>
            <script type="application/ld+json">{"@type": "B"}</script>
        </head><body></body></html>"""
        page = Selector(html)
        schemas = page.get_schemas()
        assert len(schemas["json_ld"]) == 2

    def test_microdata_nested_item(self):
        html = """<html><body>
            <div itemscope itemtype="https://schema.org/Offer">
                <span itemprop="price">9.99</span>
                <div itemscope itemtype="https://schema.org/Brand" itemprop="brand">
                    <span itemprop="name">Acme</span>
                </div>
            </div>
        </body></html>"""
        page = Selector(html)
        schemas = page.get_schemas()
        assert "microdata" in schemas
        props = schemas["microdata"][0].get("properties", {})
        assert "price" in props
        assert "brand" in props


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_title(self, analyze_html):
        page = Selector(analyze_html, url="https://example.com/test")
        info = page.analyze()
        assert info["title"] == "Test Page"

    def test_description(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert info["description"] == "A test page"

    def test_keywords_are_list(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert info["keywords"] == ["foo", "bar", "baz"]

    def test_author(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert info["author"] == "Alice"

    def test_language(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert info["language"] == "en"

    def test_canonical(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert info["canonical"] == "https://example.com/test"

    def test_charset(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert info.get("charset", "UTF-8").upper() == "UTF-8"

    def test_open_graph(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert "open_graph" in info
        assert info["open_graph"]["title"] == "OG Title"

    def test_twitter_card(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert "twitter_card" in info

    def test_schemas_included(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert "schemas" in info

    def test_feeds(self, analyze_html):
        info = Selector(analyze_html, url="https://example.com").analyze()
        assert "feeds" in info
        assert any("rss" in f for f in info["feeds"])

    def test_links_internal_external(self, analyze_html):
        info = Selector(analyze_html, url="https://example.com/test").analyze()
        assert "links" in info
        assert any("/internal" in u for u in info["links"]["internal"])
        ext_urls = info["links"]["external"]
        assert any(u == "https://external.example.com/page" for u in ext_urls)

    def test_images(self, analyze_html):
        info = Selector(analyze_html, url="https://example.com/test").analyze()
        assert "images" in info
        assert any("photo.jpg" in i for i in info["images"])

    def test_published_at_from_time_tag(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert info.get("published_at") == "2024-01-15"

    def test_word_count(self, analyze_html):
        info = Selector(analyze_html).analyze()
        assert isinstance(info.get("word_count"), int)
        assert info["word_count"] > 0

    def test_empty_page_returns_dict(self):
        page = Selector("<html><body></body></html>")
        assert isinstance(page.analyze(), dict)

    def test_text_node_returns_empty(self):
        page = Selector("<html><body><p>hi</p></body></html>")
        text_node = page.css("p::text")[0]
        assert text_node.analyze() == {}

    def test_published_at_from_meta(self):
        html = """<html><head>
            <meta property="article:published_time" content="2024-06-01T00:00:00Z">
        </head><body></body></html>"""
        info = Selector(html).analyze()
        assert info.get("published_at") == "2024-06-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Selectors.generate_regex
# ---------------------------------------------------------------------------

class TestGenerateRegex:
    def _page_with_links(self, hrefs):
        items = "".join(f'<li><a href="{h}">x</a></li>' for h in hrefs)
        return Selector(f"<html><body><ul>{items}</ul></body></html>")

    def test_digit_pattern(self):
        page = self._page_with_links(["/product/1", "/product/42", "/product/999"])
        pattern = page.css("a").generate_regex("href")
        assert re.fullmatch(pattern, "/product/123")
        assert r"\d+" in pattern

    def test_word_pattern(self):
        page = self._page_with_links(["/cat/shoes", "/cat/hats", "/cat/bags"])
        pattern = page.css("a").generate_regex("href")
        assert re.fullmatch(pattern, "/cat/boots")
        assert r"\w+" in pattern

    def test_text_source(self):
        html = "<ul><li>item-1</li><li>item-2</li><li>item-99</li></ul>"
        page = Selector(html)
        pattern = page.css("li").generate_regex()
        assert re.fullmatch(pattern, "item-7")

    def test_empty_selectors_returns_empty_string(self):
        page = Selector("<html><body></body></html>")
        result = page.css("a").generate_regex("href")
        assert result == ""

    def test_all_blank_values_returns_empty_string(self):
        html = '<ul><li><a href="">x</a></li><li><a href="">y</a></li></ul>'
        page = Selector(html)
        result = page.css("a").generate_regex("href")
        assert result == ""

    def test_single_unique_value_raises(self):
        page = self._page_with_links(["/same", "/same", "/same"])
        with pytest.raises(ValueError):
            page.css("a").generate_regex("href")

    def test_pattern_compiles_to_valid_regex(self):
        page = self._page_with_links(["/p/10", "/p/20", "/p/30"])
        pattern = page.css("a").generate_regex("href")
        compiled = re.compile(pattern)
        assert compiled.fullmatch("/p/50")

    def test_flags_added_to_pattern(self):
        page = self._page_with_links(["/p/10", "/p/20"])
        pattern = page.css("a").generate_regex("href", flags=re.IGNORECASE)
        assert "(?i)" in pattern


# ---------------------------------------------------------------------------
# Scrapy integration (no scrapy installed → ImportError path)
# ---------------------------------------------------------------------------

class TestScraplingIntegration:
    def test_module_importable(self):
        from scrapling.integrations import scrapy as scrapling_scrapy
        assert hasattr(scrapling_scrapy, "ScraplingMiddleware")
        assert hasattr(scrapling_scrapy, "scrapling_callback")

    def test_wrap_response_requires_scrapy(self):
        from scrapling.integrations.scrapy import _wrap_response, _SCRAPY_AVAILABLE
        if not _SCRAPY_AVAILABLE:
            with pytest.raises(ImportError):
                _wrap_response(object())

    def test_scrapling_callback_wraps_function(self):
        from scrapling.integrations.scrapy import scrapling_callback
        # When scrapy is not installed the decorator still wraps the function
        # but calling it requires a Scrapy response; we just verify wrapping.
        @scrapling_callback
        def parse(self, response):
            return "ok"

        assert callable(parse)
        assert parse.__name__ == "parse"
