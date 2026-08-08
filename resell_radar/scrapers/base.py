"""Base scraper with retry logic and common utilities."""
from __future__ import annotations

import re
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

_CURRENCY_PATTERN = re.compile(r"[^\d.,]")
_PRICE_PATTERN = re.compile(r"[\d,]+\.?\d*")


@dataclass
class ScrapedItem:
    """Normalised data returned by every platform scraper."""

    price: float | None = None
    currency: str = "USD"
    title: str | None = None
    availability: str = "active"  # active | sold | unavailable
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    raw: dict = field(default_factory=dict)


class ScraperError(Exception):
    """Raised when a scraper cannot obtain data after all retries."""


class BaseScraper(ABC):
    """Abstract base for all platform scrapers.

    Subclasses must implement :meth:`_scrape`.
    """

    platform: str = "unknown"
    max_retries: int = 3
    retry_delay: float = 2.0  # seconds between retries

    def fetch(self, url: str) -> ScrapedItem:
        """Fetch *url* with retry logic.  Returns a :class:`ScrapedItem`."""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                item = self._scrape(url)
                item.scraped_at = datetime.utcnow()
                return item
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "[%s] attempt %d/%d failed for %s: %s",
                    self.platform,
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)
        raise ScraperError(
            f"[{self.platform}] all {self.max_retries} attempts failed for {url}"
        ) from last_exc

    @abstractmethod
    def _scrape(self, url: str) -> ScrapedItem:  # pragma: no cover
        """Platform-specific scraping logic.  Must return a :class:`ScrapedItem`."""

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def parse_price(raw: str) -> float | None:
        """Extract a float price from a messy string like '$1,299.00'."""
        if not raw:
            return None
        cleaned = raw.replace(",", "")
        match = _PRICE_PATTERN.search(cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None

    @staticmethod
    def detect_currency(raw: str) -> str:
        """Guess ISO currency code from a price string."""
        if "€" in raw:
            return "EUR"
        if "£" in raw:
            return "GBP"
        if "¥" in raw:
            return "JPY"
        return "USD"
