"""
Utility script that crawls multiple communities and exports the results.
"""

from __future__ import annotations

from .sites import DCInsideCrawler, GalleryConfig, InstizBoardConfig, InstizCrawler
from .storage import export_by_source


def crawl_dcinside() -> None:
    galleries = [
        GalleryConfig(gallery_id="programming", name="프로그래밍 갤러리", max_pages=2),
        # GalleryConfig(gallery_id="hit", name="HIT", max_pages=1),
    ]

    with DCInsideCrawler() as crawler:
        result = crawler.crawl(galleries)

    paths = export_by_source(posts=result.posts, comments=result.comments)
    print("[DCInside] 저장 완료:", {k: {kk: str(vv) for kk, vv in val.items()} for k, val in paths.items()})


def crawl_instiz() -> None:
    boards = [
        InstizBoardConfig(board="pt", max_pages=2),
    ]

    with InstizCrawler() as crawler:
        result = crawler.crawl(boards)

    paths = export_by_source(posts=result.posts, comments=result.comments)
    print("[Instiz] 저장 완료:", {k: {kk: str(vv) for kk, vv in val.items()} for k, val in paths.items()})


def main() -> None:
    crawl_dcinside()
    crawl_instiz()


if __name__ == "__main__":
    main()
