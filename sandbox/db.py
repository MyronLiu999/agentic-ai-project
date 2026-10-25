"""The sandbox's SQLite file: schema and connection. Every module in sandbox/ goes through here.

Everything is synthetic: IDs carry the SYN- prefix, and `margins` is private data that must never
reach a distributor (it has its own module, sandbox/margins.py, which no agent tool imports).
Every write carries a `stamp`: the run's ID, the console session's, or "manual" (sandbox/stamp.py).
"""

from __future__ import annotations

import contextlib
import sqlite3

from harness.paths import state_dir

NOW = "2026-10-05"   # the seed fixes "now", so every run repeats; tools read it from here, never the clock

SCHEMA = """
CREATE TABLE IF NOT EXISTS distributors (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, region TEXT NOT NULL, contact_email TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products (sku TEXT PRIMARY KEY, name TEXT NOT NULL, list_price REAL NOT NULL);
CREATE TABLE IF NOT EXISTS margins (sku TEXT PRIMARY KEY, unit_cost REAL NOT NULL, margin_pct REAL NOT NULL);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, distributor_id TEXT NOT NULL, sku TEXT NOT NULL,
    qty INTEGER NOT NULL, unit_price REAL NOT NULL, order_date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, distributor_id TEXT NOT NULL, contact_email TEXT NOT NULL,
    question TEXT NOT NULL, file_name TEXT, period TEXT, status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL, stamp TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL, kind TEXT NOT NULL, version INTEGER NOT NULL,
    key TEXT NOT NULL UNIQUE, figures_json TEXT NOT NULL, body TEXT NOT NULL, stamp TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, request_id TEXT NOT NULL, thread_id TEXT NOT NULL,
    recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL, report_id INTEGER,
    key TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'pending', stamp TEXT NOT NULL, created_at TEXT NOT NULL);
"""

FILENAME = "sales.sqlite3"


def path():
    return state_dir() / FILENAME


@contextlib.contextmanager
def connect():
    """A connection that creates the schema if needed, commits on success and always closes."""
    conn = sqlite3.connect(path(), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        with conn:
            yield conn
    finally:
        conn.close()


def reset() -> None:
    p = path()
    if p.exists():
        p.unlink()
    uploads = state_dir() / "uploads"
    if uploads.exists():
        for f in sorted(uploads.rglob("*"), reverse=True):
            f.unlink() if f.is_file() else f.rmdir()
        uploads.rmdir()
