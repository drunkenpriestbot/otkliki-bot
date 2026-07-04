"""
Источник заказов с биржи Kwork (проекты в нише монтажа видео/Reels/Shorts),
параллельный monitor_telegram.py — тот же формат карточек, дальше идёт в тот
же classify.py -> draft.py -> notify.py.

Анонимный доступ (без логина) — по результатам gate 0/0c (сессия 023,
04.07): Kwork отдаёт /projects анонимному запросу с IP GitHub Actions runner
без капчи, а query-параметр ?keyword=... фильтрует результаты на сервере.
Логин сознательно не используется — риск бана аккаунта (сессия, стучащая из
датацентра) дороже, чем риск временной блокировки анонимного IP, который
чинится сам собой (см. вердикт совета в сессии 023).
"""
import json
import sys
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

SEEN_FILE = Path(__file__).parent / "seen_kwork.json"
BASE_URL = "https://kwork.ru/projects"

# Несколько формулировок одной и той же ниши — Kwork ищет по точному
# вхождению слова, не по смыслу (в отличие от classify.py ниже по пайплайну),
# поэтому один запрос "монтаж" не поймает заказы, где заказчик написал только
# "видеоредактор" или "шортс".
KEYWORDS = ["монтаж видео", "видеомонтаж", "видеоредактор", "шортс", "рилс"]

PAGE_TIMEOUT_MS = 30000
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Полное описание заказа спрятано в скрытом div (Kwork рендерит и куцую, и
# полную версию сразу в DOM, переключая видимость по клику "Показать
# полностью") — достаём полную версию напрямую, не куцую, которую увидел бы
# читающий страницу глазами.
EXTRACT_CARDS_JS = """
els => els.map(el => {
    const linkEl = el.querySelector('.wants-card__header-title a');
    if (!linkEl) return null;
    const href = linkEl.getAttribute('href') || '';
    const idMatch = href.match(/\\/projects\\/(\\d+)/);
    if (!idMatch) return null;

    let description = '';
    const descBlocks = el.querySelectorAll('.wants-card__description-text > div');
    for (const block of descBlocks) {
        if ((block.getAttribute('style') || '').includes('display: none')) {
            const inline = block.querySelector('.d-inline');
            if (inline) description = inline.textContent.trim();
        }
    }
    if (!description && descBlocks.length) {
        const inline = descBlocks[0].querySelector('.d-inline');
        if (inline) description = inline.textContent.trim();
    }

    const priceEl = el.querySelector('.wants-card__header-right-block, .wants-card__price');
    const budget = priceEl ? priceEl.textContent.replace(/\\s+/g, ' ').trim() : '';

    return {
        id: idMatch[1],
        title: linkEl.textContent.trim(),
        description,
        budget,
        url: 'https://kwork.ru' + href,
    };
}).filter(Boolean)
"""


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2))


def fetch_keyword(page, keyword: str) -> list[dict]:
    url = f"{BASE_URL}?keyword={urllib.parse.quote(keyword)}"
    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    page.wait_for_timeout(2000)
    return page.eval_on_selector_all(".want-card", EXTRACT_CARDS_JS)


def run() -> list[dict]:
    seen = load_seen()
    new_cards = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)

        for keyword in KEYWORDS:
            try:
                cards = fetch_keyword(page, keyword)
            except Exception as e:
                print(f"Ключевое слово '{keyword}' не удалось загрузить: {e}", file=sys.stderr)
                continue

            for card in cards:
                key = f"kwork:{card['id']}"
                if key in seen:
                    continue
                seen.add(key)
                new_cards.append(
                    {
                        "id": key,
                        "title": card["title"],
                        "description": card["description"],
                        "budget": card["budget"],
                        "max_budget": "",
                        "url": card["url"],
                        "source": "Kwork",
                    }
                )
            # Сохраняем после каждого ключевого слова — по аналогии с
            # monitor_telegram.py: если следующий запрос зависнет/упадёт,
            # уже обработанные результаты не будут пере-опрошены заново.
            save_seen(seen)

        browser.close()

    return new_cards


if __name__ == "__main__":
    result = run()
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
