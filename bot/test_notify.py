"""Разовый тест реальной отправки уведомления (Фаза 1, ручная проверка)."""
import json
import os
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env.local"
for line in ENV_FILE.read_text().splitlines():
    if "=" in line and line.strip():
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

import importlib.util

spec = importlib.util.spec_from_file_location("notify", Path(__file__).parent / "notify.py")
notify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notify)

drafted = json.loads(
    (Path(os.environ["DRAFTED_JSON"])).read_text(encoding="utf-8")
)
notify.run(drafted)
print(f"Отправлено {len(drafted)} уведомлени(й).")
