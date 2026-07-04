"""
Сливает кандидатов от нескольких источников (monitor_telegram.py,
monitor_kwork.py) в один список для classify.py. Отдельный скрипт вместо
инлайн python -c в workflow — там многострочный код с отступами YAML-блока
ломается (IndentationError на верхнем уровне модуля).
"""
import json
import sys


def main(paths: list[str]) -> None:
    merged = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            merged.extend(json.load(f))
    json.dump(merged, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main(sys.argv[1:])
