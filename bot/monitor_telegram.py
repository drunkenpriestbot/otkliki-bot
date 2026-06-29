"""
СКЕЛЕТ, НЕ ПРОВЕРЕННЫЙ ЖИВОЙ КОД (в отличие от classify.py/draft.py/notify.py,
которые рабочий код из реального проекта). В оригинале источником заказов была
веб-страница биржи (Playwright-парсинг DOM), что не переносится на Telegram —
здесь нужен другой способ читать сообщения.

Используется Telethon (MTProto-клиент от имени пользователя) — единственный
способ читать ЛЮБОЙ публичный канал, на который подписан аккаунт, без того,
чтобы добавлять туда бота. Если твои каналы с заказами разрешают добавление
ботов — можно вместо этого использовать Bot API (`getUpdates`/webhook), это
проще, но работает только в каналах, куда бот добавлен админом.

Подготовка (один раз, локально, НЕ в CI):
1. Получи api_id и api_hash на https://my.telegram.org (нужен номер телефона).
2. Установи зависимость: pip install telethon
3. Первый запуск интерактивный (попросит код из Telegram) — после него
   Telethon сохранит сессию. Сохрани строку сессии (StringSession) и положи
   её в секрет TELEGRAM_SESSION — дальше CI будет логиниться без интерактива.
4. В список CHANNELS впиши username/ссылки каналов с заказами, на которые
   подписан твой аккаунт.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import InputPeerChannel

SEEN_FILE = Path(__file__).parent / "seen.json"

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["TELEGRAM_SESSION"]

# Приватный канал (без username) — добавлен по InputPeerChannel(id, access_hash)
# после join_private.py (ImportChatInviteRequest по invite-ссылке
# +qoxNFMOfVbVkYzY6). Бэрый int не резолвится в отдельном процессе/сессии без
# кэша сущностей — нужен явный access_hash.
PRIVATE_CHAT_ID = 1406991134
PRIVATE_CHAT = InputPeerChannel(PRIVATE_CHAT_ID, -7797340264784814279)

CHANNELS = [
    "frilanse",
    "poiskfreelance",
    "theClapperChat",
    "jetlagchat",
    "KinoMastery",
    "mari_vakansii",
    "textodromo",
    "GetJob_videoedit",
    PRIVATE_CHAT,
    "cam_mtg",
    "vakansii_reelsmaker",
    "SearchEditorr",
    "reelsmaker_tinder",
    "prodjob",
    "ru_montage_pins",
]

# Сколько последних сообщений проверять за один прогон в каждом канале —
# достаточно для интервала между запусками, не вытаскивать всю историю.
MESSAGES_PER_CHANNEL = 30


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2))


async def fetch_new(client: TelegramClient, seen: set[str]) -> list[dict]:
    new_cards = []
    for channel in CHANNELS:
        channel_key = channel.channel_id if isinstance(channel, InputPeerChannel) else channel
        async for message in client.iter_messages(channel, limit=MESSAGES_PER_CHANNEL):
            if not message.text:
                continue
            msg_key = f"{channel_key}:{message.id}"
            if msg_key in seen:
                continue
            seen.add(msg_key)

            # Заказы в каналах обычно идут одним сплошным текстом без чёткой
            # структуры заголовок/описание/бюджет — в отличие от карточек на
            # бирже. Здесь просто используем первую строку как условный
            # "заголовок", остальное как описание. Бюджет, если упоминается
            # в тексте, classify.py/draft.py всё равно увидят в description —
            # отдельно парсить не обязательно, если на бирже не было строгого
            # поля "бюджет".
            lines = message.text.strip().split("\n")
            title = lines[0][:120]
            description = message.text.strip()

            # Приватный чат (channel — число, не username) не имеет публичной
            # t.me/username ссылки — используем формат t.me/c/<id>/<msg_id>,
            # он открывает сообщение внутри приложения для тех, кто уже состоит
            # в чате (наш аккаунт состоит, см. join_private.py).
            if isinstance(channel, InputPeerChannel):
                url = f"https://t.me/c/{channel.channel_id}/{message.id}"
            else:
                url = f"https://t.me/{channel}/{message.id}"

            new_cards.append(
                {
                    "id": msg_key,
                    "title": title,
                    "description": description,
                    "budget": "",
                    "max_budget": "",
                    "url": url,
                }
            )
    return new_cards


async def run() -> list[dict]:
    seen = load_seen()
    async with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as client:
        new_cards = await fetch_new(client, seen)
    save_seen(seen)
    return new_cards


if __name__ == "__main__":
    result = asyncio.run(run())
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
