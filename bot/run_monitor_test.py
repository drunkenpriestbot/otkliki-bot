"""Разовый тест monitor_telegram.py с env из .env.local (Фаза 1)."""
import os
import subprocess
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env.local"
env = os.environ.copy()
for line in ENV_FILE.read_text().splitlines():
    if "=" in line and line.strip():
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

result = subprocess.run(
    ["python", str(Path(__file__).parent / "monitor_telegram.py")],
    capture_output=True,
    text=True,
    encoding="utf-8",
    env=env,
    timeout=120,
)
print("STDOUT:")
print(result.stdout)
print("STDERR:")
print(result.stderr)
