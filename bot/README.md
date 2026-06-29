# otkliki-monitor (Telegram-версия)

См. главный README на уровень выше (в корне переданной папки) — там общая
архитектура, что нужно адаптировать и список секретов. Этот файл — только
про локальный тестовый запуск.

## Локальный запуск (для проверки перед деплоем в GitHub Actions)
```
pip install -r requirements.txt
export TELEGRAM_API_ID=...
export TELEGRAM_API_HASH=...
export TELEGRAM_SESSION=...        # см. комментарий в monitor_telegram.py
export GROQ_API_KEY=...
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
python monitor_telegram.py > candidates.json
python classify.py < candidates.json > classified.json
python draft.py < classified.json > drafted.json   # требует установленного claude CLI + claude setup-token
python notify.py < drafted.json
```

## Секреты репозитория (Settings → Secrets and variables → Actions)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — бот-уведомитель
- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION` — Telethon-доступ
  для чтения каналов с заказами
- `CLAUDE_CODE_OAUTH_TOKEN` — `claude setup-token` локально
- `GROQ_API_KEY` — console.groq.com, бесплатно
