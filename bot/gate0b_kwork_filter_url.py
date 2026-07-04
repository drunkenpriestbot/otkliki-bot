"""
Gate 0b: раскрывает дерево рубрик в сайдбаре /projects (Аудио, видео,
съемка -> Видеосъемка и монтаж / Видеоролики / ИИ-генерация видео),
кликает по трём целевым чекбоксам (Монтаж и обработка видео, Анимационный
ролик, ИИ-генерация видео) и логирует ВСЕ сетевые запросы страницы —
это SPA, фильтр может применяться через AJAX без смены page.url, так что
единственный надёжный способ узнать реальный формат запроса — перехватить
его напрямую.

Не часть production-пайплайна. Разовый диагностический скрипт.
"""

import sys

from playwright.sync_api import sync_playwright

URL = "https://kwork.ru/projects"

RUBRIC_LABEL = "Аудио, видео, съемка"
GROUP_LABELS = ["Видеосъемка и монтаж", "Видеоролики"]
TARGET_LABELS = [
    "Монтаж и обработка видео",
    "Анимационный ролик",
    "ИИ-генерация видео",
]


def try_click(page, label, log):
    try:
        locator = page.get_by_text(label, exact=True).first
        locator.scroll_into_view_if_needed(timeout=5000)
        locator.click(timeout=5000)
        log.append(f"clicked: {label}")
        page.wait_for_timeout(1200)
        return True
    except Exception as e:
        log.append(f"FAILED to click '{label}': {e}")
        return False


def main() -> int:
    requests_log = []
    click_log = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )

        def on_request(req):
            if req.resource_type in ("xhr", "fetch"):
                requests_log.append(f"{req.method} {req.url}")

        page.on("request", on_request)

        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        for text in ["Окей!", "Принять", "Ok"]:
            try:
                page.get_by_text(text, exact=True).click(timeout=2000)
                break
            except Exception:
                pass

        # раскрыть дерево: сначала верхний рубрикатор, потом группы
        try_click(page, RUBRIC_LABEL, click_log)
        for group in GROUP_LABELS:
            try_click(page, group, click_log)

        # снимок раскрытого дерева до кликов по целевым чекбоксам —
        # на случай если сами клики по TARGET_LABELS не сработают
        page.screenshot(path="filter_expanded.png", full_page=True)

        for label in TARGET_LABELS:
            try_click(page, label, click_log)

        page.wait_for_timeout(2500)
        final_url = page.url
        html = page.content()
        page.screenshot(path="filter_result.png", full_page=True)
        with open("filter_result.html", "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()

    print("Click log:")
    for line in click_log:
        print(f"  {line}")
    print(f"Final URL after filters applied: {final_url}")
    print("XHR/fetch requests observed:")
    for line in requests_log:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
