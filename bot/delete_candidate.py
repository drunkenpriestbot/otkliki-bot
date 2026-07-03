"""
Запускается GitHub Actions по нажатию кнопки "Удалить" (через Cloudflare
Worker -> workflow_dispatch с inputs.action=delete). Просто убирает кандидата
из pending/ — сама кнопка и карточка в Telegram уже свёрнуты воркером сразу
при нажатии, без ожидания этого запуска.
"""
import sys

import pending_store


def main(candidate_id: str) -> None:
    pending_store.delete(candidate_id)


if __name__ == "__main__":
    main(sys.argv[1])
