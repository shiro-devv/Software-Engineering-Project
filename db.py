"""SQLite persistence for the student attendance app.

The module deliberately keeps every query small and parameterised.  A fresh
connection is opened for each operation because Streamlit may rerun a script
from any of several threads.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import bcrypt

APP_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = APP_DIR / "data" / "attendance.db"
DB_PATH = Path(os.environ.get("ATTENDANCE_DB_PATH", str(DEFAULT_DB_PATH))).expanduser()

BCRYPT_ROUNDS = 12


class DuplicateStudentCode(Exception):
    """Raised when a student code has already been enrolled."""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Yield a transactional connection and always close it afterwards."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    """Create the schema and seed the requested default administrator once."""
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                photo BLOB,
                face_encoding BLOB,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS attendance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'present',
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE (student_id, date)
            );

            CREATE INDEX IF NOT EXISTS idx_attendance_date
                ON attendance_logs (date, time);
            CREATE INDEX IF NOT EXISTS idx_attendance_student
                ON attendance_logs (student_id);
            """
        )

        admin_exists = connection.execute(
            "SELECT 1 FROM users WHERE username = ?",
            (os.environ.get("ATTENDANCE_ADMIN_USERNAME", "admin"),),
        ).fetchone()
        if not admin_exists:
            username = os.environ.get("ATTENDANCE_ADMIN_USERNAME", "admin")
            password = os.environ.get("ATTENDANCE_ADMIN_PASSWORD", "admin123")
            connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, _hash_password(password)),
            )


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------


def _hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("bcrypt accepts passwords of at most 72 UTF-8 bytes.")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode(
        "utf-8"
    )


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def today_iso() -> str:
    """Return the local calendar date in ISO format."""
    return datetime.now().date().isoformat()


def current_time_iso() -> str:
    """Return the local wall-clock time ready for display or storage."""
    return datetime.now().strftime("%H:%M:%S")


def format_time(value: str | None) -> str:
    """Render a stored ``HH:MM:SS`` value as ``08:32 AM``."""
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%H:%M:%S").strftime("%I:%M %p")
    except ValueError:
        return value


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    """Return the matching user, or ``None`` for invalid credentials."""
    username = username.strip()
    if not username or not password:
        return None
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None:
        return None
    try:
        valid = bcrypt.checkpw(
            password.encode("utf-8"), row["password_hash"].encode("utf-8")
        )
    except (ValueError, TypeError):
        return None
    if not valid:
        return None
    return {"id": row["id"], "username": row["username"]}


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------


def count_students(search: str = "") -> int:
    """Count students, optionally narrowing the result by name or code."""
    query = "SELECT COUNT(*) AS total FROM students"
    params: tuple[Any, ...] = ()
    if search.strip():
        query += " WHERE name LIKE ? COLLATE NOCASE OR student_code LIKE ? COLLATE NOCASE"
        pattern = f"%{search.strip()}%"
        params = (pattern, pattern)
    with _connect() as connection:
        row = connection.execute(query, params).fetchone()
    return int(row["total"]) if row else 0


