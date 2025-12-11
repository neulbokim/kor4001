"""
Utilities for constructing and managing Selenium WebDriver instances.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def build_chrome_driver(
    *, headless: bool = True, block_images: bool = True, extra_args: list[str] | None = None
) -> webdriver.Chrome:
    """
    Create a Chrome WebDriver with sane defaults for crawling.
    """

    options = Options()
    options.headless = headless
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    for arg in extra_args or []:
        options.add_argument(arg)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    if block_images:
        driver.execute_cdp_cmd(
            "Network.setBlockedURLs",
            {"urls": ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp", "*.svg", "*.woff", "*.woff2"]},
        )
        driver.execute_cdp_cmd("Network.enable", {})

    return driver


@contextmanager
def chrome_driver(
    *, headless: bool = True, block_images: bool = True, extra_args: list[str] | None = None
) -> Iterator[webdriver.Chrome]:
    """
    Context manager wrapper so callers can simply use `with chrome_driver() as driver`.
    """

    driver = build_chrome_driver(
        headless=headless,
        block_images=block_images,
        extra_args=extra_args,
    )
    try:
        yield driver
    finally:
        driver.quit()

