"""
Central location for paths and lightweight settings that multiple crawlers use.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"


def ensure_data_dirs() -> None:
    """
    Create the default data directories if they do not exist.

    Separating this logic keeps the directory handling consistent
    no matter where we trigger the crawl from (script, notebook, etc.).
    """

    for path in (DATA_DIR, RAW_DIR, PROCESSED_DIR):
        path.mkdir(parents=True, exist_ok=True)


@dataclass
class DateRange:
    """
    Optional date filter for crawlers that support pagination by time.
    """

    start: str | None = None  # ISO formatted string, e.g. "2024-01-01"
    end: str | None = None
