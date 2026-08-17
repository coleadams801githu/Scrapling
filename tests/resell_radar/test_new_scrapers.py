"""Tests for the new StockX, GOAT, and Depop scrapers (no real HTTP)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from resell_radar.scrapers.stockx import StockXScraper
from resell_radar.scrapers.goat import GoatScraper
from resell_radar.scrapers.depop import DepopScraper


# --------------------------------------------------------------------------- StockX


class TestStockXScraper:
    def test_platform(self):
        assert StockXScraper().platform == "stockx"

    def test_scrape_api_success(self):
        """_scrape_api parses product market data correctly."""
        scraper = StockXScraper()
        data = {
            "Product": {
                "title": "Nike Air Max 1",
                "market": {"lowestAsk": 189.0, "lastSale": 175.0},
            }
        }

        class _FakeResp:
            def read(self):
                return json.dumps(data).encode()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        with patch("urllib.request.urlopen", return_value=_FakeResp()):
            item = scraper._scrape_api("nike-air-max-1")

        assert item.title == "Nike Air Max 1"
        assert item.price == 189.0
        assert item.availability == "active"

    def test_scrape_api_no_ask_uses_last_sale(self):
        scraper = StockXScraper()
        data = {
            "Product": {
                "title": "Sold Out Item",
                "market": {"lowestAsk": None, "lastSale": 210.0},
            }
        }

        class _FakeResp:
            def read(self):
                return json.dumps(data).encode()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        with patch("urllib.request.urlopen", return_value=_FakeResp()):
            item = scraper._scrape_api("sold-out-item")

        assert item.price == 210.0

    def test_scrape_html_falls_back_to_api_on_slug_present(self):
        """When a slug is present and API succeeds, _scrape_html is never called."""
        scraper = StockXScraper()
        api_item = MagicMock()
        api_item.price = 200.0

        with patch.object(scraper, "_scrape_api", return_value=api_item) as mock_api, \
             patch.object(scraper, "_scrape_html") as mock_html:
            result = scraper._scrape("https://stockx.com/nike-air-max-1")
            mock_api.assert_called_once()
            mock_html.assert_not_called()

    def test_falls_back_to_html_on_api_error(self):
        scraper = StockXScraper()
        html_item = MagicMock()
        html_item.price = 195.0

        with patch.object(scraper, "_scrape_api", side_effect=Exception("api down")), \
             patch.object(scraper, "_scrape_html", return_value=html_item) as mock_html:
            result = scraper._scrape("https://stockx.com/nike-air-max-1")
            mock_html.assert_called_once()
            assert result.price == 195.0


# --------------------------------------------------------------------------- GOAT


class TestGoatScraper:
    def test_platform(self):
        assert GoatScraper().platform == "goat"

    def test_parse_next_data_standard(self):
        scraper = GoatScraper()
        data = {
            "props": {
                "pageProps": {
                    "product": {
                        "name": "Air Max 1",
                        "lowestPriceCents": {"amount": 18000},
                        "status": "active",
                    }
                }
            }
        }
        item = scraper._parse_next_data(data)
        assert item.title == "Air Max 1"
        assert item.price == pytest.approx(180.0)
        assert item.availability == "active"

    def test_parse_next_data_sold_out(self):
        scraper = GoatScraper()
        data = {
            "props": {
                "pageProps": {
                    "product": {
                        "name": "Rare Item",
                        "lowestPriceCents": {"amount": 30000},
                        "status": "sold_out",
                    }
                }
            }
        }
        item = scraper._parse_next_data(data)
        assert item.availability == "sold"

    def test_parse_next_data_missing_price(self):
        scraper = GoatScraper()
        data = {"props": {"pageProps": {"product": {"name": "Empty"}}}}
        item = scraper._parse_next_data(data)
        assert item.price is None

    def test_scrape_uses_next_data_when_present(self):
        scraper = GoatScraper()
        next_data = {
            "props": {"pageProps": {"product": {"name": "Test", "lowestPriceCents": {"amount": 25000}, "status": "active"}}}
        }

        mock_page = MagicMock()
        mock_script = MagicMock()
        mock_script.text = json.dumps(next_data)
        mock_page.css_first.return_value = mock_script

        with patch("scrapling.fetchers.Fetcher.get", return_value=mock_page):
            item = scraper._scrape("https://www.goat.com/sneakers/test-item")

        assert item.price == pytest.approx(250.0)


# --------------------------------------------------------------------------- Depop


class TestDepopScraper:
    def test_platform(self):
        assert DepopScraper().platform == "depop"

    def test_scrape_api_success(self):
        scraper = DepopScraper()
        data = {
            "description": "Vintage Levi Jeans",
            "priceAmount": "45.00",
            "price": {"currencyName": "GBP"},
            "status": "active",
        }

        class _FakeResp:
            def read(self):
                return json.dumps(data).encode()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        with patch("urllib.request.urlopen", return_value=_FakeResp()):
            item = scraper._scrape_api("username-vintage-levi-jeans-abc123")

        assert item.title == "Vintage Levi Jeans"
        assert item.price == pytest.approx(45.0)
        assert item.currency == "GBP"
        assert item.availability == "active"

    def test_scrape_api_sold(self):
        scraper = DepopScraper()
        data = {"description": "Sold item", "priceAmount": "30.00",
                "price": {"currencyName": "USD"}, "status": "sold"}

        class _FakeResp:
            def read(self):
                return json.dumps(data).encode()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        with patch("urllib.request.urlopen", return_value=_FakeResp()):
            item = scraper._scrape_api("username-sold-item-def456")

        assert item.availability == "sold"

    def test_falls_back_to_html_on_api_error(self):
        scraper = DepopScraper()
        html_item = MagicMock()
        html_item.price = 35.0

        with patch.object(scraper, "_scrape_api", side_effect=Exception("api down")), \
             patch.object(scraper, "_scrape_html", return_value=html_item) as mock_html:
            result = scraper._scrape("https://www.depop.com/products/username-item-abc123/")
            mock_html.assert_called_once()
            assert result.price == 35.0
