"""
Запускается GitHub Actions по нажатию кнопки "Сгенерировать отклик" (через
Cloudflare Worker -> workflow_dispatch с inputs.action=generate). Берёт ОДНОГО
кандидата из pending.json по id, прогоняет через draft.py (Claude) и, если
релевантно, шлёт полную карточку с черновиком через notify.py. В любом случае
убирает кандидата из pending.json — повторное нажатие той же кнопки не имеет
смысла (кнопки в самом сообщении уже снесены воркером сразу при нажатии).
"""
import json
import sys
from pathlib import Path

import draft
import notify

PENDING_FILE = Path(__file__).parent / "pending.json"


def main(candidate_id: str) -> None:
    pending = json.loads(PENDING_FILE.read_text(encoding="utf-8")) if PENDING_FILE.exists() else {}
    card = pending.pop(candidate_id, None)
    PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")

    if card is None:
        print(f"candidate_id {candidate_id} не найден в pending.json", file=sys.stderr)
        return

    drafted = draft.run([card])
    if drafted:
        notify.run(drafted)
    else:
        print(f"Claude посчитал {candidate_id} нерелевантным при генерации отклика", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
