"""StockX scraper — tries the public API first, falls back to HTML."""
from __future__ import annotations

import json
import logging
import re

from resell_radar.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

# StockX product URLs contain a UUID-like slug or a hyphenated name followed by the
# product path.  Examples:
#   https://stockx.com/nike-air-max-1-86-big-bubble-black
#   https://stockx.com/adidas-yeezy-boost-350-v2-zebra
_SLUG_RE = re.compile(r"stockx\.com/([a-z0-9][a-z0-9-]+[a-z0-9])(?:[/?#]|$)")
_API_BASE = "https://stockx.com/api/products/"


class StockXScraper(BaseScraper):
    """Scraper for StockX sneaker / streetwear listings.

    Attempts the unofficial product API endpoint first.  If that fails (e.g.
    due to auth requirements), falls back to HTML scraping via
    :class:`~scrapling.fetchers.StealthyFetcher`.
    """

    platform = "stockx"

    def _scrape(self, url: str) -> ScrapedItem:
        m = _SLUG_RE.search(url.lower())
        if m:
            try:
                return self._scrape_api(m.group(1))
            except Exception as exc:
                logger.warning("[stockx] API failed (%s), falling back to HTML", exc)
        return self._scrape_html(url)

    # ------------------------------------------------------------------ API

    def _scrape_api(self, slug: str) -> ScrapedItem:
        import urllib.request

        api_url = f"{_API_BASE}{slug}"
        req = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
                "x-requested-with": "XMLHttpRequest",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        product = data.get("Product", data.get("product", data))
        title = product.get("title") or product.get("name")

        # Market data lives under the first child or the product's market itself
        market = product.get("market", {})
        ask = market.get("lowestAsk") or market.get("lowestAskFloat")
        bid = market.get("highestBid") or market.get("highestBidFloat")
        last_sale = market.get("lastSale") or market.get("lastSalePrice")
        # Use lowest ask as the "current price"; fall back to last sale
        price = ask or last_sale or bid

        return ScrapedItem(
            price=float(price) if price else None,
            currency="USD",
            title=title,
            availability="active" if ask else ("active" if last_sale else "unavailable"),
            raw=product,
        )

    # ------------------------------------------------------------------ HTML

    def _scrape_html(self, url: str) -> ScrapedItem:
        from scrapling.fetchers import StealthyFetcher

        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            wait=2000,
        )

        # Try JSON-LD structured data first — most reliable
        script_el = page.css_first("script[type='application/ld+json']")
        if script_el:
            try:
                ld = json.loads(script_el.text)
                if isinstance(ld, list):
                    ld = ld[0]
                offers = ld.get("offers", {})
                raw_price = offers.get("price") or offers.get("lowPrice")
                currency = offers.get("priceCurrency", "USD")
                title = ld.get("name")
                in_stock = offers.get("availability", "").endswith("InStock")
                return ScrapedItem(
                    price=float(raw_price) if raw_price else None,
                    currency=currency,
                    title=title,
                    availability="active" if in_stock else "unavailable",
                )
            except (json.JSONDecodeError, KeyError):
                pass

        title_el = page.css_first("h1[data-testid='product-title']") or page.css_first("h1")
        title = title_el.text.strip() if title_el else None

        price_el = (
            page.css_first("[data-testid='trade-button-lowest-ask'] span")
            or page.css_first("[data-testid='price']")
            or page.css_first("p[data-testid='lowest-ask']")
        )
        raw_price = price_el.text.strip() if price_el else ""
        price = self.parse_price(raw_price)

        return ScrapedItem(
            price=price,
            currency="USD",
            title=title,
            availability="active" if price else "unavailable",
        )
