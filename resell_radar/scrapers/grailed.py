"""Grailed scraper — prefers the GraphQL API, falls back to HTML."""
from __future__ import annotations

import json
import logging
import re

from resell_radar.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

_LISTING_ID_RE = re.compile(r"/listings/(\d+)")
_GRAPHQL_URL = "https://www.grailed.com/api/listings"


class GrailedScraper(BaseScraper):
    platform = "grailed"

    def _scrape(self, url: str) -> ScrapedItem:
        m = _LISTING_ID_RE.search(url)
        if m:
            try:
                return self._scrape_api(m.group(1))
            except Exception as exc:
                logger.warning("[grailed] API failed (%s), falling back to HTML", exc)
        return self._scrape_html(url)

    def _scrape_api(self, listing_id: str) -> ScrapedItem:
        import urllib.request

        api_url = f"{_GRAPHQL_URL}/{listing_id}"
        req = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        listing = data.get("listing", data)
        price_cents = listing.get("price_cents") or listing.get("price")
        price = price_cents / 100 if price_cents else price_cents
        title = listing.get("title")
        sold = listing.get("sold") or listing.get("sold_at") is not None
        availability = "sold" if sold else "active"

        return ScrapedItem(
            price=float(price) if price else None,
            currency="USD",
            title=title,
            availability=availability,
            raw=listing,
        )

    def _scrape_html(self, url: str) -> ScrapedItem:
        from scrapling.fetchers import StealthyFetcher

        page = StealthyFetcher.fetch(url, headless=True, network_idle=True, wait=1500)

        title_el = page.css_first("h1.listing-title") or page.css_first("h1")
        title = title_el.text.strip() if title_el else None

        price_el = page.css_first(".price") or page.css_first("[class*='price']")
        raw_price = price_el.text.strip() if price_el else ""
        price = self.parse_price(raw_price)

        sold_el = page.css_first(".sold-badge") or page.css_first("[class*='sold']")
        availability = "sold" if sold_el else "active"

        return ScrapedItem(price=price, currency="USD", title=title, availability=availability)
