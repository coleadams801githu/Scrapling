"""Tests for scraper URL routing (get_scraper_for_url + PLATFORM_MAP)."""
from __future__ import annotations

import pytest

from resell_radar.scrapers import (
    PLATFORM_MAP,
    DepopScraper,
    EbayScraper,
    GoatScraper,
    GrailedScraper,
    IstdibsScraper,
    PoshmarkScraper,
    StockXScraper,
    TheRealRealScraper,
    VestiaireScraper,
    ScraperError,
    get_scraper_for_url,
)


@pytest.mark.parametrize(
    "url, expected_cls",
    [
        ("https://www.ebay.com/itm/123456789", EbayScraper),
        ("https://www.grailed.com/listings/12345678-brand-item", GrailedScraper),
        ("https://www.1stdibs.com/furniture/tables/dining-tables/some-table/id-f_12345/", IstdibsScraper),
        ("https://poshmark.com/listing/vintage-jacket-abc123", PoshmarkScraper),
        ("https://www.therealreal.com/products/women/apparel/tops/brand-top", TheRealRealScraper),
        ("https://www.vestiairecollective.com/men-s-bags/handbags/brand/item-12345678.shtml", VestiaireScraper),
        ("https://stockx.com/nike-air-max-1-86-big-bubble-black", StockXScraper),
        ("https://www.goat.com/sneakers/air-max-1-86-dq3989-001", GoatScraper),
        ("https://www.depop.com/products/username-vintage-levi-jeans-abc123/", DepopScraper),
    ],
)
def test_get_scraper_for_url(url, expected_cls):
    scraper = get_scraper_for_url(url)
    assert isinstance(scraper, expected_cls)


def test_get_scraper_for_url_unknown_raises():
    with pytest.raises(ScraperError):
        get_scraper_for_url("https://unknown-platform.com/item/123")


def test_platform_map_contains_all_known_platforms():
    expected = {
        "depop", "ebay", "goat", "grailed", "istdibs",
        "poshmark", "stockx", "therealreal", "vestiaire",
    }
    assert set(PLATFORM_MAP.keys()) == expected


def test_scraper_platform_attribute_matches_map_key():
    """Each scraper's ``platform`` attribute must match its map key."""
    for key, cls in PLATFORM_MAP.items():
        assert cls().platform == key, f"{cls.__name__}.platform should be {key!r}"
