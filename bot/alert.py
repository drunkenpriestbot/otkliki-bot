"""
Короткие служебные уведомления в Telegram (не карточки кандидатов) — для
сообщений о деградации/ошибках, которые должен увидеть человек, а не тихий
лог GitHub Actions, который никто не читает без повода.
"""
import os

import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"


def send(text: str) -> None:
    requests.post(API_URL, json={"chat_id": CHAT_ID, "text": text}, timeout=20).raise_for_status()
