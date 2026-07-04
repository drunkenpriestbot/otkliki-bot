"""
Отправляет в Telegram уведомления о новых релевантных заказах с готовым черновиком
отклика. Сам не отправляет ничего на бирже/в чат с заказом — только уведомляет,
отклик отправляет человек вручную (см. LESSONS_LEARNED.md, пункт 1 — почему).

Черновик оформлен как code-block (тап = копирование целиком, без лимита в 256
символов, который есть у кнопки copy_text). Кнопка "Перейти к заказу" открывает
исходное сообщение/страницу заказа. Если человек хочет поправить текст — копирует
блок, редактирует и отправляет Reply на это же сообщение бота; отдельный
Cloudflare Worker-вебхук (cloudflare-worker/webhook.js) подхватывает Reply,
достаёт ссылку на заказ из текста исходного сообщения и прикрепляет такую же
кнопку к отредактированному сообщению.
"""
import html
import json
import os
import re
import sys

import requests

# Черновик от draft.py содержит ссылки на портфолио в виде markdown
# [Работа N](URL) (см. WRITING_RULES в draft.py — голые URL отпугивают
# клиентов). html.escape не трогает [ ] ( ), так что разметка переживает
# экранирование текста — после escape конвертируем её в реальные <a> теги.
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def render_draft_html(draft: str) -> str:
    escaped = html.escape(draft)
    return MD_LINK_RE.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', escaped)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"


def send_message(text: str, url: str) -> None:
    resp = requests.post(
        API_URL,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": {
                "inline_keyboard": [[{"text": "🔗 Перейти к заказу", "url": url}]]
            },
        },
        timeout=20,
    )
    resp.raise_for_status()


MAX_DESCRIPTION_LEN = 2500


def format_card(card: dict) -> str:
    draft_html = render_draft_html(card["draft"])
    budget_line = ""
    if card.get("budget"):
        budget_line = f"💰 {html.escape(card['budget'])}\n"
    max_budget = card.get("max_budget")
    if max_budget:
        budget_line += f"💸 {html.escape(max_budget)}\n"

    description = card.get("description", "")
    if len(description) > MAX_DESCRIPTION_LEN:
        description = description[:MAX_DESCRIPTION_LEN] + "…"
    description_block = (
        f"<blockquote expandable>{html.escape(description)}</blockquote>\n\n"
        if description
        else ""
    )

    source_line = f"📍 {html.escape(card['source'])}\n" if card.get("source") else ""

    return (
        f"🆕 {html.escape(card['title'])}\n"
        f"{source_line}"
        f"{budget_line}"
        f"🔗 {html.escape(card['url'])}\n\n"
        f"{description_block}"
        f"Черновик отклика:\n"
        f"<blockquote>{draft_html}</blockquote>"
    )


def run(cards: list[dict]) -> None:
    if not cards:
        return
    for card in cards:
        send_message(format_card(card), card["url"])


if __name__ == "__main__":
    cards = json.load(sys.stdin)
    run(cards)
