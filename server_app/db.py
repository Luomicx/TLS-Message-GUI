from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from .security import hash_password, verify_password


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


ALLOWED_ENCODINGS = {"base64", "hex", "caesar"}


def normalize_encoding_rule(text: str) -> list[str]:
    """Accepts 'base64,hex' or JSON array; returns normalized list of tokens."""
    if text is None:
        return []
    s = text.strip()
    if not s:
        return []

    # If user pasted JSON, accept it.
    if s.startswith("["):
        try:
            arr = json.loads(s)
        except Exception as e:  # noqa: BLE001
            raise ValueError("encoding_rule JSON invalid") from e
        if not isinstance(arr, list):
            raise ValueError("encoding_rule must be a list")
        tokens = [str(x).strip().lower() for x in arr if str(x).strip()]
    else:
        tokens = [t.strip().lower() for t in s.split(",") if t.strip()]

    bad = [t for t in tokens if t not in ALLOWED_ENCODINGS]
    if bad:
        raise ValueError(f"invalid encoding token(s): {', '.join(bad)}")

    # De-dup while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out


def encoding_rule_to_json(rule: Iterable[str]) -> str:
    return json.dumps(list(rule), ensure_ascii=False)


@dataclass
class UserRow:
    id: int
    username: str
    avatar: Optional[bytes]
    encoding_rule: str
    locked: int
    created_at: str


@dataclass(frozen=True)
class LoginResult:
    ok: bool
    code: str
    message: str
    user: dict[str, Any] | None = None


