"""
Лёгкое превью-уведомление для каждого кандидата, прошедшего classify.py —
БЕЗ черновика (черновик через Claude стоит вызова, поэтому генерируется
только по кнопке). Карточка содержит заголовок/описание/ссылку и две кнопки:
"Сгенерировать отклик" / "Удалить".

Полные данные кандидата сохраняются в pending.json (по id), чтобы воркер
(cloudflare-worker/webhook.js) мог дёрнуть GitHub Actions с одним только id
в callback_data — Telegram ограничивает callback_data 64 байтами, так что
сам заказ туда не поместится.
"""
import html
import json
import os
import sys
from pathlib import Path

import requests

PENDING_FILE = Path(__file__).parent / "pending.json"

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

MAX_DESCRIPTION_LEN = 2500


def load_pending() -> dict:
    if PENDING_FILE.exists():
        return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    return {}


def save_pending(pending: dict) -> None:
    PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")


def format_preview(card: dict) -> str:
    budget_line = ""
    if card.get("budget"):
        budget_line = f"💰 {html.escape(card['budget'])}\n"

    description = card.get("description", "")
    if len(description) > MAX_DESCRIPTION_LEN:
        description = description[:MAX_DESCRIPTION_LEN] + "…"
    description_block = (
        f"<blockquote expandable>{html.escape(description)}</blockquote>"
        if description
        else ""
    )

    return (
        f"🆕 {html.escape(card['title'])}\n"
        f"{budget_line}"
        f"🔗 {html.escape(card['url'])}\n\n"
        f"{description_block}"
    )


def send_preview(card: dict) -> None:
    resp = requests.post(
        API_URL,
        json={
            "chat_id": CHAT_ID,
            "text": format_preview(card),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "✍️ Сгенерировать отклик", "callback_data": f"gen:{card['id']}"},
                        {"text": "🗑 Удалить", "callback_data": f"del:{card['id']}"},
                    ]
                ]
            },
        },
        timeout=20,
    )
    resp.raise_for_status()


def run(cards: list[dict]) -> None:
    if not cards:
        return
    pending = load_pending()
    for card in cards:
        pending[card["id"]] = card
        send_preview(card)
    save_pending(pending)


if __name__ == "__main__":
    cards = json.load(sys.stdin)
    run(cards)
