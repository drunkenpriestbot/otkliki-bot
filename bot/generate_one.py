"""
Запускается GitHub Actions по нажатию кнопки "Сгенерировать отклик" (через
Cloudflare Worker -> workflow_dispatch с inputs.action=generate). Берёт ОДНОГО
кандидата из pending/<id>.json, прогоняет через draft.py (Claude) и, если
релевантно, шлёт полную карточку с черновиком через notify.py. В любом случае
убирает кандидата из pending/ — повторное нажатие той же кнопки не имеет
смысла (кнопки в самом сообщении уже снесены воркером сразу при нажатии).
"""
import sys

import draft
import notify
import pending_store


def main(candidate_id: str) -> None:
    card = pending_store.load(candidate_id)

    if card is None:
        # Раньше здесь была тихая заглушка — с точки зрения пользователя
        # кнопка выглядела просто сломанной, никакой обратной связи не было.
        # Теперь явно сообщаем в Telegram, чтобы не гадать.
        print(f"candidate_id {candidate_id} не найден в pending/", file=sys.stderr)
        import alert
        alert.send(
            f"⚠️ Кандидат {candidate_id} не найден — карточка устарела или "
            f"уже обработана. Если это ошибка, напишите вручную."
        )
        return

    pending_store.delete(candidate_id)

    drafted = draft.run([card])
    if drafted:
        notify.run(drafted)
    else:
        print(f"Claude посчитал {candidate_id} нерелевантным при генерации отклика", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
