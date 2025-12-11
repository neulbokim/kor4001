from argparse import ArgumentParser

from crawler.sites import InstizCrawler, InstizBoardConfig
from crawler.storage import export_by_source


def main(max_pages: int) -> None:
    boards = [
        InstizBoardConfig(board="pt", max_pages=max_pages),
    ]
    with InstizCrawler() as crawler:
        result = crawler.crawl(boards)

    export_paths = export_by_source(posts=result.posts, comments=result.comments)
    print(export_paths)
    if result.posts:
        print(result.posts[0].title, result.posts[0].posted_at)
        print(result.posts[-1].title, result.posts[-1].posted_at)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=2, help="크롤링할 최대 페이지 수")
    args = parser.parse_args()
    main(args.max_pages)
