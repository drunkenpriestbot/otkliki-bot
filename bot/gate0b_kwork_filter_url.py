"""
Gate 0b: находит рабочий URL страницы заказов Kwork, отфильтрованной по
рубрикам "Монтаж и обработка видео", "Анимационный ролик", "ИИ-генерация
видео" — кликает по чекбоксам в реальном браузере и читает итоговый URL
после применения фильтра (SPA, JS-роутинг, статический HTML не содержит
готовых ссылок с query-параметрами).

Не часть production-пайплайна. Разовый диагностический скрипт.
"""

import sys

from playwright.sync_api import sync_playwright

URL = "https://kwork.ru/projects"

TARGET_LABELS = [
    "Монтаж и обработка видео",
    "Анимационный ролик",
    "ИИ-генерация видео",
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
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # закрыть cookie-баннер, если есть, чтобы не перекрывал чекбоксы
        for text in ["Окей!", "Принять", "Ok"]:
            try:
                page.get_by_text(text, exact=True).click(timeout=2000)
                break
            except Exception:
                pass

        clicked = []
        for label in TARGET_LABELS:
            try:
                locator = page.get_by_text(label, exact=True).first
                locator.scroll_into_view_if_needed(timeout=5000)
                locator.click(timeout=5000)
                clicked.append(label)
                page.wait_for_timeout(1500)
            except Exception as e:
                print(f"Не удалось кликнуть '{label}': {e}")

        page.wait_for_timeout(2000)
        final_url = page.url
        html = page.content()
        page.screenshot(path="filter_result.png", full_page=True)
        with open("filter_result.html", "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()

    print(f"Clicked: {clicked}")
    print(f"Final URL after filters applied: {final_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
