"""
Simple crawler for TheQoo board listings (title + date).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag
from requests import RequestException

from ..base import BaseCrawler, CrawlResult, progress_bar
from ..models import Post


@dataclass
class TheQooBoardConfig:
    path: str = "talk"  # e.g., "beauty", "beauty/category/25604"
    name: str | None = None
    start_page: int = 1
    max_pages: int = 1
    start_date: datetime | str | None = None
    end_date: datetime | str | None = None


class TheQooCrawler(BaseCrawler):
    site_name = "theqoo"
    BASE_URL = "https://theqoo.net"

    def __init__(self, **kwargs):
        kwargs.setdefault("use_selenium", False)
        kwargs.setdefault("delay", 0.5)
        super().__init__(**kwargs)

    def crawl(self, boards: Sequence[TheQooBoardConfig]) -> CrawlResult:
        posts: list[Post] = []
        for config in progress_bar(boards, desc="[TheQoo] board", unit="board"):
            posts.extend(self._crawl_board(config))
        return CrawlResult(posts=posts, comments=[])

    def _crawl_board(self, config: TheQooBoardConfig) -> list[Post]:
        posts: list[Post] = []
        seen: set[str] = set()
        label = config.name or config.path
        start_dt = self._coerce_date(config.start_date)
        end_dt = self._coerce_date(config.end_date)

        page_iter = progress_bar(
            range(config.start_page, config.start_page + config.max_pages),
            desc=f"[{label}] page",
            unit="page",
        )

        for page in page_iter:
            url = self._build_url(config.path, page)
            soup = self.get_soup(url)
            row_nodes = soup.select("table.bd_lst tbody tr")
            if not row_nodes:
                row_nodes = [
                    cell.find_parent("tr")
                    for cell in soup.select("td.title")
                    if cell.find_parent("tr")
                ]

            stop_pagination = False
            for row in row_nodes:
                if not row:
                    continue
                if "notice" in row.get("class", []):
                    continue
                title_anchor = row.select_one("td.title a[href]")
                if not title_anchor:
                    continue
                href = title_anchor["href"]
                post_id = self._extract_post_id(href)
                if not post_id or post_id in seen:
                    continue
                number_cell = row.select_one("td.no")
                if number_cell:
                    strong = number_cell.find("strong")
                    if strong and "공지" in strong.get_text(strip=True):
                        continue
                seen.add(post_id)

                comment_link = row.select_one("td.title a.replyNum")
                comment_count = self._extract_int(comment_link.get_text(strip=True)) if comment_link else 0
                category_cell = row.select_one("td.cate")
                category = category_cell.get_text(strip=True) if category_cell else None
                date_cell = row.select_one("td.time")
                views_cell = row.select_one("td.m_no")
                posted_at = self._parse_list_date(date_cell)

                if start_dt and posted_at and posted_at < start_dt:
                    stop_pagination = True
                    break
                if end_dt and posted_at and posted_at > end_dt:
                    continue
                if (start_dt or end_dt) and posted_at is None:
                    continue

                detail_data = self._fetch_detail(urljoin(self.BASE_URL, href))
                detail_posted_at = detail_data.get("posted_at") if detail_data else None
                effective_date = detail_posted_at or posted_at

                if start_dt and detail_posted_at and detail_posted_at < start_dt:
                    stop_pagination = True
                    break
                if end_dt and detail_posted_at and detail_posted_at > end_dt:
                    continue

                detail_comment_count = detail_data.get("comment_count") if detail_data else None
                detail_content = detail_data.get("content") if detail_data else ""
                detail_title = detail_data.get("title") if detail_data else None
                detail_author = detail_data.get("author") if detail_data else None
                detail_meta = detail_data.get("meta") if detail_data else {}

                posts.append(
                    Post(
                        site=self.site_name,
                        gallery=label,
                        source_id=post_id,
                        url=urljoin(self.BASE_URL, href),
                        title=detail_title or title_anchor.get_text(strip=True),
                        content=detail_content,
                        author=detail_author,
                        posted_at=effective_date,
                        comment_count=detail_comment_count or comment_count,
                        meta={
                            "board_path": config.path,
                            "category": category,
                            "views": self._extract_int(views_cell.get_text(strip=True)) if views_cell else None,
                            **detail_meta,
                        },
                    )
                )
            if stop_pagination:
                break
        return posts

    def _build_url(self, path: str, page: int) -> str:
        normalized = path.lstrip("/")
        separator = "&" if "?" in normalized else "?"
        return f"{self.BASE_URL}/{normalized}{separator}page={page}"

    @staticmethod
    def _extract_post_id(href: str) -> str | None:
        if "#" in href:
            href = href.split("#", 1)[0]
        parts = href.strip("/").split("/")
        if not parts:
            return None
        last = parts[-1]
        if "?" in last:
            last = last.split("?")[0]
        return last if last.isdigit() else None

    @staticmethod
    def _parse_list_date(node: Tag | None) -> datetime | None:
        if not node:
            return None
        text = node.get_text(strip=True)
        now = datetime.now()
        patterns = [
            "%Y.%m.%d",
            "%y.%m.%d",
            "%m.%d",
            "%H:%M",
            "%m-%d",
        ]
        for fmt in patterns:
            try:
                dt = datetime.strptime(text, fmt)
                if fmt == "%m.%d" or fmt == "%m-%d":
                    dt = dt.replace(year=now.year)
                if fmt == "%H:%M":
                    dt = now.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
                return dt
            except ValueError:
                continue
        return None

    @staticmethod
    def _extract_int(value: str | None) -> int | None:
        if not value:
            return None
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits) if digits else None

    @staticmethod
    def _coerce_date(value: datetime | str | None) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%y.%m.%d"):
                try:
                    dt = datetime.strptime(value, fmt)
                    if dt.year < 100:
                        dt = dt.replace(year=dt.year + 2000)
                    return dt
                except ValueError:
                    continue
        return None

    def _fetch_detail(self, url: str) -> dict | None:
        try:
            soup = self.get_soup(url)
        except RequestException:
            return None

        header = soup.select_one(".theqoo_document_header")
        title = header.select_one(".title").get_text(strip=True) if header else None
        category = header.select_one(".cate").get_text(strip=True) if header else None

        content_node = soup.select_one("article[itemprop='articleBody']")
        content = content_node.get_text("\n", strip=True) if content_node else ""

        author = None
        author_block = soup.select_one(".board .btm_area .side")
        if author_block:
            for child in author_block.children:
                if isinstance(child, NavigableString):
                    candidate = child.strip()
                    if candidate:
                        author = candidate
                        break
        date_node = soup.select_one(".board .btm_area .side.fr span")
        posted_at = self._parse_list_date(date_node)

        return {
            "title": title,
            "author": author,
            "posted_at": posted_at,
            "content": content,
            "comment_count": self._extract_detail_comment_count(soup),
            "meta": {"detail_category": category, "detail_url": url},
        }

    @staticmethod
    def _extract_detail_comment_count(soup: BeautifulSoup) -> int | None:
        header = soup.select_one(".fdb_lst .comment_header_bar")
        if not header:
            return None
        digits = "".join(ch for ch in header.get_text(strip=True) if ch.isdigit())
        return int(digits) if digits else None