def list_students_with_status(
    attendance_date: str,
    search: str = "",
    limit: int = 6,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return one page of students together with today's attendance state."""
    query = """
        SELECT
            s.id,
            s.student_code,
            s.name,
            s.photo,
            s.created_at,
            CASE WHEN a.id IS NULL THEN 'absent' ELSE 'present' END AS status,
            a.time AS marked_time
        FROM students AS s
        LEFT JOIN attendance_logs AS a
            ON a.student_id = s.id AND a.date = ?
    """
    params: list[Any] = [attendance_date]
    if search.strip():
        query += " WHERE s.name LIKE ? COLLATE NOCASE OR s.student_code LIKE ? COLLATE NOCASE"
        pattern = f"%{search.strip()}%"
        params.extend([pattern, pattern])
    query += " ORDER BY s.name COLLATE NOCASE, s.id LIMIT ? OFFSET ?"
    params.extend([max(1, limit), max(0, offset)])

    with _connect() as connection:
        rows = connection.execute(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def get_student(student_id: int) -> dict[str, Any] | None:
    """Fetch all editable fields for an individual student."""
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, student_code, name, photo, face_encoding, created_at
            FROM students
            WHERE id = ?
            """,
            (int(student_id),),
        ).fetchone()
    return _row_to_dict(row)


def add_student(
    name: str,
    student_code: str,
    photo: bytes | None,
    face_encoding: bytes | None,
) -> int:
    """Insert a student and return the new primary key."""
    try:
        with _connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO students (student_code, name, photo, face_encoding)
                VALUES (?, ?, ?, ?)
                """,
                (student_code.strip(), name.strip(), photo, face_encoding),
            )
            return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        if "student_code" in str(exc).lower() or "unique" in str(exc).lower():
            raise DuplicateStudentCode(student_code) from exc
        raise


def update_student(
    student_id: int,
    name: str,
    student_code: str,
    photo: bytes | None,
    face_encoding: bytes | None,
) -> bool:
    """Update student details.  Photo and encoding are replaced together."""
    try:
        with _connect() as connection:
            cursor = connection.execute(
                """
                UPDATE students
                SET name = ?, student_code = ?, photo = ?, face_encoding = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    student_code.strip(),
                    photo,
                    face_encoding,
                    int(student_id),
                ),
            )
            return cursor.rowcount > 0
    except sqlite3.IntegrityError as exc:
        if "student_code" in str(exc).lower() or "unique" in str(exc).lower():
            raise DuplicateStudentCode(student_code) from exc
        raise


def delete_student(student_id: int) -> bool:
    """Remove a student and, through the FK cascade, their attendance logs."""
    with _connect() as connection:
        cursor = connection.execute("DELETE FROM students WHERE id = ?", (int(student_id),))
        return cursor.rowcount > 0


def list_face_encodings() -> list[dict[str, Any]]:
    """Return only the columns needed by the recognition cache."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, name, face_encoding
            FROM students
            WHERE face_encoding IS NOT NULL
            ORDER BY id
            """
        ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------


def get_attendance_for(student_id: int, attendance_date: str) -> dict[str, Any] | None:
    """Return a student's attendance row for a given day, if it exists."""
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT id, student_id, date, time, status
            FROM attendance_logs
            WHERE student_id = ? AND date = ?
            """,
            (int(student_id), attendance_date),
        ).fetchone()
    return _row_to_dict(row)


def mark_present(student_id: int, attendance_date: str | None = None) -> tuple[bool, str]:
    """Mark a student present exactly once.

    Returns ``(created, time)``.  When the student was already marked, their
    original timestamp is returned and no duplicate row is written.
    """
    attendance_date = attendance_date or today_iso()
    existing = get_attendance_for(student_id, attendance_date)
    if existing:
        return False, existing["time"]

    timestamp = current_time_iso()
    try:
        with _connect() as connection:
            connection.execute(
                """
                INSERT INTO attendance_logs (student_id, date, time, status)
                VALUES (?, ?, ?, 'present')
                """,
                (int(student_id), attendance_date, timestamp),
            )
        return True, timestamp
    except sqlite3.IntegrityError:
        # A second request won the race; use its original timestamp.
        existing = get_attendance_for(student_id, attendance_date)
        if existing:
            return False, existing["time"]
        raise


def dashboard_metrics(attendance_date: str | None = None) -> dict[str, int]:
    """Return the three values displayed on the dashboard."""
    attendance_date = attendance_date or today_iso()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM students) AS total,
                (
                    SELECT COUNT(DISTINCT student_id)
                    FROM attendance_logs
                    WHERE date = ? AND status = 'present'
                ) AS present
            """,
            (attendance_date,),
        ).fetchone()
    total = int(row["total"]) if row else 0
    present = int(row["present"]) if row else 0
    return {
        "total": total,
        "present": present,
        "absent": max(total - present, 0),
    }


def recent_activity(
    attendance_date: str | None = None, limit: int = 8
) -> list[dict[str, Any]]:
    """Return today's most recent check-ins for the activity card."""
    attendance_date = attendance_date or today_iso()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT s.name, a.time, a.status
            FROM attendance_logs AS a
            JOIN students AS s ON s.id = a.student_id
            WHERE a.date = ?
            ORDER BY a.time DESC, a.id DESC
            LIMIT ?
            """,
            (attendance_date, max(1, limit)),
        ).fetchall()
    return [dict(row) for row in rows]
