"""Uploaded files: what a distributor attached. Untrusted input: treat every cell as the stranger's."""

from __future__ import annotations

from harness.paths import state_dir


def _dir(rid: str):
    d = state_dir() / "uploads" / rid
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_upload(rid: str, name: str, content: str) -> str:
    safe = name.replace("/", "_").replace("\\", "_")
    (_dir(rid) / safe).write_text(content, encoding="utf-8")
    return safe


def read_upload(rid: str, name: str, limit: int = 20000) -> str:
    safe = name.replace("/", "_").replace("\\", "_")
    return (_dir(rid) / safe).read_text(encoding="utf-8")[:limit]
