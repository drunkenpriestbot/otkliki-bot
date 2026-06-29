"""
Шаг 1 из 2 для получения TELEGRAM_SESSION без интерактивного терминала.
Читает TELEGRAM_API_ID/TELEGRAM_API_HASH/TELEGRAM_PHONE из .env.local рядом,
запрашивает код подтверждения у Telegram и сохраняет промежуточное состояние
(временную сессию + phone_code_hash) в login_state.json — оно нужно шагу 2.

Запуск: python step1_send_code.py
После запуска Telegram пришлёт код на номер из .env.local — ввести его в
step2_sign_in.py.
"""
import json
from pathlib import Path

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

ENV_FILE = Path(__file__).parent / ".env.local"
STATE_FILE = Path(__file__).parent / "login_state.json"

env = {}
for line in ENV_FILE.read_text().splitlines():
    if "=" in line and line.strip():
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

API_ID = int(env["TELEGRAM_API_ID"])
API_HASH = env["TELEGRAM_API_HASH"]
PHONE = env["TELEGRAM_PHONE"]

client = TelegramClient(
    StringSession(),
    API_ID,
    API_HASH,
    device_model="Desktop",
    system_version="Windows 11",
    app_version="5.2.3 x64",
    lang_code="ru",
    system_lang_code="ru",
)
client.connect()
sent = client.send_code_request(PHONE)

STATE_FILE.write_text(
    json.dumps(
        {
            "session": client.session.save(),
            "phone_code_hash": sent.phone_code_hash,
            "phone": PHONE,
        }
    )
)
client.disconnect()
print(f"Код отправлен на {PHONE}. Способ доставки: {type(sent.type).__name__}")
print("Введи код в step2_sign_in.py")
