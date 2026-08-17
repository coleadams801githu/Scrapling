"""Poshmark scraper — extracts price from __NEXT_DATA__ JSON blob."""
from __future__ import annotations

import json
import logging

from resell_radar.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class PoshmarkScraper(BaseScraper):
    platform = "poshmark"

    def _scrape(self, url: str) -> ScrapedItem:
        from scrapling.fetchers import Fetcher

        page = Fetcher.get(url, stealthy_headers=True)

        script_el = page.css_first("script#__NEXT_DATA__")
        if script_el:
            try:
                data = json.loads(script_el.text)
                return self._parse_next_data(data)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("[poshmark] __NEXT_DATA__ parse failed: %s", exc)

        return self._scrape_html(page)

    def _parse_next_data(self, data: dict) -> ScrapedItem:
        props = data.get("props", {}).get("pageProps", {})
        listing = props.get("listing", props.get("post", {}))
        price_info = listing.get("price_amount", {})
        raw_price = price_info.get("val") or listing.get("price")
        currency = price_info.get("currency_code", "USD")
        title = listing.get("title")
        status = listing.get("status", "available")
        sold = status.lower() in ("sold", "not_for_sale")
        availability = "sold" if sold else "active"

        return ScrapedItem(
            price=float(raw_price) if raw_price else None,
            currency=currency,
            title=title,
            availability=availability,
            raw=listing,
        )

    def _scrape_html(self, page) -> ScrapedItem:
        title_el = page.css_first("h1.listing__title") or page.css_first("h1")
        title = title_el.text.strip() if title_el else None

        price_el = (
            page.css_first(".listing__ipad-centered p.fw--bold")
            or page.css_first("[data-test='listing-price']")
        )
        raw_price = price_el.text.strip() if price_el else ""
        price = self.parse_price(raw_price)

        sold_el = page.css_first(".sold-tag") or page.css_first("[class*='sold']")
        availability = "sold" if sold_el else "active"

        return ScrapedItem(price=price, currency="USD", title=title, availability=availability)
