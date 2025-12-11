"""
Abstract base crawler that wraps Selenium driver management and parsing helpers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable, Protocol, TypeVar

import requests
from bs4 import BeautifulSoup
from selenium.webdriver.remote.webdriver import WebDriver

from . import driver as driver_module


class SupportsToDict(Protocol):
    def to_dict(self) -> dict: ...


@dataclass
class CrawlResult:
    posts: list[SupportsToDict]
    comments: list[SupportsToDict]


T = TypeVar("T")

try:
    from tqdm.auto import tqdm as _tqdm  # type: ignore[assignment]
except ImportError:
    _tqdm = None


def progress_bar(iterable: Iterable[T], **kwargs) -> Iterable[T]:
    return _tqdm(iterable, **kwargs) if _tqdm else iterable


class BaseCrawler:
    """
    Provides a shared Selenium driver plus convenience helpers.
    """

    site_name: str = "generic"

    def __init__(
        self,
        *,
        driver: WebDriver | None = None,
        headless: bool = True,
        block_images: bool = True,
        delay: float = 1.5,
        use_selenium: bool = True,
        request_headers: dict[str, str] | None = None,
    ):
        self.delay = delay
        self.use_selenium = use_selenium
        self._driver_provided = driver is not None
        self.driver = None
        self.session: requests.Session | None = None
        self.request_headers = request_headers or {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

        if self.use_selenium:
            self.driver = driver or driver_module.build_chrome_driver(
                headless=headless, block_images=block_images
            )
        else:
            self.session = requests.Session()

    def close(self) -> None:
        if self.use_selenium and self.driver and not self._driver_provided:
            self.driver.quit()
        if self.session:
            self.session.close()

    def __enter__(self) -> "BaseCrawler":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    def get_soup(self, url: str) -> BeautifulSoup:
        """
        Load the URL through Selenium (default) or `requests` and return soup.
        """

        if self.use_selenium:
            assert self.driver is not None
            self.driver.get(url)
            time.sleep(self.delay)
            page_source = self.driver.page_source
        else:
            assert self.session is not None
            response = self.session.get(url, headers=self.request_headers, timeout=20)
            response.raise_for_status()
            page_source = response.text

        return BeautifulSoup(page_source, "html.parser")

    def crawl(self, *args, **kwargs) -> CrawlResult:  # pragma: no cover - interface method
        raise NotImplementedError
