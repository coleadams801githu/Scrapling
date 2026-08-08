"""eBay scraper — uses the eBay Browse API (OAuth2 app token) with HTML fallback."""
from __future__ import annotations

import os
import logging
import re

from resell_radar.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

_EBAY_API_URL = "https://api.ebay.com/buy/browse/v1/item/"
_ITEM_ID_RE = re.compile(r"/itm/(?:[^/]+/)?(\d+)")


def _extract_item_id(url: str) -> str | None:
    m = _ITEM_ID_RE.search(url)
    return m.group(1) if m else None


class EbayScraper(BaseScraper):
    """Scraper for eBay item pages.

    Prefers the eBay Browse API when ``EBAY_APP_TOKEN`` is set in the
    environment.  Falls back to HTML scraping via StealthyFetcher otherwise.
    """

    platform = "ebay"

    def _scrape(self, url: str) -> ScrapedItem:
        token = os.environ.get("EBAY_APP_TOKEN")
        item_id = _extract_item_id(url)
        if token and item_id:
            return self._scrape_api(item_id, token)
        return self._scrape_html(url)

    # ------------------------------------------------------------------ API

    def _scrape_api(self, item_id: str, token: str) -> ScrapedItem:
        import urllib.request
        import json

        api_url = f"{_EBAY_API_URL}{item_id}"
        req = urllib.request.Request(
            api_url,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        price_info = data.get("price", {})
        raw_price = price_info.get("value")
        currency = price_info.get("currency", "USD")
        title = data.get("title")
        buying_options = data.get("buyingOptions", [])
        sold = data.get("itemEndDate") is not None
        availability = "sold" if sold else ("active" if buying_options else "unavailable")

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
            disable_resources=True,
            network_idle=True,
        )

        title_el = page.css_first("h1.x-item-title__mainTitle span.ux-textspans")
        title = title_el.text if title_el else None

        price_el = page.css_first(".x-price-primary span.ux-textspans")
        raw_price_str = price_el.text if price_el else ""
        currency = self.detect_currency(raw_price_str)
        price = self.parse_price(raw_price_str)

        sold_el = page.css_first(".vim-soldout-status")
        availability = "sold" if sold_el else "active"

        return ScrapedItem(
            price=price,
            currency=currency,
            title=title,
            availability=availability,
        )
