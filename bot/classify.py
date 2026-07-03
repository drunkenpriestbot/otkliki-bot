"""
Бесплатный смысловой фильтр кандидатов от monitor_telegram.py через Groq API
(бесплатный тариф, без карты, ~1000 запросов/день). Понимает смысл, а не буквы —
переживает любые опечатки/жаргон/перефразировки заказчика без ручного словаря
синонимов. Только то, что Groq сочтёт релевантным, идёт дальше на Claude
(draft.py) для финальной проверки и написания черновика.

ВАЖНО: PROMPT_TEMPLATE ниже — placeholder. Замени описание того, что считается
релевантным заказом, под свою нишу (см. комментарий внутри).
"""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

CACHE_FILE = Path(__file__).parent / "classify_cache.json"
UNCLASSIFIED_FILE = Path(__file__).parent / "unclassified.json"

# Явные маркеры самопиара монтажёров, предлагающих СВОИ услуги — не вакансии,
# а противоположность вакансии. Живой инцидент: при смене модели на более
# дешёвую (llama-3.1-8b-instant) именно эти посты массово путались с наймом
# по ключевым словам "монтаж"/"монтажёр". Regex ловит только однозначные
# случаи и отсекает их ДО вызова Groq — экономит квоту без риска для
# точности на пограничных случаях (те по-прежнему идут на LLM).
SELF_PROMO_PATTERNS = [
    re.compile(r"#помогу\b", re.IGNORECASE),
    re.compile(
        r"меня зовут .{0,40}(я (делаю|занимаюсь)|монтаж[её]р)",
        re.IGNORECASE | re.DOTALL,
    ),
]


def is_obvious_self_promo(text: str) -> bool:
    return any(p.search(text) for p in SELF_PROMO_PATTERNS)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

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
    cache = load_cache()
    degraded = []

    for card in candidates:
        text = f"{card['title']}\n{card['description']}"

        if is_obvious_self_promo(text):
            continue

        h = text_hash(text)
        if h in cache:
            if cache[h] == "YES":
                relevant.append(card)
            continue

        prompt = PROMPT_TEMPLATE.format(
            title=card["title"], description=card["description"]
        )
        try:
            answer = ask_groq(prompt)
        except Exception as e:
            # Раньше отказ Groq либо тихо ронял кандидата (fail-closed), либо
            # тихо считал его релевантным (старый fail-open) — оба варианта
            # без единого сигнала пользователю о деградации. Теперь сохраняем
            # сырой пост на ручной разбор и явно уведомляем в конце прогона
            # одним сообщением (не спамим по кандидату).
            print(f"Groq недоступен для {card['id']}: {e}, сохраняю на ручной разбор", file=sys.stderr)
            degraded.append(card)
            continue

        cache[h] = "YES" if answer.startswith("YES") else "NO"
        if answer.startswith("YES"):
            relevant.append(card)

    save_cache(cache)

    if degraded:
        existing = json.loads(UNCLASSIFIED_FILE.read_text(encoding="utf-8")) if UNCLASSIFIED_FILE.exists() else []
        existing.extend(degraded)
        UNCLASSIFIED_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            import alert
            alert.send(
                f"⚠️ Groq недоступен — {len(degraded)} кандидатов не проверено, "
                f"сохранены в unclassified.json для ручного разбора."
            )
        except Exception as e:
            print(f"Не удалось отправить алерт о деградации: {e}", file=sys.stderr)

    return relevant


if __name__ == "__main__":
    candidates = json.load(sys.stdin)
    result = run(candidates)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
