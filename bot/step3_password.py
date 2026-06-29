"""
Шаг 3 (только если включена двухфакторная аутентификация). Завершает вход
облачным паролем после того, как код подтверждён в step2_sign_in.py.

Запуск: python step3_password.py <пароль>
"""
import json
import sys
from pathlib import Path

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

STATE_FILE = Path(__file__).parent / "login_state.json"

if len(sys.argv) < 2:
    raise SystemExit("Использование: python step3_password.py <пароль>")

password = sys.argv[1]
state = json.loads(STATE_FILE.read_text())

env = {}
for line in (Path(__file__).parent / ".env.local").read_text().splitlines():
    if "=" in line and line.strip():
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

client = TelegramClient(
    StringSession(state["session"]),
    int(env["TELEGRAM_API_ID"]),
    env["TELEGRAM_API_HASH"],
    device_model="Desktop",
    system_version="Windows 11",
    app_version="5.2.3 x64",
    lang_code="ru",
    system_lang_code="ru",
)
client.connect()
client.sign_in(password=password)

session_string = client.session.save()
print("\n=== TELEGRAM_SESSION (сохрани как секрет, никому не показывай) ===\n")
print(session_string)
client.disconnect()
