"""
Gate 0: проверка, отдаёт ли Kwork нормальную страницу заказов
анонимному запросу (без логина) с IP, откуда реально бегает раннер
GitHub Actions (датацентр Azure/Microsoft) — или сразу капчу/403.

Не часть production-пайплайна. Разовый диагностический скрипт (см. вердикт
совета в сессии 023): результат решает, нужна ли авторизация вообще и стоит
ли вообще строить monitor_kwork.py на Playwright+Actions.

Сохраняет screenshot.png и page.html — смотреть глазами после прогона.
"""

import sys

from playwright.sync_api import sync_playwright

URL = "https://kwork.ru/projects"

CAPTCHA_MARKERS = [
    "captcha",
    "cloudflare",
    "checking your browser",
    "доступ ограничен",
    "подтвердите, что вы не робот",
]


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )

        response = page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)  # дать дорисоваться JS-контенту

        status = response.status if response else None
        html = page.content()
        title = page.title()

        page.screenshot(path="screenshot.png", full_page=True)
        with open("page.html", "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()

    html_lower = html.lower()
    hit_markers = [m for m in CAPTCHA_MARKERS if m in html_lower]

    print(f"HTTP status: {status}")
    print(f"Title: {title}")
    print(f"HTML length: {len(html)}")
    print(f"Captcha/antibot markers found: {hit_markers or 'none'}")

    # Грубая эвристика "похоже на реальную ленту заказов": страница большая
    # и не содержит явных маркеров антибота. Финальное решение — смотреть
    # screenshot.png/page.html руками, это не заменяет ручную проверку.
    looks_ok = status == 200 and len(html) > 20000 and not hit_markers
    print(f"Looks like real order feed (heuristic, verify manually): {looks_ok}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
