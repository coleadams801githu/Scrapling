"""Scraper registry — maps platform names and URL patterns to scraper classes."""
from __future__ import annotations

from resell_radar.scrapers.base import BaseScraper, ScrapedItem, ScraperError
from resell_radar.scrapers.ebay import EbayScraper
from resell_radar.scrapers.grailed import GrailedScraper
from resell_radar.scrapers.istdibs import IstdibsScraper
from resell_radar.scrapers.poshmark import PoshmarkScraper
from resell_radar.scrapers.therealreal import TheRealRealScraper
from resell_radar.scrapers.vestiaire import VestiaireScraper

__all__ = [
    "BaseScraper",
    "ScrapedItem",
    "ScraperError",
    "EbayScraper",
    "GrailedScraper",
    "IstdibsScraper",
    "PoshmarkScraper",
    "TheRealRealScraper",
    "VestiaireScraper",
    "get_scraper_for_url",
    "PLATFORM_MAP",
]

PLATFORM_MAP: dict[str, type[BaseScraper]] = {
    "ebay": EbayScraper,
    "grailed": GrailedScraper,
    "istdibs": IstdibsScraper,
    "poshmark": PoshmarkScraper,
    "therealreal": TheRealRealScraper,
    "vestiaire": VestiaireScraper,
}

_URL_PATTERNS: list[tuple[str, str]] = [
    ("ebay.com", "ebay"),
    ("grailed.com", "grailed"),
    ("1stdibs.com", "istdibs"),
    ("poshmark.com", "poshmark"),
    ("therealreal.com", "therealreal"),
    ("vestiairecollective.com", "vestiaire"),
]


def get_scraper_for_url(url: str) -> BaseScraper:
    """Return an instantiated scraper for *url*, or raise :class:`ScraperError`."""
    url_lower = url.lower()
    for domain, platform in _URL_PATTERNS:
        if domain in url_lower:
            return PLATFORM_MAP[platform]()
    raise ScraperError(f"No scraper registered for URL: {url}")
