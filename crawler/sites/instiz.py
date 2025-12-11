"""
Crawler for Instiz boards (e.g., 이슈카테고리).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..base import BaseCrawler, CrawlResult
from ..models import Comment, Post


@dataclass
class InstizBoardConfig:
    board: str = "pt"
    start_page: int = 1
    max_pages: int = 2
    include_comments: bool = True


class InstizCrawler(BaseCrawler):
    site_name = "instiz"
    BASE_URL = "https://www.instiz.net"

    def __init__(self, **kwargs):
        kwargs.setdefault("use_selenium", False)
        kwargs.setdefault("delay", 0.5)
        super().__init__(**kwargs)

    def crawl(self, boards: Sequence[InstizBoardConfig]) -> CrawlResult:
        posts: list[Post] = []
        comments: list[Comment] = []
        for config in boards:
            board_posts, board_comments = self._crawl_board(config)
            posts.extend(board_posts)
            comments.extend(board_comments)
        return CrawlResult(posts=posts, comments=comments)

    def _crawl_board(self, config: InstizBoardConfig) -> tuple[list[Post], list[Comment]]:
        posts: list[Post] = []
        comments: list[Comment] = []
        seen_ids: set[str] = set()

        for offset in range(config.max_pages):
            page = config.start_page + offset
            url = f"{self.BASE_URL}/{config.board}?page={page}"
            soup = self.get_soup(url)
            rows = soup.select("tr[id^='list']")
            if not rows:
                break

            for row in rows:
                link = row.find("a", href=True)
                if not link:
                    continue
                href = link["href"]
                post_id = self._extract_post_id(href)
                if not post_id or post_id in seen_ids:
                    continue

                title = self._extract_title(row)
                view_count = self._extract_views(row)
                list_comment_count = self._extract_comment_count(row)

                post, post_comments = self._parse_post(
                    board=config.board,
                    href=href,
                    post_id=post_id,
                    fallback_title=title,
                    fallback_comment_count=list_comment_count,
                )
                if not post:
                    continue

                if view_count is not None:
                    post.meta["views"] = view_count

                posts.append(post)
                if config.include_comments:
                    comments.extend(post_comments)
                seen_ids.add(post_id)

        return posts, comments

    def _parse_post(
        self,
        *,
        board: str,
        href: str,
        post_id: str,
        fallback_title: str | None,
        fallback_comment_count: int | None,
    ) -> tuple[Post | None, list[Comment]]:
        detail_url = urljoin(self.BASE_URL, href)
        soup = self.get_soup(detail_url)

        title = self._extract_meta(soup, property_name="og:title") or fallback_title or ""
        content_node = soup.select_one("div.memo_content")
        content = content_node.get_text("\n", strip=True) if content_node else ""
        published = self._extract_meta(soup, property_name="article:published_time")
        posted_at = datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None

        image_url = self._extract_meta(soup, property_name="og:image")
        if image_url:
            content = f"{content}\n[이미지] {image_url}" if content else image_url

        post = Post(
            site=self.site_name,
            gallery=board,
            source_id=post_id,
            url=detail_url,
            title=title,
            content=content,
            author=None,
            posted_at=posted_at,
            comment_count=fallback_comment_count or 0,
            meta={"board": board},
        )

        comment_rows = soup.select("#ajax_table tr")
        parsed_comments: list[Comment] = []
        for idx, row in enumerate(comment_rows, start=1):
            comment = self._parse_comment_row(row, post_id, idx, board)
            if comment:
                parsed_comments.append(comment)

        post.comment_count = len(parsed_comments)
        return post, parsed_comments

    def _parse_comment_row(self, row: Tag, post_id: str, index: int, board: str) -> Comment | None:
        author_node = row.select_one(".href")
        content_node = row.select_one(".comment_line span[id^='n']")
        time_node = row.select_one(".comment_line .minitext")
        if not content_node:
            return None

        author = author_node.get_text(strip=True) if author_node else None
        content = content_node.get_text(" ", strip=True)
        timestamp = None
        if time_node and time_node.has_attr("onmouseover"):
            raw = time_node["onmouseover"]
            parts = raw.replace("'", '"').split('"')
            for part in parts:
                if part.strip().startswith("202"):
                    try:
                        timestamp = datetime.strptime(part.strip(), "%Y/%m/%d %H:%M:%S")
                        break
                    except ValueError:
                        continue

        return Comment(
            site=self.site_name,
            source_id=f"{post_id}_{index}",
            author=author,
            content=content,
            posted_at=timestamp,
            meta={"post_id": post_id, "board": board},
        )

    @staticmethod
    def _extract_post_id(href: str) -> str | None:
        fragments = href.split("/")
        if not fragments:
            return None
        last = fragments[-1]
        if "?" in last:
            last = last.split("?")[0]
        return last if last.isdigit() else None

    @staticmethod
    def _extract_title(row: Tag) -> str | None:
        title_node = row.select_one("div.sbj")
        if not title_node:
            return None
        return title_node.get_text(" ", strip=True)

    @staticmethod
    def _extract_views(row: Tag) -> int | None:
        view_node = row.select_one("div.listno")
        if not view_node:
            return None
        text = view_node.get_text(" ", strip=True)
        marker = text.find("조회")
        if marker != -1:
            digits = "".join(ch for ch in text[marker:] if ch.isdigit())
            if digits:
                return int(digits)
        return None

    @staticmethod
    def _extract_comment_count(row: Tag) -> int | None:
        cmt = row.select_one("span.cmt")
        if not cmt:
            return None
        digits = "".join(ch for ch in cmt.get_text(strip=True) if ch.isdigit())
        return int(digits) if digits else None

    @staticmethod
    def _extract_meta(soup: BeautifulSoup, *, property_name: str) -> str | None:
        node = soup.select_one(f'meta[property="{property_name}"]')
        if node:
            return node.get("content")
        return None
