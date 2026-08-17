"""Depop scraper — uses the public product API when possible."""
from __future__ import annotations

import json
import logging
import re

from resell_radar.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

# Depop product URL examples:
#   https://www.depop.com/products/username-product-slug-abc123/
#   https://depop.com/products/some-item-id/
_PRODUCT_ID_RE = re.compile(r"/products/[^/]+-([a-f0-9]{8,})/")
_SLUG_RE = re.compile(r"/products/([^/?#]+)")
_API_BASE = "https://api.depop.com/api/v1/products/"


class DepopScraper(BaseScraper):
    """Scraper for Depop secondhand fashion listings.

    Attempts the Depop public REST API first.  Falls back to HTML scraping
    via :class:`~scrapling.fetchers.StealthyFetcher` when the API is
    unavailable.
    """

    platform = "depop"

    def _scrape(self, url: str) -> ScrapedItem:
        slug_match = _SLUG_RE.search(url)
        if slug_match:
            try:
                return self._scrape_api(slug_match.group(1))
            except Exception as exc:
                logger.warning("[depop] API failed (%s), falling back to HTML", exc)
        return self._scrape_html(url)

    # ------------------------------------------------------------------ API

    def _scrape_api(self, slug: str) -> ScrapedItem:
        import urllib.request

        api_url = f"{_API_BASE}{slug}/"
        req = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
                "depop-version": "2",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        title = data.get("description") or data.get("slug")
        price_info = data.get("price", {})
        # The main price is usually in the top-level price field as a string
        raw_price = data.get("priceAmount") or (
            price_info.get("amount") if isinstance(price_info, dict) else price_info
        )
        currency = (
            price_info.get("currencyName", "USD")
            if isinstance(price_info, dict)
            else "USD"
        )
        sold = data.get("status", "").lower() in ("sold", "inactive")
        availability = "sold" if sold else "active"

        return ScrapedItem(
            price=float(raw_price) if raw_price else None,
            currency=currency,
            title=title,
            availability=availability,
            raw=data,
        )

    # ------------------------------------------------------------------ HTML

    def _scrape_html(self, url: str) -> ScrapedItem:
        from scrapling.fetchers import StealthyFetcher

        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            wait=1500,
        )

        # Try JSON-LD first
        script_el = page.css_first("script[type='application/ld+json']")
        if script_el:
            try:
                ld = json.loads(script_el.text)
                if isinstance(ld, list):
                    ld = ld[0]
                offers = ld.get("offers", {})
                raw_price = offers.get("price")
                currency = offers.get("priceCurrency", "USD")
                title = ld.get("name")
                in_stock = offers.get("availability", "").endswith("InStock")
                return ScrapedItem(
                    price=float(raw_price) if raw_price else None,
                    currency=currency,
                    title=title,
                    availability="active" if in_stock else "sold",
                )
            except (json.JSONDecodeError, KeyError):
                pass

        title_el = (
            page.css_first("h1[data-testid='product-title']")
            or page.css_first("p[class*='Description']")
            or page.css_first("h1")
        )
        title = title_el.text.strip() if title_el else None

        price_el = (
            page.css_first("p[data-testid='product-price']")
            or page.css_first("p[class*='Price']")
            or page.css_first("[aria-label*='price']")
        )
        raw_price = price_el.text.strip() if price_el else ""
        price = self.parse_price(raw_price)
        currency = self.detect_currency(raw_price)

        sold_el = (
            page.css_first("[data-testid='sold-badge']")
            or page.css_first("p[class*='Sold']")
            or page.css_first("[aria-label='Sold']")
        )
        availability = "sold" if sold_el else "active"

        return ScrapedItem(
            price=price,
            currency=currency,
            title=title,
            availability=availability,
        )
