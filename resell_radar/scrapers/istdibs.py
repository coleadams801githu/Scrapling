"""1stDibs scraper — tries the REST API first, falls back to HTML."""
from __future__ import annotations

import json
import logging
import re

from resell_radar.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

_SKU_RE = re.compile(r"/furniture/[^/]+/[^/]+/([^/?#]+)")
_API_BASE = "https://www.1stdibs.com/api/furniture/item/"


class IstdibsScraper(BaseScraper):
    platform = "istdibs"

    def _scrape(self, url: str) -> ScrapedItem:
        m = _SKU_RE.search(url)
        if m:
            try:
                return self._scrape_api(m.group(1))
            except Exception as exc:
                logger.warning("[1stdibs] API failed (%s), falling back to HTML", exc)
        return self._scrape_html(url)

    def _scrape_api(self, sku: str) -> ScrapedItem:
        import urllib.request

        api_url = f"{_API_BASE}{sku}"
        req = urllib.request.Request(
            api_url,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        item = data.get("item", data)
        price = item.get("price", {}).get("amount")
        currency = item.get("price", {}).get("currency", "USD")
        title = item.get("title")
        sold = item.get("isSold") or item.get("sold", False)
        availability = "sold" if sold else "active"

        return ScrapedItem(
            price=float(price) if price else None,
            currency=currency,
            title=title,
            availability=availability,
            raw=item,
        )

    def _scrape_html(self, url: str) -> ScrapedItem:
        from scrapling.fetchers import StealthyFetcher

        page = StealthyFetcher.fetch(url, headless=True, network_idle=True, wait=2000)

        title_el = page.css_first("h1[data-tn='pdp-title']") or page.css_first("h1")
        title = title_el.text.strip() if title_el else None

        price_el = (
            page.css_first("[data-tn='price-amount']")
            or page.css_first(".price-amount")
            or page.css_first("[class*='price']")
        )
        raw_price = price_el.text.strip() if price_el else ""
        price = self.parse_price(raw_price)
        currency = self.detect_currency(raw_price)

        sold_el = page.css_first(".sold-badge") or page.css_first("[class*='sold']")
        availability = "sold" if sold_el else "active"

        return ScrapedItem(price=price, currency=currency, title=title, availability=availability)
