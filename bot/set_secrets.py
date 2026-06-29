"""Заливает секреты из .env.local в GitHub Actions secrets (без вывода значений)."""
import subprocess
from pathlib import Path

REPO = "drunkenpriestbot/otkliki-bot"
ENV_FILE = Path(__file__).parent / ".env.local"

KEYS_TO_PUSH = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_SESSION",
    "GROQ_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
]

env = {}
for line in ENV_FILE.read_text().splitlines():
    if "=" in line and line.strip():
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

for key in KEYS_TO_PUSH:
    if key not in env:
        print(f"ПРОПУЩЕН (нет в .env.local): {key}")
        continue
    proc = subprocess.run(
        ["gh", "secret", "set", key, "--repo", REPO],
        input=env[key],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    status = "OK" if proc.returncode == 0 else f"FAIL: {proc.stderr.strip()}"
    print(f"{key}: {status}")
