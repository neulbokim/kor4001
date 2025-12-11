"""
Crawler package that provides shared infrastructure plus site-specific crawlers.
"""

from . import config, models, storage  # noqa: F401

try:  # Optional because some workflows do not need Selenium
    from . import driver  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    driver = None  # type: ignore

__all__ = ["config", "models", "storage", "driver"]
