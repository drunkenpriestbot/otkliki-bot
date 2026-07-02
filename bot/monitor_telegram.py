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

# Один зависший/флуд-заблокированный канал не должен убивать весь прогон до
# жёсткого лимита job (10 мин в monitor.yml, живой инцидент 02.07 — job молча
# завис на fetch_new и был убит таймаутом, ничего не сохранив и не отправив).
CHANNEL_TIMEOUT = 30

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
    # frilanse и poiskfreelance убраны 02.07 — общие свалки для шабашки/
    # микрозаймов/сетевых разводов, к монтажу видео отношения не имеют, только
    # шумели спамом мимо классификатора.
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


async def fetch_channel(client: TelegramClient, channel, seen: set[str]) -> list[dict]:
    channel_key = channel.channel_id if isinstance(channel, InputPeerChannel) else channel
    new_cards = []
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


async def fetch_new(client: TelegramClient, seen: set[str]) -> list[dict]:
    new_cards = []
    for channel in CHANNELS:
        channel_key = channel.channel_id if isinstance(channel, InputPeerChannel) else channel
        try:
            new_cards.extend(
                await asyncio.wait_for(fetch_channel(client, channel, seen), timeout=CHANNEL_TIMEOUT)
            )
        except asyncio.TimeoutError:
            print(f"Канал {channel_key} завис (>{CHANNEL_TIMEOUT}s), пропускаю", file=sys.stderr)
        # Сохраняем seen после каждого канала — если следующий канал зависнет
        # или упадёт, уже обработанные каналы не будут пере-опрошены заново.
        save_seen(seen)
    return new_cards


CONNECT_TIMEOUT = 30


async def run() -> list[dict]:
    seen = load_seen()
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    # client.connect() (внутри __aenter__) ничем не таймаутится сам по себе —
    # если сеть до Telegram зависнет на уровне TCP/MTProto-хендшейка, весь job
    # молча висит до жёсткого лимита GitHub Actions (живой инцидент 02.07,
    # 10+ минут без единого байта вывода, ДО того как дело доходит до самих
    # каналов). Оборачиваем явным таймаутом, а не полагаемся на per-channel.
    await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
    try:
        new_cards = await fetch_new(client, seen)
    finally:
        await client.disconnect()
    return new_cards


if __name__ == "__main__":
    try:
        result = asyncio.run(run())
    except asyncio.TimeoutError:
        print("Не удалось подключиться к Telegram за отведённое время", file=sys.stderr)
        result = []
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
