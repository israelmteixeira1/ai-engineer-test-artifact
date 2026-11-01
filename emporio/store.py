import json
import sqlite3
from pathlib import Path


class ConversationStore:
    def __init__(self, path: str | Path = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT PRIMARY KEY, messages TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, reason TEXT,
                summary TEXT, contact TEXT, created_at TEXT);
            """
        )

    def load(self, session_id: str) -> list[dict]:
        row = self.db.execute(
            "SELECT messages FROM conversations WHERE session_id = ?", (session_id,)
        ).fetchone()
        return json.loads(row[0]) if row else []

    def save(self, session_id: str, messages: list[dict]) -> None:
        self.db.execute(
            "INSERT INTO conversations VALUES (?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET messages = excluded.messages",
            (session_id, json.dumps(messages, ensure_ascii=False)),
        )
        self.db.commit()

    def add_ticket(self, session_id: str, reason: str, summary: str, contact: str, created_at: str) -> int:
        cursor = self.db.execute(
            "INSERT INTO tickets (session_id, reason, summary, contact, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, reason, summary, contact, created_at),
        )
        self.db.commit()
        return cursor.lastrowid
