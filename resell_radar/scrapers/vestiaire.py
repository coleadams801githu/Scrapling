"""Vestiaire Collective scraper — uses StealthyFetcher with session persistence."""
from __future__ import annotations

import logging

from resell_radar.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class VestiaireScraper(BaseScraper):
    platform = "vestiaire"

    def _scrape(self, url: str) -> ScrapedItem:
        from scrapling.fetchers import StealthyFetcher

        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            wait=2000,
        )

        title_el = (
            page.css_first("h1[data-cy='product-title']")
            or page.css_first("h1.product-title")
            or page.css_first("h1")
        )
        title = title_el.text.strip() if title_el else None

        price_el = (
            page.css_first("[data-cy='product-price']")
            or page.css_first(".product-price__amount")
            or page.css_first("span.price")
        )
        raw_price = price_el.text.strip() if price_el else ""
        price = self.parse_price(raw_price)
        currency = self.detect_currency(raw_price)

        sold_el = (
            page.css_first("[data-cy='sold-badge']")
            or page.css_first(".sold-badge")
            or page.css_first(".product-sold")
        )
        availability = "sold" if sold_el else "active"

        return ScrapedItem(price=price, currency=currency, title=title, availability=availability)
