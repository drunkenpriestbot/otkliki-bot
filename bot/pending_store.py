"""
Хранилище кандидатов на карточки в Telegram — один файл на кандидата
(pending/<id>.json) вместо единого pending.json.

Раньше несколько параллельных прогонов GitHub Actions (крон раз в 10 минут +
клики кнопок "Сгенерировать"/"Удалить") писали в один общий pending.json.
При почти одновременных запусках `git pull --no-rebase -X ours` на конфликте
брал версию текущего рана целиком — и тихо терял кандидатов, добавленных
другим параллельным раном, включая тех, чьи карточки с кнопками уже были
отправлены в Telegram. Итог: нажатие рабочей кнопки — "candidate_id не найден"
без вообще какой-либо обратной связи.

С отдельным файлом на кандидата разные раны пишут в разные файлы — git не
видит конфликта между ними в принципе, потому что конфликтовать нечему.
"""
import json
from pathlib import Path

PENDING_DIR = Path(__file__).parent / "pending"


def _safe_name(candidate_id: str) -> str:
    return candidate_id.replace(":", "__").replace("/", "_") + ".json"


def path_for(candidate_id: str) -> Path:
    return PENDING_DIR / _safe_name(candidate_id)


def exists(candidate_id: str) -> bool:
    return path_for(candidate_id).exists()


def save(card: dict) -> None:
    PENDING_DIR.mkdir(exist_ok=True)
    path_for(card["id"]).write_text(
        json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load(candidate_id: str) -> dict | None:
    p = path_for(candidate_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def delete(candidate_id: str) -> None:
    p = path_for(candidate_id)
    if p.exists():
        p.unlink()


def load_all() -> dict[str, dict]:
    if not PENDING_DIR.exists():
        return {}
    result = {}
    for f in PENDING_DIR.glob("*.json"):
        card = json.loads(f.read_text(encoding="utf-8"))
        result[card["id"]] = card
    return result
