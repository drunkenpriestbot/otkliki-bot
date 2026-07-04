"""
Gate 0c: проверяет, фильтрует ли /projects через query-параметр
?keyword=... (найден input name="keyword" в фильтре "Ключевые слова" на
странице заказов) — без кликов по дереву рубрик, просто прямой переход
по URL с параметром. Дешевле и надёжнее, чем раскрывать checkbox-дерево.

Не часть production-пайплайна. Разовый диагностический скрипт.
"""

import sys
import urllib.parse

from playwright.sync_api import sync_playwright

BASE = "https://kwork.ru/projects"
KEYWORDS = ["монтаж", "видео", "reels"]


def extract_titles(page):
    # заголовки карточек заказов — .card-item__title или похожий класс;
    # неизвестен точно, поэтому просто вытаскиваем видимый текст ссылок
    # на /projects/<id>
    return page.eval_on_selector_all(
        "a[href*='/projects/']",
        "els => els.map(e => e.textContent.trim()).filter(t => t.length > 3)",
    )


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )

        print("=== baseline (no filter) ===")
        page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)
        baseline_titles = extract_titles(page)
        print(f"URL: {page.url}")
        for t in baseline_titles[:8]:
            print(f"  - {t}")

        for kw in KEYWORDS:
            url = f"{BASE}?keyword={urllib.parse.quote(kw)}"
            print(f"\n=== keyword={kw} ===")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
            titles = extract_titles(page)
            print(f"URL after load: {page.url}")
            print(f"Count: {len(titles)}")
            for t in titles[:8]:
                print(f"  - {t}")

        browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
