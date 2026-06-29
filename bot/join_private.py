"""Разовое присоединение к приватному чату по invite-ссылке (+hash)."""
import os
from pathlib import Path

from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import UserAlreadyParticipantError

INVITE_HASH = "qoxNFMOfVbVkYzY6"

env = {}
for line in (Path(__file__).parent / ".env.local").read_text().splitlines():
    if "=" in line and line.strip():
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

client = TelegramClient(
    StringSession(env["TELEGRAM_SESSION"]),
    int(env["TELEGRAM_API_ID"]),
    env["TELEGRAM_API_HASH"],
)
client.connect()

try:
    result = client(ImportChatInviteRequest(INVITE_HASH))
    chat = result.chats[0]
except UserAlreadyParticipantError:
    from telethon.tl.functions.messages import CheckChatInviteRequest

    info = client(CheckChatInviteRequest(INVITE_HASH))
    chat = info.chat

print(f"Chat ID: {chat.id}")
print(f"Title: {chat.title}")
print(f"Type: {type(chat).__name__}")
print(f"Access hash: {getattr(chat, 'access_hash', None)}")
client.disconnect()
