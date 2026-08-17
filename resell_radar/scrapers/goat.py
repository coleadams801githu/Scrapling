"""GOAT scraper — extracts price from __NEXT_DATA__ JSON blob."""
from __future__ import annotations

import json
import logging
import re

from resell_radar.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

# GOAT product URL example:
#   https://www.goat.com/sneakers/air-max-1-86-big-bubble-black-dq3989-001
_SLUG_RE = re.compile(r"goat\.com/(?:sneakers|apparel|accessories)/([a-z0-9][a-z0-9-]+[a-z0-9])")


class GoatScraper(BaseScraper):
    """Scraper for GOAT sneaker / streetwear listings.

    GOAT inlines product data in a ``<script id="__NEXT_DATA__">`` block on
    the product page.  We parse that block for price and availability before
    falling back to CSS selectors.
    """

    platform = "goat"

    def _scrape(self, url: str) -> ScrapedItem:
        from scrapling.fetchers import Fetcher

        page = Fetcher.get(url, stealthy_headers=True)

        script_el = page.css_first("script#__NEXT_DATA__")
        if script_el:
            try:
                data = json.loads(script_el.text)
                return self._parse_next_data(data)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("[goat] __NEXT_DATA__ parse failed: %s", exc)

        return self._scrape_html(page)

    # ------------------------------------------------------------------ __NEXT_DATA__

    def _parse_next_data(self, data: dict) -> ScrapedItem:
        props = data.get("props", {}).get("pageProps", {})

        # Different GOAT page versions nest product data differently
        product = (
            props.get("product")
            or props.get("listing")
            or props.get("productTemplate")
            or {}
        )
        title = product.get("name") or product.get("title")

        # Price is stored in cents (USD)
        price_cents = (
            product.get("lowestPriceCents", {}).get("amount")
            or product.get("retailPriceCents")
            or product.get("lowestAskingPrice", {}).get("amount")
        )
        price = price_cents / 100 if price_cents else None

        status = product.get("status", "")
        sold = status.lower() in ("sold_out", "sold", "unavailable")
        availability = "sold" if sold else "active"

        return ScrapedItem(
            price=price,
            currency="USD",
            title=title,
            availability=availability,
            raw=product,
        )

    # ------------------------------------------------------------------ HTML fallback

    def _scrape_html(self, page) -> ScrapedItem:
        title_el = (
            page.css_first("h1[data-qa='product-name']")
            or page.css_first("h1.product-name")
            or page.css_first("h1")
        )
        title = title_el.text.strip() if title_el else None

        price_el = (
            page.css_first("[data-qa='lowest-ask-price']")
            or page.css_first("span.lowest-ask")
            or page.css_first("[data-qa='buy-bar-price']")
        )
        raw_price = price_el.text.strip() if price_el else ""
        price = self.parse_price(raw_price)

        sold_el = (
            page.css_first("[data-qa='sold-out-badge']")
            or page.css_first(".sold-out")
        )
        availability = "sold" if sold_el else "active"

        return ScrapedItem(
            price=price,
            currency="USD",
            title=title,
            availability=availability,
        )
