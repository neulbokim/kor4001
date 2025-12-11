import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from argparse import ArgumentParser
from crawler.sites.dcinside import DCInsideCrawler, GalleryConfig
from crawler.storage import export_by_source



def build_galleries(max_pages: int) -> list[GalleryConfig]:
    return [
        GalleryConfig(gallery_id="football_new9", name="해외축구_갤러리", max_pages=max_pages),
        GalleryConfig(gallery_id="leagueoflegends6", name="리그오브레전드_갤러리", max_pages=max_pages),
        GalleryConfig(gallery_id="exam_new2", name="수능_갤러리", max_pages=max_pages),
        GalleryConfig(gallery_id="cosmetic", name="향수화장품_갤러리", max_pages=max_pages),
        GalleryConfig(
            gallery_id="entertainment",
            name="국내연예-남자여자연예인_갤러리",
            max_pages=max_pages,
        ),
        GalleryConfig(gallery_id="m_entertainer_new1", name="남자연예인_갤러리", max_pages=max_pages),
    ]


def main(max_pages: int) -> None:
    galleries = build_galleries(max_pages)
    with DCInsideCrawler() as crawler:
        for gallery in galleries:
            print(f"[run_dcinside] '{gallery.name or gallery.gallery_id}' 크롤링 시작")
            result = crawler.crawl([gallery])
            export_paths = export_by_source(posts=result.posts, comments=result.comments)
            print(export_paths)
            if result.posts:
                print(result.posts[0].title, result.posts[0].posted_at)
                print(result.posts[-1].title, result.posts[-1].posted_at)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=100, help="각 갤러리에서 크롤링할 최대 페이지 수")
    args = parser.parse_args()
    main(args.max_pages)
