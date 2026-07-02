"""
Бесплатный смысловой фильтр кандидатов от monitor_telegram.py через Groq API
(бесплатный тариф, без карты, ~1000 запросов/день). Понимает смысл, а не буквы —
переживает любые опечатки/жаргон/перефразировки заказчика без ручного словаря
синонимов. Только то, что Groq сочтёт релевантным, идёт дальше на Claude
(draft.py) для финальной проверки и написания черновика.

ВАЖНО: PROMPT_TEMPLATE ниже — placeholder. Замени описание того, что считается
релевантным заказом, под свою нишу (см. комментарий внутри).
"""
import json
import os
import sys
import time

import requests

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

PROMPT_TEMPLATE = """Сообщение из Telegram-канала/чата фрилансеров-монтажёров:
Заголовок: {title}
Описание: {description}

Вопрос: это РЕАЛЬНАЯ вакансия/заказ на монтаж видео (Reels/Shorts/TikTok,
говорящая голова, сторителлинг, моушн-графика, нарезка вебинаров и т.п.),
адресованная фрилансеру-монтажёру, который может на неё откликнуться?

ОТНОСИТСЯ, если: есть описание задачи/проекта + явный призыв откликнуться
исполнителю (например "ищем монтажера", "пишите в ЛС", "@username", контакт
для отклика), даже без точной суммы оплаты.

НЕ ОТНОСИТСЯ:
- Обычная переписка/болтовня в чате, не являющаяся постом с вакансией (вопрос
  "кто возьмёт ролик?", обсуждение, жалобы, нерелевантный оффтоп).
- Сообщение от лица САМОГО монтажёра, который ищет заказ себе (а не нанимает
  кого-то) — например "ищу проект", "посоветуйте у кого заказать".
- Вакансии не на монтаж видео (дизайн, копирайтинг, SMM, разработка и т.п.).

Ответь СТРОГО одним словом: YES или NO."""


GROQ_MAX_RETRIES = 3
# Retry-After у Groq бывает и "подождите пару секунд" (RPM-лимит), и "подождите
# 4m40s" (дневная квота токенов исчерпана, TPD) — во втором случае это не
# временный затык, а фактический стоп на сегодня. Спать несколько минут на
# КАЖДОГО кандидата нельзя — весь job зависает (живой инцидент 02.07, 10:50).
# Ждём максимум это значение, иначе сразу считаем недоступным.
MAX_RETRY_SLEEP = 10


def ask_groq(prompt: str) -> str:
    for attempt in range(GROQ_MAX_RETRIES):
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 5,
            },
            timeout=30,
        )
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 3))
            if retry_after <= MAX_RETRY_SLEEP and attempt < GROQ_MAX_RETRIES - 1:
                time.sleep(retry_after)
                continue
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip().upper()
    resp.raise_for_status()


def run(candidates: list[dict]) -> list[dict]:
    relevant = []
    for card in candidates:
        prompt = PROMPT_TEMPLATE.format(
            title=card["title"], description=card["description"]
        )
        try:
            answer = ask_groq(prompt)
        except Exception as e:
            # Раньше при отказе Groq кандидат пропускался как "на всякий случай
            # релевантный", чтобы не терять заказ молча. На практике это привело
            # к обратному: пока дневная квота Groq на исходе (частые 429),
            # именно этот фолбэк пропускал спам/несвязанные посты без всякой
            # проверки контента (живой инцидент 02.07 — юзер получил чистый
            # спам вместо вакансий по монтажу). Лучше изредка молча пропустить
            # реальный заказ при сбое Groq, чем систематически заливать спамом.
            print(f"Groq недоступен для {card['id']}: {e}, пропускаю кандидата", file=sys.stderr)
            continue

        if answer.startswith("YES"):
            relevant.append(card)
    return relevant


if __name__ == "__main__":
    candidates = json.load(sys.stdin)
    result = run(candidates)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
