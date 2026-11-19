"""SQLite database for call logging and tracking."""

import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "calls.sqlite"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    listing_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    address TEXT,
                    txid TEXT,
                    amount INTEGER DEFAULT 0,
                    asset TEXT DEFAULT 'ALGO',
                    is_error INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_calls_address ON calls(address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_calls_txid ON calls(txid)")
    finally:
        conn.close()


# Ensure DB and table exist on import
init_db()


def log_call(
    listing_id: str,
    tool: str,
    address: Optional[str] = None,
    txid: Optional[str] = None,
    amount: int = 0,
    asset: str = "ALGO",
    is_error: bool = False,
    error_message: Optional[str] = None,
) -> int:
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO calls (ts, listing_id, tool, address, txid, amount, asset, is_error, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    listing_id,
                    tool,
                    address,
                    txid,
                    amount,
                    asset,
                    1 if is_error else 0,
                    error_message,
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_call_by_txid(txid: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM calls WHERE txid = ? ORDER BY id DESC LIMIT 1", (txid,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_calls_by_address(address: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM calls WHERE address = ? ORDER BY ts DESC LIMIT ?", (address, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
