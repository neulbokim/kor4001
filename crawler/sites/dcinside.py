"""
Crawler for DCInside galleries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from requests import RequestException

from ..base import BaseCrawler, CrawlResult, progress_bar
from ..models import Comment, Post

DATE_FORMAT = "%Y.%m.%d %H:%M:%S"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in (DATE_FORMAT, "%Y.%m.%d", "%y.%m.%d %H:%M:%S", "%y.%m.%d"):
        try:
            dt = datetime.strptime(value, fmt)
            # DCInside omits century in some contexts -> patch to 2000+
            if dt.year < 2000:
                dt = dt.replace(year=dt.year + 2000)
            return dt
        except ValueError:
            continue
    return None


def _parse_list_range(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    now = datetime.now()
    patterns = [
        "%Y-%m-%d %H:%M:%S",
        "%Y.%m.%d %H:%M:%S",
        "%y.%m.%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%y/%m/%d %H:%M:%S",
        "%Y.%m.%d",
        "%Y/%m/%d",
        "%y.%m.%d",
        "%y/%m/%d",
    ]
    for fmt in patterns:
        try:
            dt = datetime.strptime(value, fmt)
            if dt.year < 2000:
                dt = dt.replace(year=dt.year + 2000)
            return dt
        except ValueError:
            continue
    if ":" in value and value.count(":") == 1:
        hour, minute = value.split(":")
        return now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    return _parse_datetime(value if len(value.split(".")) == 3 else f"20{value}")


def _coerce_datetime(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


@dataclass
class GalleryConfig:
    gallery_id: str
    name: str | None = None
    start_page: int = 1
    max_pages: int = 3
    start_date: datetime | str | None = None
    end_date: datetime | str | None = None
    include_comments: bool = True

    def normalized_start(self) -> datetime | None:
        return _coerce_datetime(self.start_date)

    def normalized_end(self) -> datetime | None:
        return _coerce_datetime(self.end_date)


class DCInsideCrawler(BaseCrawler):
    site_name = "dcinside"
    BASE_URL = "https://gall.dcinside.com"
    EXCLUDED_SUBJECTS = {"공지", "설문", "AD"}

    def __init__(self, **kwargs):
        kwargs.setdefault("use_selenium", False)
        kwargs.setdefault("delay", 0.5)
        super().__init__(**kwargs)

    def crawl(self, galleries: Sequence[GalleryConfig]) -> CrawlResult:
        posts: list[Post] = []
        comments: list[Comment] = []
        for config in progress_bar(galleries, desc="[DCInside] gallery", unit="gallery"):
            gallery_posts, gallery_comments = self._crawl_gallery(config)
            posts.extend(gallery_posts)
            comments.extend(gallery_comments)
        return CrawlResult(posts=posts, comments=comments)

    def _crawl_gallery(self, config: GalleryConfig) -> tuple[list[Post], list[Comment]]:
        posts: list[Post] = []
        comments: list[Comment] = []
        seen_ids: set[str] = set()
        start_dt = config.normalized_start()
        end_dt = config.normalized_end()
        label = config.name or config.gallery_id

        page_iter = progress_bar(
            range(config.start_page, config.start_page + config.max_pages),
            desc=f"[DCInside {label}] page",
            unit="page",
        )

        for page in page_iter:
            url = f"{self.BASE_URL}/board/lists/?id={config.gallery_id}&page={page}"
            try:
                soup = self.get_soup(url)
            except RequestException:
                continue
            rows = soup.select("table.gall_list tbody tr.ub-content")
            if not rows:
                break

            for row in rows:
                data_type = row.get("data-type", "")
                if data_type == "icon_notice":
                    continue
                number_cell = row.find("td", class_="gall_num")
                if not number_cell:
                    continue
                post_id = row.get("data-no") or number_cell.get_text(strip=True)
                if not post_id or post_id in seen_ids or not post_id.isdigit():
                    continue

                title_cell = row.find("td", class_="gall_tit")
                anchor = title_cell.find("a", href=True) if title_cell else None
                if not anchor:
                    continue
                href = anchor["href"]
                if not href.startswith("/board/view/"):
                    continue

                relative_date = row.find("td", class_="gall_date")
                date_text = relative_date.get_text(strip=True) if relative_date else None
                list_date_text = relative_date.get("title") if relative_date and relative_date.get("title") else date_text
                list_date = _parse_list_range(list_date_text or date_text)
                list_title = anchor.get_text(strip=True) if anchor else None
                writer_cell = row.find("td", class_="gall_writer")
                list_writer = None
                list_writer_ip = None
                list_writer_uid = None
                if writer_cell:
                    nickname = writer_cell.find("span", class_="nickname")
                    list_writer = nickname.get_text(strip=True) if nickname else writer_cell.get_text(strip=True)
                    ip_span = writer_cell.find("span", class_="ip")
                    list_writer_ip = ip_span.get_text(strip=True) if ip_span else None
                    list_writer_uid = writer_cell.get("data-uid") or writer_cell.get("user_id")
                list_views_cell = row.find("td", class_="gall_count")
                list_reco_cell = row.find("td", class_="gall_recommend")
                reply_box = row.find("a", class_="reply_numbox")
                reply_count = None
                if reply_box:
                    span = reply_box.find("span", class_="reply_num")
                    if span:
                        reply_count = _extract_int(span.get_text(strip=True))

                detail_post, detail_comments = self._parse_post(
                    config=config,
                    post_id=post_id,
                    relative_url=href,
                    list_date=list_date,
                    list_title=list_title,
                    list_writer=list_writer,
                    list_meta={
                        "writer_ip": list_writer_ip,
                        "writer_uid": list_writer_uid,
                        "list_date_text": list_date_text,
                        "list_views": _extract_int(list_views_cell.get_text(strip=True)) if list_views_cell else None,
                        "list_recommendations": _extract_int(list_reco_cell.get_text(strip=True)) if list_reco_cell else None,
                        "list_comment_count": reply_count,
                    },
                )
                if not detail_post:
                    continue

                post_dt = detail_post.posted_at or list_date
                if start_dt and post_dt and post_dt < start_dt:
                    continue
                if end_dt and post_dt and post_dt > end_dt:
                    continue

                posts.append(detail_post)
                if config.include_comments:
                    comments.extend(detail_comments)
                seen_ids.add(post_id)

        return posts, comments

    def _parse_post(
        self,
        *,
        config: GalleryConfig,
        post_id: str,
        relative_url: str,
        list_date: datetime | None,
        list_title: str | None,
        list_writer: str | None,
        list_meta: dict | None,
    ) -> tuple[Post | None, list[Comment]]:
        detail_url = urljoin(self.BASE_URL, relative_url)
        try:
            soup = self.get_soup(detail_url)
        except RequestException:
            return None, []
        title_node = soup.select_one("span.title_subject")
        content_node = soup.select_one("div.write_div")
        if not title_node or not content_node:
            return None, []

        title = title_node.get_text(strip=True) if title_node else (list_title or "")
        content = content_node.get_text("\n", strip=True)
        author_node = soup.select_one("span.nickname")
        author = author_node.get_text(strip=True) if author_node else list_writer
        date_node = soup.select_one("span.gall_date")
        posted_at = _parse_datetime(date_node.get_text(strip=True) if date_node else None) or list_date

        view_node = soup.select_one("span.gall_count")
        views = None
        if view_node:
            views = _extract_int(view_node.get_text(strip=True))

        recommend_node = soup.select_one("span.gall_reply_num")
        recommends = None
        if recommend_node:
            recommends = _extract_int(recommend_node.get_text(strip=True))

        post = Post(
            site=self.site_name,
            gallery=config.name or config.gallery_id,
            source_id=post_id,
            url=detail_url,
            title=title,
            content=content,
            author=author,
            posted_at=posted_at,
            comment_count=0,
            meta={
                "views": views,
                "recommendations": recommends,
                "gallery_id": config.gallery_id,
                "page_url": detail_url,
                "list_writer": list_writer,
                **(list_meta or {}),
            },
        )

        comment_nodes = soup.select("li.ub-content")
        parsed_comments: list[Comment] = []
        for node in comment_nodes:
            content_block = node.select_one("p.usertxt") or node.select_one("div.reply-content")
            if not content_block:
                continue
            comment_text = content_block.get_text(" ", strip=True)
            if not comment_text:
                continue

            user_node = node.select_one("span.nickname") or node.select_one("span.nick") or node.select_one("span.ip")
            comment_author = user_node.get_text(strip=True) if user_node else None
            comment_date_text = node.select_one("span.date_time")
            comment_dt = (
                _parse_datetime(comment_date_text.get_text(strip=True))
                if comment_date_text
                else None
            )

            parsed_comments.append(
                Comment(
                    site=self.site_name,
                    source_id=f"{post_id}_{len(parsed_comments)+1}",
                    author=comment_author,
                    content=comment_text,
                    posted_at=comment_dt,
                    meta={
                        "post_id": post_id,
                        "gallery_id": config.gallery_id,
                        "gallery": config.name or config.gallery_id,
                    },
                )
            )

        post.comment_count = len(parsed_comments)
        return post, parsed_comments


def _extract_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else None