class Database:
    def __init__(self, path: Path, *, journal_mode: str = "WAL"):
        self.path = Path(path)
        self.journal_mode = journal_mode

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(f"PRAGMA journal_mode={self.journal_mode}")
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    avatar BLOB NULL,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    encoding_rule TEXT NOT NULL DEFAULT '[]',
                    locked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_users_locked ON users(locked);
                CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

                CREATE TABLE IF NOT EXISTS friends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    friend_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(username, friend_id),
                    FOREIGN KEY(friend_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_friends_username ON friends(username);
                CREATE INDEX IF NOT EXISTS idx_friends_friend_id ON friends(friend_id);

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    receiver TEXT NOT NULL,
                    content TEXT NOT NULL,
                    encoding_rule TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_receiver_id ON messages(receiver, id);
                CREATE INDEX IF NOT EXISTS idx_messages_sender_receiver ON messages(sender, receiver);
                """
            )

    def ensure_seed_users(self) -> None:
        """Insert a few demo users when DB is empty (for screenshot-like demo)."""
        with self.connect() as conn:
            cur = conn.execute("SELECT COUNT(*) AS c FROM users")
            c = int(cur.fetchone()["c"])
            if c > 0:
                return

            # Simple seed users; avatars empty.
            for name in [
                "besti",
                "zhjw",
                "华航",
                "bestnk",
                "Ella",
                "计算机",
                "网络工程",
                "山高人为峰",
                "我的名字是不是非常非常的长呢",
            ]:
                self.insert_user(
                    conn,
                    username=name,
                    password="123456",
                    avatar=None,
                    encoding_rule=["base64"],
                    locked=0,
                )

    def insert_user(
        self,
        conn: sqlite3.Connection,
        *,
        username: str,
        password: str,
        avatar: Optional[bytes],
        encoding_rule: Iterable[str],
        locked: int,
    ) -> int:
        ph = hash_password(password)
        t = now_text()
        cur = conn.execute(
            """
            INSERT INTO users(
                username, avatar, password_salt, password_hash, encoding_rule, locked, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                username,
                avatar,
                ph.salt,
                ph.digest,
                encoding_rule_to_json(encoding_rule),
                int(bool(locked)),
                t,
                t,
            ),
        )
        return int(cur.lastrowid)

    def list_users(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT id, username, avatar, encoding_rule, locked, created_at
                FROM users
                ORDER BY created_at ASC, id ASC
                """
            )
            return list(cur.fetchall())

    def list_unlocked_users(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT id, username, avatar, encoding_rule, locked, created_at
                FROM users
                WHERE locked = 0
                ORDER BY created_at ASC, id ASC
                """
            )
            return list(cur.fetchall())

    def verify_login(self, username: str, password: str) -> bool:
        return self.verify_login_detail(username, password).ok

    def verify_login_detail(self, username: str, password: str) -> LoginResult:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT id, username, avatar, encoding_rule, password_salt, password_hash, locked
                FROM users
                WHERE username = ?
                LIMIT 1
                """,
                (username,),
            )
            row = cur.fetchone()
            if row is None:
                return LoginResult(False, "user_not_found", "用户名或密码错误")
            if int(row["locked"]) != 0:
                return LoginResult(False, "user_locked", "帐号被锁定")
            ok = verify_password(
                password,
                bytes(row["password_salt"]),
                bytes(row["password_hash"]),
            )
            if not ok:
                return LoginResult(False, "invalid_credentials", "用户名或密码错误")
            return LoginResult(
                True,
                "ok",
                "登录成功",
                user={
                    "id": int(row["id"]),
                    "username": str(row["username"]),
                    "encoding_rule": normalize_encoding_rule(str(row["encoding_rule"])),
                    "avatar": bool(row["avatar"]),
                },
            )

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT id, username, avatar, encoding_rule, locked, created_at
                FROM users
                WHERE username = ?
                LIMIT 1
                """,
                (username,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return self._user_row_to_dict(row)

    def register_user(
        self,
        *,
        username: str,
        password: str,
        avatar: Optional[bytes] = None,
        encoding_rule: Iterable[str] = (),
    ) -> dict[str, Any]:
        clean_username = username.strip()
        if not clean_username:
            raise ValueError("username cannot be empty")
        if password is None or password == "":
            raise ValueError("password cannot be empty")
        rule = list(encoding_rule) or ["base64"]
        with self.connect() as conn:
            user_id = self.insert_user(
                conn,
                username=clean_username,
                password=password,
                avatar=avatar,
                encoding_rule=rule,
                locked=0,
            )
        return {
            "id": user_id,
            "username": clean_username,
            "encoding_rule": list(rule),
        }

    def search_users_fuzzy(
        self, query: str, *, exclude_username: str | None = None
    ) -> list[dict[str, Any]]:
        clean = query.strip()
        if not clean:
            return []
        sql = """
            SELECT id, username, avatar, encoding_rule, locked, created_at
            FROM users
            WHERE locked = 0 AND username LIKE ?
            """
        params: list[Any] = [f"%{clean}%"]
        if exclude_username:
            sql += " AND username != ?"
            params.append(exclude_username)
        sql += " ORDER BY username ASC LIMIT 50"
        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            return [self._user_row_to_dict(row) for row in cur.fetchall()]

    def search_user_by_id(
        self, user_id: int | str, *, exclude_username: str | None = None
    ) -> list[dict[str, Any]]:
        try:
            numeric_id = int(user_id)
        except (TypeError, ValueError):
            return []
        sql = """
            SELECT id, username, avatar, encoding_rule, locked, created_at
            FROM users
            WHERE id = ? AND locked = 0
            """
        params: list[Any] = [numeric_id]
        if exclude_username:
            sql += " AND username != ?"
            params.append(exclude_username)
        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            return [self._user_row_to_dict(row) for row in cur.fetchall()]

    def add_friend(self, username: str, friend_id: int) -> dict[str, Any]:
        owner = self.get_user_by_username(username)
        if owner is None:
            raise ValueError("user_not_found")
        friend_rows = self.search_user_by_id(friend_id)
        if not friend_rows:
            raise ValueError("friend_not_found")
        friend = friend_rows[0]
        if friend["username"] == username:
            raise ValueError("cannot_add_self")

        created_at = now_text()
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT 1 FROM friends WHERE username = ? AND friend_id = ? LIMIT 1",
                (username, int(friend_id)),
            )
            if cur.fetchone() is not None:
                raise ValueError("already_friend")
            conn.execute(
                "INSERT INTO friends(username, friend_id, created_at) VALUES(?,?,?)",
                (username, int(friend_id), created_at),
            )
            conn.execute(
                "INSERT OR IGNORE INTO friends(username, friend_id, created_at) VALUES(?,?,?)",
                (friend["username"], int(owner["id"]), created_at),
            )
        return friend

    def list_friends(self, username: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT u.id, u.username, u.avatar, u.encoding_rule, u.locked, u.created_at
                FROM friends f
                JOIN users u ON u.id = f.friend_id
                WHERE f.username = ? AND u.locked = 0
                ORDER BY u.username ASC
                """,
                (username,),
            )
            return [self._user_row_to_dict(row) for row in cur.fetchall()]

    def save_message(
        self,
        *,
        sender: str,
        receiver: str,
        content: str,
        encoding_rule: Iterable[str] = (),
    ) -> dict[str, Any]:
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("content cannot be empty")
        rule = normalize_encoding_rule(encoding_rule_to_json(encoding_rule))
        created_at = now_text()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages(sender, receiver, content, encoding_rule, created_at)
                VALUES(?,?,?,?,?)
                """,
                (
                    sender,
                    receiver,
                    clean_content,
                    encoding_rule_to_json(rule),
                    created_at,
                ),
            )
            message_id = int(cur.lastrowid)
        return {
            "id": message_id,
            "sender": sender,
            "receiver": receiver,
            "content": clean_content,
            "encoding_rule": rule,
            "created_at": created_at,
        }

    def pull_messages(
        self,
        username: str,
        *,
        since_id: int = 0,
        peer: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT id, sender, receiver, content, encoding_rule, created_at
            FROM messages
            WHERE id > ? AND (sender = ? OR receiver = ?)
            """
        params: list[Any] = [int(since_id), username, username]
        if peer:
            sql += " AND (sender = ? OR receiver = ?)"
            params.extend([peer, peer])
        sql += " ORDER BY id ASC"
        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            return [self._message_row_to_dict(row) for row in cur.fetchall()]

    def list_sessions(self, username: str) -> list[dict[str, Any]]:
        friends = self.list_friends(username)
        friend_map = {item["username"]: item for item in friends}
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT
                    CASE WHEN sender = ? THEN receiver ELSE sender END AS peer,
                    MAX(id) AS last_message_id,
                    MAX(created_at) AS last_message_at
                FROM messages
                WHERE sender = ? OR receiver = ?
                GROUP BY peer
                ORDER BY last_message_id DESC
                """,
                (username, username, username),
            )
            sessions = []
            for row in cur.fetchall():
                peer = str(row["peer"])
                session = {
                    "username": peer,
                    "last_message_id": int(row["last_message_id"]),
                    "last_message_at": str(row["last_message_at"]),
                }
                if peer in friend_map:
                    session.update(friend_map[peer])
                sessions.append(session)
            for friend in friends:
                if friend["username"] not in {item["username"] for item in sessions}:
                    sessions.append(friend)
            return sessions

    def delete_user(self, user_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (int(user_id),))

    def update_username(self, user_id: int, username: str) -> None:
        if not username or not username.strip():
            raise ValueError("username cannot be empty")
        with self.connect() as conn:
            conn.execute(
                "UPDATE users SET username = ?, updated_at = ? WHERE id = ?",
                (username.strip(), now_text(), int(user_id)),
            )

    def update_locked(self, user_id: int, locked: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE users SET locked = ?, updated_at = ? WHERE id = ?",
                (int(bool(locked)), now_text(), int(user_id)),
            )

    def update_encoding_rule(self, user_id: int, encoding_text: str) -> None:
        rule = normalize_encoding_rule(encoding_text)
        with self.connect() as conn:
            conn.execute(
                "UPDATE users SET encoding_rule = ?, updated_at = ? WHERE id = ?",
                (encoding_rule_to_json(rule), now_text(), int(user_id)),
            )

    def update_password(self, user_id: int, new_password: str) -> None:
        if new_password is None or new_password == "":
            raise ValueError("password cannot be empty")
        ph = hash_password(new_password)
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET password_salt = ?, password_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (ph.salt, ph.digest, now_text(), int(user_id)),
            )

    def update_avatar(self, user_id: int, avatar_bytes: Optional[bytes]) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE users SET avatar = ?, updated_at = ? WHERE id = ?",
                (avatar_bytes, now_text(), int(user_id)),
            )

    def _user_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "username": str(row["username"]),
            "avatar": bool(row["avatar"]),
            "encoding_rule": normalize_encoding_rule(str(row["encoding_rule"])),
            "locked": int(row["locked"]),
            "created_at": str(row["created_at"]),
        }

    def _message_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "sender": str(row["sender"]),
            "receiver": str(row["receiver"]),
            "content": str(row["content"]),
            "encoding_rule": normalize_encoding_rule(str(row["encoding_rule"])),
            "created_at": str(row["created_at"]),
        }
