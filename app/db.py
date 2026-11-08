import hashlib
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 3

TABLES = [
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT,
        password_hash TEXT,
        created_at TEXT NOT NULL
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)",
    """CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
    """CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, id)",
    """CREATE TABLE IF NOT EXISTS security_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_events_time ON security_events(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_events_user ON security_events(user_id, created_at)",
    """CREATE TABLE IF NOT EXISTS usage_daily (
        day TEXT PRIMARY KEY,
        calls INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        fact TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (user_id, fact)
    )""",
]


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _now() -> str:
    return _iso(datetime.now(timezone.utc))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Database:
    def __init__(self, path: str, session_days: int = 30):
        if path == ":memory:":
            raise ValueError("Use a file path; each operation opens its own connection.")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.session_days = session_days
        self._init_schema()

    def _init_schema(self) -> None:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            conn.execute("PRAGMA foreign_keys = OFF")  # needed while rebuilding tables
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            has_users = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'users'"
            ).fetchone()
            if version == 0 and has_users:
                self._migrate_v0_to_v1(conn)
            for statement in TABLES:  # every statement is IF NOT EXISTS, so this also adds newer tables
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        finally:
            conn.close()

    def _migrate_v0_to_v1(self, conn) -> None:
        
        expiry = _iso(datetime.now(timezone.utc) + timedelta(days=self.session_days))
        conn.execute("BEGIN")
        try:
            conn.execute(
                "CREATE TABLE users_new (id TEXT PRIMARY KEY, email TEXT, password_hash TEXT, created_at TEXT NOT NULL)"
            )
            conn.execute("INSERT INTO users_new (id, created_at) SELECT id, created_at FROM users")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
                "created_at TEXT NOT NULL, expires_at TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT OR IGNORE INTO sessions (token_hash, user_id, created_at, expires_at) "
                "SELECT token_hash, id, created_at, ? FROM users",
                (expiry,),
            )
            conn.execute("DROP TABLE users")
            conn.execute("ALTER TABLE users_new RENAME TO users")
            for statement in TABLES:  # adds the indexes (and any missing table)
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_account(self, email: Optional[str] = None, password_hash: Optional[str] = None) -> Optional[str]:
        user_id = uuid.uuid4().hex
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, email, password_hash, _now()),
                )
        except sqlite3.IntegrityError:
            return None
        return user_id

    def create_user(self):
        user_id = self.create_account()
        return user_id, self.create_session(user_id)

    def get_user(self, user_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return None
        return {"id": row["id"], "email": row["email"], "anonymous": row["email"] is None}

    def find_user_by_email(self, email: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
        return dict(row) if row else None

    def set_credentials(self, user_id: str, email: str, password_hash: str) -> bool:
        """Turn an anonymous user into a registered one. False if the email is taken or already set."""
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "UPDATE users SET email = ?, password_hash = ? WHERE id = ? AND email IS NULL",
                    (email, password_hash, user_id),
                )
                return cur.rowcount == 1
        except sqlite3.IntegrityError:
            return False

    def purge_abandoned_anonymous(self) -> None:
        
        grace = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM users WHERE email IS NULL AND created_at < ? AND NOT EXISTS "
                "(SELECT 1 FROM sessions WHERE sessions.user_id = users.id AND sessions.expires_at > ?)",
                (grace, _now()),
            )

    def delete_user(self, user_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        expires = _iso(datetime.now(timezone.utc) + timedelta(days=self.session_days))
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (hash_token(token), user_id, _now(), expires),
            )
        return token

    def user_id_for_token(self, token: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > ?",
                (hash_token(token), _now()),
            ).fetchone()
        return row["user_id"] if row else None

    def revoke_session(self, token: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))

    def revoke_user_sessions(self, user_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def purge_expired_sessions(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (_now(),))

    def consume_daily_call(self, limit: int) -> bool:
        
        if limit <= 0:
            return True
        today = datetime.now(timezone.utc).date().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO usage_daily (day, calls) VALUES (?, 1) "
                "ON CONFLICT(day) DO UPDATE SET calls = calls + 1 WHERE calls < ?",
                (today, limit),
            )
            return cur.rowcount == 1

    def record_event(self, user_id: Optional[str], kind: str, detail: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO security_events (user_id, kind, detail, created_at) VALUES (?, ?, ?, ?)",
                (user_id, kind, detail[:200], _now()),
            )

    def event_rows(self, since: str, user_id: Optional[str] = None) -> list:
        sql = "SELECT kind, detail, created_at FROM security_events WHERE created_at >= ?"
        params = [since]
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def recent_events(self, limit: int = 20, user_id: Optional[str] = None) -> list:
        sql = "SELECT kind, detail, created_at FROM security_events"
        params = []
        if user_id is not None:
            sql += " WHERE user_id = ?"
            params.append(user_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def purge_old_events(self, days: int = 90) -> None:
        cutoff = _iso(datetime.now(timezone.utc) - timedelta(days=days))
        with self._conn() as conn:
            conn.execute("DELETE FROM security_events WHERE created_at < ?", (cutoff,))

    def add_message(self, user_id: str, role: str, content: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (user_id, role, content, _now()),
            )

    def recent_messages(self, user_id: str, limit: int = 10) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def count_user_messages(self, user_id: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE user_id = ? AND role = 'user'",
                (user_id,),
            ).fetchone()
        return row["n"]

    def add_memory(self, user_id: str, fact: str, max_memories: int = 50) -> bool:
        with self._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM memories WHERE user_id = ?", (user_id,)
            ).fetchone()["n"]
            if count >= max_memories:
                return False
            cur = conn.execute(
                "INSERT OR IGNORE INTO memories (user_id, fact, created_at) VALUES (?, ?, ?)",
                (user_id, fact, _now()),
            )
            return cur.rowcount == 1

    def list_memories(self, user_id: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, fact, created_at FROM memories WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_memory(self, user_id: str, memory_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM memories WHERE id = ? AND user_id = ?", (memory_id, user_id)
            )
            return cur.rowcount == 1