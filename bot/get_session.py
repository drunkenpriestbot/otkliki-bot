"""
Запустить ОДИН РАЗ локально, чтобы получить TELEGRAM_SESSION (StringSession).
Не запускать в GitHub Actions — это интерактивный шаг.

Перед запуском впиши свои API_ID/API_HASH ниже (с my.telegram.org) или передай
через переменные окружения TELEGRAM_API_ID/TELEGRAM_API_HASH.

Запуск: python get_session.py
Спросит номер телефона, потом код из Telegram (и пароль 2FA, если включён).
В конце выведет строку сессии — её нужно сохранить как секрет TELEGRAM_SESSION
и больше никому не показывать (это полный доступ к аккаунту).
"""
import os

from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

if not API_ID or not API_HASH:
    raise SystemExit(
        "Впиши TELEGRAM_API_ID и TELEGRAM_API_HASH как переменные окружения "
        "или прямо в этот файл перед запуском."
    )

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    session_string = client.session.save()
    print("\n=== Сохрани эту строку как секрет TELEGRAM_SESSION ===\n")
    print(session_string)
    print("\n=== Никому не показывай, это полный доступ к аккаунту ===\n")
