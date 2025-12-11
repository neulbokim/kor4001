from argparse import ArgumentParser

from run_dcinside import main as run_dcinside
from run_theqoo import main as run_theqoo


def main(dc_max_pages: int, theqoo_max_pages: int) -> None:
    print("[run_communities] DCInside 크롤링 시작")
    run_dcinside(dc_max_pages)
    print("[run_communities] TheQoo 크롤링 시작")
    run_theqoo(theqoo_max_pages)


if __name__ == "__main__":
    parser = ArgumentParser(description="DCInside와 TheQoo 크롤러를 순차 실행합니다.")
    parser.add_argument("--dc-max-pages", type=int, default=100, help="DCInside 갤러리별 max 페이지")
    parser.add_argument("--theqoo-max-pages", type=int, default=100, help="TheQoo 보드별 max 페이지")
    args = parser.parse_args()
    main(args.dc_max_pages, args.theqoo_max_pages)
