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

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"


def _load_groq_keys() -> list[str]:
    # Несколько бесплатных аккаунтов Groq — у каждого своя дневная TPD-квота
    # (100k токенов), которую при 13 каналах раз в 15 минут регулярно не
    # хватает на один аккаунт. GROQ_API_KEY — основной, GROQ_API_KEY_2..9 —
    # дополнительные, ротируем по кругу при 429 (квота исчерпана) или 401
    # (ключ невалиден — например ещё не подтверждён новый аккаунт).
    # В GitHub Actions env-переменная для отсутствующего секрета придёт как
    # пустая строка (не отсутствующим ключом) — фильтруем явно. Перебираем
    # фиксированный диапазон, а не останавливаемся на первом пропуске — так
    # можно свободно убрать/добавить ключ в середине списка.
    keys = [os.environ["GROQ_API_KEY"]]
    for i in range(2, 20):
        key = os.environ.get(f"GROQ_API_KEY_{i}")
        if key:
            keys.append(key)
    return keys


GROQ_KEYS = _load_groq_keys()
_current_key_idx = 0

CACHE_FILE = Path(__file__).parent / "classify_cache.json"
UNCLASSIFIED_FILE = Path(__file__).parent / "unclassified.json"

# Двухсторонний keyword-фильтр ДО вызова Groq — по аналогии с поиском в
# App Store/Google Play: явный мусор отсекается по чёрному списку, а то, что
# осталось, обязано содержать И тематику (монтаж видео), И сигнал найма —
# иначе Groq вообще не вызывается. Живой инцидент 03.07: дневная TPD-квота
# (100k токенов) стабильно упирается в потолок при обычной эксплуатации
# 13 каналов раз в 10 минут — экономить нужно объёмом запросов, не моделью
# (смена модели уже один раз ломала точность, см. ниже).

# Явные маркеры самопиара монтажёров, предлагающих СВОИ услуги — не вакансии,
# а противоположность вакансии. Живой инцидент: при смене модели на более
# дешёвую (llama-3.1-8b-instant) именно эти посты массово путались с наймом
# по ключевым словам "монтаж"/"монтажёр".
SELF_PROMO_PATTERNS = [
    re.compile(r"#помогу\b", re.IGNORECASE),
    re.compile(
        r"меня зовут .{0,40}(я (делаю|занимаюсь)|монтаж[её]р)",
        re.IGNORECASE | re.DOTALL,
    ),
]

# Другие категории явного мусора, регулярно всплывающие в тех же чатах —
# крипта/обмен валют и доход-скам ("600$ в день", "без вложений"). Ни разу
# не были реальной вакансией на монтаж видео за всё время эксплуатации.
SPAM_PATTERNS = [
    re.compile(r"\b(usdt|trc[- ]?20)\b", re.IGNORECASE),
    re.compile(r"курс\s+(обсуд\w*|договорн\w*)", re.IGNORECASE),
    re.compile(r"без\s+вложени", re.IGNORECASE),
    re.compile(
        r"(доход|заработ\w*)\s+(от|до)?\s*\d+\s*(\$|доллар|usd|рубл|₽)",
        re.IGNORECASE,
    ),
    re.compile(r"\d+\s*(\$|доллар\S*|usd)\S*\s+в\s+день", re.IGNORECASE),
]

# Обязательная тематика — должно упоминаться собственно видео/монтаж, иначе
# это не может быть вакансией на монтаж видео в принципе.
TOPIC_PATTERN = re.compile(
    r"(?i)(монт\w*|видеоредактор|видео.?эдитор|reels?|shorts?|tiktok|ролик|"
    r"видеограф|моушн|сторителлинг)"
)

# Обязательный сигнал найма — иначе это может быть болтовнёй/самопиаром,
# упомянувшим монтаж мимоходом, а не постом с вакансией.
HIRING_SIGNAL_PATTERN = re.compile(
    r"(?i)(ищ(у|ем|ется)|нужен|нужна|нужны|требуется|треб(уются)?|ваканси|"
    r"в\s+лс|пис\w*|свяж\w*|@\w+|контакт)"
)


def is_obvious_self_promo(text: str) -> bool:
    return any(p.search(text) for p in SELF_PROMO_PATTERNS)


def is_obvious_spam(text: str) -> bool:
    return any(p.search(text) for p in SPAM_PATTERNS)


def passes_prefilter(text: str, source: str = "") -> bool:
    if is_obvious_spam(text):
        return False
    if not TOPIC_PATTERN.search(text):
        return False

    # На Kwork /projects — по определению уже заказ покупателя, а не
    # переписка/самопиар монтажёра, как в шумных Telegram-каналах. Требовать
    # тут слова вроде "ищу"/"нужен"/"в лс" неверно: заказчик обычно пишет
    # задачу императивом ("Смонтировать ролик 45-75 сек"), без них — и такие
    # карточки тихо терялись ДО Groq, без единого сигнала об этом.
    if source == "Kwork":
        return True

    if is_obvious_self_promo(text):
        return False
    if not HIRING_SIGNAL_PATTERN.search(text):
        return False
    return True


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

PROMPT_TEMPLATE = """Пост/заказ с биржи фриланса или из Telegram-канала/чата монтажёров:
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
    global _current_key_idx
    last_resp = None

    # Перебираем ключи по кругу максимум по одному разу каждый за вызов —
    # если ключ невалиден (401, например неподтверждённый аккаунт) или у
    # него исчерпана дневная квота (429 с большим Retry-After), сразу
    # переходим к следующему, не тратя циклы retry на заведомо мёртвый ключ.
    for _ in range(len(GROQ_KEYS)):
        key = GROQ_KEYS[_current_key_idx]

        for attempt in range(GROQ_MAX_RETRIES):
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 5,
                },
                timeout=30,
            )
            if resp.status_code == 401:
                break  # невалидный ключ — сразу к следующему
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 3))
                if retry_after <= MAX_RETRY_SLEEP and attempt < GROQ_MAX_RETRIES - 1:
                    time.sleep(retry_after)
                    continue
                break  # дневная квота этого ключа исчерпана — к следующему
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip().upper()

        last_resp = resp
        _current_key_idx = (_current_key_idx + 1) % len(GROQ_KEYS)

    last_resp.raise_for_status()


def run(candidates: list[dict]) -> list[dict]:
    relevant = []
    cache = load_cache()
    degraded = []

    for card in candidates:
        text = f"{card['title']}\n{card['description']}"

        if not passes_prefilter(text, card.get("source", "")):
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
