import os
import json
import uuid
import sqlite3
import threading
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Union

from app.config import CHAT_DB_PATH, OUTPUTS_DIR


class ChatStore:
    """Thread-safe SQLite persistent dynamic chat session and message storage."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else CHAT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _get_conn(self):
        """Thread-safe SQLite connection factory with WAL mode and foreign keys enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initialize SQLite database tables and indices if not already present."""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP,
                        active_image_id TEXT,
                        active_image_path TEXT
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT,
                        image_path TEXT,
                        image_url TEXT,
                        edit_parent_id TEXT,
                        metadata_json TEXT,
                        created_at TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC);")
                conn.commit()

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_session(
        self,
        title: Optional[str] = None,
        session_id: Optional[str] = None,
        active_image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new chat session."""
        sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        now = self._utc_now_iso()
        clean_title = (title.strip() if title and title.strip() else None) or "New Chat"
        active_img_id = Path(active_image_path).stem if active_image_path else None

        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO sessions (id, title, created_at, updated_at, active_image_id, active_image_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sid, clean_title, now, now, active_img_id, active_image_path))
                conn.commit()

        return {
            "id": sid,
            "title": clean_title,
            "created_at": now,
            "updated_at": now,
            "active_image_id": active_img_id,
            "active_image_path": active_image_path,
            "messages": []
        }

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all chat sessions with summary (sorted by updated_at desc)."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT 
                    s.id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    s.active_image_id,
                    s.active_image_path,
                    COUNT(m.id) as message_count,
                    (
                        SELECT m2.image_url 
                        FROM messages m2 
                        WHERE m2.session_id = s.id AND m2.image_url IS NOT NULL 
                        ORDER BY m2.created_at DESC LIMIT 1
                    ) as latest_image_url,
                    (
                        SELECT m3.image_path 
                        FROM messages m3 
                        WHERE m3.session_id = s.id AND m3.image_path IS NOT NULL 
                        ORDER BY m3.created_at DESC LIMIT 1
                    ) as latest_image_path
                FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                GROUP BY s.id
                ORDER BY s.updated_at DESC;
            """)
            rows = cursor.fetchall()

        summaries = []
        for r in rows:
            preview_img = r["latest_image_url"]
            if not preview_img and r["latest_image_path"]:
                clean_name = Path(r["latest_image_path"]).name
                preview_img = f"/api/image/{clean_name}"
            elif not preview_img and r["active_image_path"]:
                clean_name = Path(r["active_image_path"]).name
                preview_img = f"/api/image/{clean_name}"

            summaries.append({
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "active_image_id": r["active_image_id"],
                "active_image_path": r["active_image_path"],
                "message_count": int(r["message_count"] or 0),
                "preview_image": preview_img
            })
        return summaries

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details, active context, and message history in chronological order."""
        with self._get_conn() as conn:
            s_cur = conn.execute("SELECT * FROM sessions WHERE id = ?;", (session_id,))
            s_row = s_cur.fetchone()
            if not s_row:
                return None

            m_cur = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC;",
                (session_id,)
            )
            m_rows = m_cur.fetchall()

        messages = []
        for mr in m_rows:
            meta = None
            if mr["metadata_json"]:
                try:
                    meta = json.loads(mr["metadata_json"])
                except Exception:
                    meta = {}

            messages.append({
                "id": mr["id"],
                "session_id": mr["session_id"],
                "role": mr["role"],
                "content": mr["content"],
                "image_path": mr["image_path"],
                "image_url": mr["image_url"],
                "edit_parent_id": mr["edit_parent_id"],
                "metadata": meta,
                "created_at": mr["created_at"]
            })

        return {
            "id": s_row["id"],
            "title": s_row["title"],
            "created_at": s_row["created_at"],
            "updated_at": s_row["updated_at"],
            "active_image_id": s_row["active_image_id"],
            "active_image_path": s_row["active_image_path"],
            "message_count": len(messages),
            "messages": messages
        }

    def update_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        active_image_path: Optional[str] = None,
        active_image_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update session title or active image context."""
        now = self._utc_now_iso()
        fields = ["updated_at = ?"]
        values = [now]

        if title is not None:
            fields.append("title = ?")
            values.append(title.strip())

        if active_image_path is not None:
            fields.append("active_image_path = ?")
            values.append(active_image_path)
            clean_id = active_image_id or (Path(active_image_path).stem if active_image_path else None)
            fields.append("active_image_id = ?")
            values.append(clean_id)

        values.append(session_id)
        sql = f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?;"

        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute(sql, tuple(values))
                if cur.rowcount == 0:
                    return None
                conn.commit()

        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all cascading messages."""
        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("DELETE FROM sessions WHERE id = ?;", (session_id,))
                conn.commit()
                return cur.rowcount > 0

    def clear_all_sessions(self) -> int:
        """Delete all chat sessions and messages, and vacuum the database."""
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM messages;")
                cur = conn.execute("DELETE FROM sessions;")
                conn.commit()
                conn.execute("VACUUM;")
                return cur.rowcount

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        image_path: Optional[str] = None,
        image_url: Optional[str] = None,
        edit_parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a user or assistant message to a chat session, updating updated_at and active context."""
        mid = message_id or f"msg_{uuid.uuid4().hex[:12]}"
        now = self._utc_now_iso()

        # Derive image_url if not provided but image_path exists
        if not image_url and image_path:
            clean_name = Path(image_path).name
            image_url = f"/api/image/{clean_name}"

        meta_json = json.dumps(metadata) if metadata is not None else None

        with self._lock:
            with self._get_conn() as conn:
                # Ensure session exists; if not, create it
                s_check = conn.execute("SELECT id FROM sessions WHERE id = ?;", (session_id,)).fetchone()
                if not s_check:
                    default_title = content[:30] if content else "Chat Session"
                    conn.execute("""
                        INSERT INTO sessions (id, title, created_at, updated_at, active_image_id, active_image_path)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (session_id, default_title, now, now, None, None))

                conn.execute("""
                    INSERT INTO messages (
                        id, session_id, role, content, image_path, image_url, edit_parent_id, metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (mid, session_id, role, content, image_path, image_url, edit_parent_id, meta_json, now))

                # Update session's updated_at and active image if an image is provided
                if image_path:
                    active_id = Path(image_path).stem
                    conn.execute("""
                        UPDATE sessions 
                        SET updated_at = ?, active_image_path = ?, active_image_id = ?
                        WHERE id = ?;
                    """, (now, image_path, active_id, session_id))
                else:
                    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?;", (now, session_id))

                conn.commit()

        return {
            "id": mid,
            "session_id": session_id,
            "role": role,
            "content": content,
            "image_path": image_path,
            "image_url": image_url,
            "edit_parent_id": edit_parent_id,
            "metadata": metadata or {},
            "created_at": now
        }

    def set_active_context(
        self,
        session_id: str,
        image_path: str,
        image_id: Optional[str] = None
    ) -> bool:
        """Update active image context for a chat session."""
        now = self._utc_now_iso()
        img_id = image_id or Path(image_path).stem

        with self._lock:
            with self._get_conn() as conn:
                cur = conn.execute("""
                    UPDATE sessions 
                    SET updated_at = ?, active_image_path = ?, active_image_id = ?
                    WHERE id = ?;
                """, (now, image_path, img_id, session_id))
                conn.commit()
                return cur.rowcount > 0

    def get_lineage_messages(
        self,
        session_id: str,
        edit_parent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve message history along parent-child edit tree branch.
        If edit_parent_id is None, returns chronological history.
        If edit_parent_id is provided, traverses backward along edit_parent_id links.
        """
        if not edit_parent_id:
            sess = self.get_session(session_id)
            return sess.get("messages", []) if sess else []

        with self._lock:
            with self._get_conn() as conn:
                lineage = []
                curr_id = edit_parent_id
                visited = set()
                while curr_id and curr_id not in visited:
                    visited.add(curr_id)
                    row = conn.execute(
                        "SELECT * FROM messages WHERE id = ? AND session_id = ?;",
                        (curr_id, session_id)
                    ).fetchone()
                    if not row:
                        break
                    meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                    lineage.insert(0, {
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "role": row["role"],
                        "content": row["content"],
                        "image_path": row["image_path"],
                        "image_url": row["image_url"],
                        "edit_parent_id": row["edit_parent_id"],
                        "metadata": meta,
                        "created_at": row["created_at"]
                    })
                    curr_id = row["edit_parent_id"]
                return lineage


# Default global instance
default_store = ChatStore()

# Module-level convenience functions
def create_session(title: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
    return default_store.create_session(title=title, session_id=session_id)

def list_sessions() -> List[Dict[str, Any]]:
    return default_store.list_sessions()

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    return default_store.get_session(session_id)

def update_session(session_id: str, title: Optional[str] = None, active_image_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return default_store.update_session(session_id, title=title, active_image_path=active_image_path)

def delete_session(session_id: str) -> bool:
    return default_store.delete_session(session_id)

def clear_all_sessions() -> int:
    return default_store.clear_all_sessions()

def add_message(
    session_id: str,
    role: str,
    content: str,
    image_path: Optional[str] = None,
    image_url: Optional[str] = None,
    edit_parent_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return default_store.add_message(
        session_id=session_id,
        role=role,
        content=content,
        image_path=image_path,
        image_url=image_url,
        edit_parent_id=edit_parent_id,
        metadata=metadata
    )

def set_active_context(session_id: str, image_path: str) -> bool:
    return default_store.set_active_context(session_id=session_id, image_path=image_path)

def get_lineage_messages(session_id: str, edit_parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return default_store.get_lineage_messages(session_id=session_id, edit_parent_id=edit_parent_id)
