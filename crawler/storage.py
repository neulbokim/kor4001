"""
Persistence helpers for saving crawled data as JSON/CSV.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from .config import PROCESSED_DIR, RAW_DIR, ensure_data_dirs
from .models import Comment, Post


def _prepare_records(records: Iterable[Post | Comment]) -> list[dict]:
    serialized = []
    for item in records:
        if hasattr(item, "to_dict"):
            serialized.append(item.to_dict())  # type: ignore[arg-type]
        elif isinstance(item, dict):
            serialized.append(item)
        else:
            raise TypeError(f"Unsupported record type: {type(item)}")
    return serialized


def _slugify(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.strip().lower()
    sanitized = "".join(ch if ch.isalnum() else "_" for ch in lowered)
    return sanitized.strip("_") or ""


def _source_prefix(site: str | None, gallery: str | None) -> str:
    site_slug = _slugify(site) or "data"
    gallery_slug = _slugify(gallery)
    return f"{site_slug}_{gallery_slug}" if gallery_slug else site_slug


def save_json(records: Iterable[Post | Comment | dict], filename: str) -> Path:
    ensure_data_dirs()
    path = RAW_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(_prepare_records(records), f, ensure_ascii=False, indent=2)
    return path


def save_csv(records: Iterable[Post | Comment | dict], filename: str) -> Path:
    ensure_data_dirs()
    path = RAW_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(_prepare_records(records))
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def export_dataset(
    *,
    posts: Sequence[Post] | None = None,
    comments: Sequence[Comment] | None = None,
    prefix: str,
) -> dict[str, Path]:
    """
    Save posts/comments in CSV format while returning the paths.
    JSON 저장은 제거됨 (CSV만 저장)
    """

    results: dict[str, Path] = {}

    if posts:
        results["posts_csv"] = save_csv(posts, f"{prefix}_posts.csv")

    if comments:
        results["comments_csv"] = save_csv(comments, f"{prefix}_comments.csv")

    return results



def _comment_group_value(comment: Comment) -> str | None:
    meta = comment.meta or {}
    for key in ("gallery", "gallery_id", "board"):
        if key in meta and meta[key]:
            return str(meta[key])
    return None


def export_by_source(
    *,
    posts: Sequence[Post] | None = None,
    comments: Sequence[Comment] | None = None,
) -> dict[str, dict[str, Path]]:
    """
    Save datasets grouped by site/gallery so filenames follow `site_gallery_*`.
    JSON 저장은 제거됨 (CSV만 저장)
    """

    results: dict[str, dict[str, Path]] = {}
    posts_by = defaultdict(list)
    comments_by = defaultdict(list)

    for post in posts or []:
        key = _source_prefix(post.site, post.gallery)
        posts_by[key].append(post)
    for comment in comments or []:
        key = _source_prefix(comment.site, _comment_group_value(comment))
        comments_by[key].append(comment)

    for key, grouped_posts in posts_by.items():
        bucket = results.setdefault(key, {})
        bucket["posts_csv"] = save_csv(grouped_posts, f"{key}_posts.csv")

    for key, grouped_comments in comments_by.items():
        bucket = results.setdefault(key, {})
        bucket["comments_csv"] = save_csv(grouped_comments, f"{key}_comments.csv")

    return results
