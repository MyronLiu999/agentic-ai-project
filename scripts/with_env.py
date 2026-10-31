"""Run project Python commands with OPENAI_API_KEY from the ignored local .env.

    python scripts/with_env.py --check
    python scripts/with_env.py -m harness.ping
    python scripts/with_env.py run.py --tasks tasks/ --sweeps 1 --arm dev-myron

Only OPENAI_API_KEY is read. A single unquoted or matching-quoted value is
supported; the file is data and is never executed as shell or Python code.
The local key takes precedence over a stale inherited environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def read_key(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        raise ValueError("Create .env in the project root and set OPENAI_API_KEY.") from None
    values = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if separator and name.strip() == "OPENAI_API_KEY":
            value = value.strip()
            if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
                value = value[1:-1]
            values.append(value)
    if len(values) != 1:
        raise ValueError(".env must contain exactly one OPENAI_API_KEY=value entry.")
    key = values[0]
    if (not key.startswith("sk-") or len(key) < 20
            or any(not 33 <= ord(character) <= 126 for character in key)):
        raise ValueError("Set the full original OpenAI key in .env; it must start with sk- and contain no spaces or masked characters.")
    return key


def main() -> int:
    arguments = sys.argv[1:]
    if not arguments:
        print("Usage: python scripts/with_env.py --check | -m harness.ping | run.py ...", file=sys.stderr)
        return 2
    try:
        key = read_key(ROOT / ".env")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if arguments == ["--check"]:
        print("Local .env key format is valid. No API request was made.")
        return 0
    environment = os.environ.copy()
    environment["OPENAI_API_KEY"] = key
    environment["PYTHONUTF8"] = "1"
    return subprocess.run([sys.executable, *arguments], cwd=ROOT, env=environment).returncode


if __name__ == "__main__":
    sys.exit(main())
