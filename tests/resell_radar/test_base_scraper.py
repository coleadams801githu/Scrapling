"""Tests for BaseScraper helpers and ScrapedItem defaults."""
from __future__ import annotations

import pytest

from resell_radar.scrapers.base import BaseScraper, ScrapedItem, ScraperError


# --------------------------------------------------------------------------- concrete stub


class _StubScraper(BaseScraper):
    """Minimal concrete subclass used only in unit tests."""

    platform = "stub"
    max_retries = 2
    retry_delay = 0  # speed up tests

    def __init__(self, responses=None, exception=None):
        self._responses = list(responses or [ScrapedItem(price=99.0)])
        self._exception = exception
        self._call_count = 0

    def _scrape(self, url: str) -> ScrapedItem:
        self._call_count += 1
        if self._exception:
            raise self._exception
        return self._responses.pop(0)


# --------------------------------------------------------------------------- ScrapedItem


class TestScrapedItem:
    def test_defaults(self):
        item = ScrapedItem()
        assert item.price is None
        assert item.currency == "USD"
        assert item.availability == "active"
        assert item.raw == {}
        assert item.scraped_at is not None

    def test_custom_values(self):
        item = ScrapedItem(price=123.45, currency="EUR", title="Test", availability="sold")
        assert item.price == 123.45
        assert item.currency == "EUR"
        assert item.title == "Test"
        assert item.availability == "sold"


# --------------------------------------------------------------------------- BaseScraper.parse_price


class TestParsePrice:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("$1,299.00", 1299.00),
            ("€ 849", 849.0),
            ("1.250,00", 1.25),  # European style — not fully normalised, best-effort
            ("Free", None),
            ("", None),
            ("$0.99", 0.99),
            ("USD 2,500", 2500.0),
        ],
    )
    def test_parse_price(self, raw, expected):
        result = BaseScraper.parse_price(raw)
        assert result == pytest.approx(expected, abs=1e-2) if expected is not None else result is None


# --------------------------------------------------------------------------- BaseScraper.detect_currency


class TestDetectCurrency:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("$100", "USD"),
            ("€100", "EUR"),
            ("£100", "GBP"),
            ("¥100", "JPY"),
            ("100", "USD"),
        ],
    )
    def test_detect(self, raw, expected):
        assert BaseScraper.detect_currency(raw) == expected


# --------------------------------------------------------------------------- BaseScraper.fetch (retry)


class TestFetch:
    def test_success_first_attempt(self):
        scraper = _StubScraper(responses=[ScrapedItem(price=50.0)])
        item = scraper.fetch("https://example.com/item/1")
        assert item.price == 50.0
        assert scraper._call_count == 1

    def test_retry_on_failure_then_success(self):
        scraper = _StubScraper()
        scraper._responses = [ScrapedItem(price=75.0)]

        # Make first call raise, second succeed
        call_counts = {"n": 0}

        def _scrape_patched(url):
            call_counts["n"] += 1
            if call_counts["n"] == 1:
                raise ValueError("transient error")
            return ScrapedItem(price=75.0)

        scraper._scrape = _scrape_patched
        item = scraper.fetch("https://example.com/item/2")
        assert item.price == 75.0
        assert call_counts["n"] == 2

    def test_raises_scraper_error_after_all_retries(self):
        scraper = _StubScraper(exception=ValueError("always fails"))
        with pytest.raises(ScraperError):
            scraper.fetch("https://example.com/item/3")
        assert scraper._call_count == scraper.max_retries

    def test_fetch_stamps_scraped_at(self):
        from datetime import datetime, timezone

        before = datetime.utcnow()
        scraper = _StubScraper(responses=[ScrapedItem()])
        item = scraper.fetch("https://example.com/item/4")
        after = datetime.utcnow()
        assert before <= item.scraped_at <= after
