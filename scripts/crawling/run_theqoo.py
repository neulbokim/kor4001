import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from argparse import ArgumentParser
from crawler.sites import TheQooCrawler, TheQooBoardConfig
from crawler.storage import export_by_source



def main(max_pages: int) -> None:
    boards = [
        TheQooBoardConfig(path="beauty/category/25604", max_pages=max_pages),
        TheQooBoardConfig(path="ktalk/category/1947874", max_pages=max_pages),
    ]

    with TheQooCrawler() as crawler:
        for board in boards:
            label = board.name or board.path
            print(f"[run_theqoo] '{label}' 보드 크롤링 시작")
            result = crawler.crawl([board])
            export_paths = export_by_source(posts=result.posts)
            print(export_paths)
            if result.posts:
                print(result.posts[0].title, result.posts[0].posted_at)
                print(result.posts[-1].title, result.posts[-1].posted_at)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=100, help="각 보드에서 크롤링할 최대 페이지 수")
    args = parser.parse_args()
    main(args.max_pages)
