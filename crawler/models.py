"""
Dataclasses shared by multiple crawlers for consistent serialization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def _serialize_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


@dataclass
class Comment:
    site: str
    source_id: str
    author: str | None
    content: str
    posted_at: datetime | None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["posted_at"] = _serialize_dt(self.posted_at)
        return data


@dataclass
class Post:
    site: str
    gallery: str
    source_id: str
    url: str
    title: str
    content: str
    author: str | None
    posted_at: datetime | None
    comment_count: int = 0
    meta: dict[str, Any] = field(default_factory=dict)
    comments: list[Comment] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["posted_at"] = _serialize_dt(self.posted_at)
        data["comments"] = [comment.to_dict() for comment in self.comments]
        return data
