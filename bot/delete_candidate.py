"""
Запускается GitHub Actions по нажатию кнопки "Удалить" (через Cloudflare
Worker -> workflow_dispatch с inputs.action=delete). Просто убирает кандидата
из pending.json — сама кнопка и карточка в Telegram уже свёрнуты воркером
сразу при нажатии, без ожидания этого запуска.
"""
import json
import sys
from pathlib import Path

PENDING_FILE = Path(__file__).parent / "pending.json"


def main(candidate_id: str) -> None:
    pending = json.loads(PENDING_FILE.read_text(encoding="utf-8")) if PENDING_FILE.exists() else {}
    pending.pop(candidate_id, None)
    PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
