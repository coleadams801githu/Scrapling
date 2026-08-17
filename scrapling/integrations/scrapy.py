"""Scrapy integration for Scrapling.

Drop-in replacement for Parsel inside a Scrapy project.  Two usage patterns
are provided:

1. **Middleware** – automatically swap every ``response.selector`` (a Parsel
   ``Selector``) for a Scrapling ``Selector`` on its way to your spider
   callbacks.  Add to ``settings.py``::

       SPIDER_MIDDLEWARES = {
           'scrapling.integrations.scrapy.ScraplingMiddleware': 100,
       }

2. **Decorator** – selectively wrap individual spider callback methods::

       from scrapling.integrations.scrapy import scrapling_callback

       class MySpider(scrapy.Spider):
           name = "example"
           start_urls = ["https://example.com"]

           @scrapling_callback
           def parse(self, response):
               # response.selector is now a Scrapling Selector
               for title in response.selector.css("h1::text").getall():
                   yield {"title": title}

The ``response.selector`` replacement is done lazily (only when first
accessed) so there is no overhead on response objects that are never
scraped.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Generator, Optional

try:
    import scrapy  # noqa: F401  – only used for type checking / runtime guard
    from scrapy import Spider
    from scrapy.http import Response, TextResponse
    _SCRAPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SCRAPY_AVAILABLE = False
    Spider = object  # type: ignore[assignment,misc]
    Response = object  # type: ignore[assignment]
    TextResponse = object  # type: ignore[assignment]

from scrapling.parser import Selector as ScraplingSelector


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _wrap_response(response: Any) -> Any:
    """Patch ``response.selector`` with a Scrapling ``Selector`` instance.

    The patch is applied *in-place* and is idempotent: calling it on an
    already-patched response is a no-op.

    :param response: A Scrapy ``TextResponse`` (or subclass) object.
    :return: The same response object, with ``selector`` replaced.
    """
    if not _SCRAPY_AVAILABLE:
        raise ImportError(
            "Scrapy is not installed.  Install it with: pip install scrapy"
        )

    # Already patched – avoid double-wrapping
    if isinstance(getattr(response, "selector", None), ScraplingSelector):
        return response

    # Only text responses have meaningful HTML bodies
    if not isinstance(response, TextResponse):
        return response

    scrapling_selector = ScraplingSelector(
        content=response.text,
        url=response.url,
        encoding=response.encoding or "utf-8",
    )

    # Override attribute (works on Scrapy responses which don't use __slots__)
    response.__dict__["selector"] = scrapling_selector
    return response


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class ScraplingMiddleware:
    """Scrapy Spider Middleware that replaces ``response.selector`` with a
    Scrapling ``Selector`` for all responses before they reach the spider.

    Register in ``settings.py``::

        SPIDER_MIDDLEWARES = {
            'scrapling.integrations.scrapy.ScraplingMiddleware': 100,
        }
    """

    @classmethod
    def from_crawler(cls, crawler: Any) -> "ScraplingMiddleware":  # pragma: no cover
        return cls()

    # Scrapy calls this for every response delivered to a spider callback.
    def process_spider_input(self, response: Any, spider: Any) -> None:
        """Swap ``response.selector`` before the callback sees the response."""
        _wrap_response(response)
        return None  # signal that we did not handle the response ourselves

    def process_spider_output(
        self,
        response: Any,
        result: Any,
        spider: Any,
    ) -> Generator:
        """Pass through – we only care about input."""
        yield from result

    def process_spider_exception(
        self,
        response: Any,
        exception: Exception,
        spider: Any,
    ) -> Optional[Generator]:
        """Pass through – we only care about input."""
        return None


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def scrapling_callback(func: Callable) -> Callable:
    """Decorator that replaces ``response.selector`` with a Scrapling
    ``Selector`` before calling the wrapped spider callback.

    Works with both regular functions and async generators::

        class MySpider(scrapy.Spider):
            name = "example"
            start_urls = ["https://example.com"]

            @scrapling_callback
            def parse(self, response):
                yield {"title": response.selector.css("title::text").get()}

    :param func: The spider callback to wrap.
    :return: A wrapped version of *func*.
    """
    @functools.wraps(func)
    def wrapper(self: Any, response: Any, *args: Any, **kwargs: Any) -> Any:
        _wrap_response(response)
        return func(self, response, *args, **kwargs)

    return wrapper


__all__ = [
    "ScraplingMiddleware",
    "scrapling_callback",
]
