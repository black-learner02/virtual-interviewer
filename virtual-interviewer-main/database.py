import sqlite3
import json
import hashlib
import secrets
from datetime import datetime

DB_NAME = "interview_db.sqlite"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        full_name TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS auth_sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS interviews (
        session_id TEXT PRIMARY KEY,
        user_id INTEGER,
        candidate_name TEXT,
        target_role TEXT,
        start_time TEXT,
        status TEXT DEFAULT 'IN_PROGRESS',
        language TEXT DEFAULT 'en',
        resume_text TEXT,
        job_description TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        question_index INTEGER,
        question_text TEXT,
        question_type TEXT DEFAULT 'technical',
        transcript TEXT,
        audio_metrics TEXT,
        video_metrics TEXT,
        timeline_json TEXT,
        ai_feedback TEXT,
        ai_score INTEGER,
        FOREIGN KEY(session_id) REFERENCES interviews(session_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        session_id TEXT PRIMARY KEY,
        report_json TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES interviews(session_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS pdf_reports (
        session_id TEXT PRIMARY KEY,
        pdf_data BLOB NOT NULL,
        analytics_json TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES interviews(session_id)
    )''')

    conn.commit()
    _run_migrations(c)
    conn.commit()
    conn.close()
    print(f"💽 Database ready: {DB_NAME}")


def _run_migrations(c):
    """Non-destructively adds columns that may be missing in older DBs."""
    c.execute("PRAGMA table_info(interviews)")
    cols = [r[1] for r in c.fetchall()]
    if "user_id" not in cols:
        c.execute("ALTER TABLE interviews ADD COLUMN user_id INTEGER")
        print("  ↳ Migrated: interviews.user_id")
    if "language" not in cols:
        c.execute("ALTER TABLE interviews ADD COLUMN language TEXT DEFAULT 'en'")
        print("  ↳ Migrated: interviews.language")
    if "resume_text" not in cols:
        c.execute("ALTER TABLE interviews ADD COLUMN resume_text TEXT")
        print("  ↳ Migrated: interviews.resume_text")
    if "job_description" not in cols:
        c.execute("ALTER TABLE interviews ADD COLUMN job_description TEXT")
        print("  ↳ Migrated: interviews.job_description")

    c.execute("PRAGMA table_info(responses)")
    cols = [r[1] for r in c.fetchall()]
    if "question_type" not in cols:
        c.execute("ALTER TABLE responses ADD COLUMN question_type TEXT DEFAULT 'technical'")
        print("  ↳ Migrated: responses.question_type")


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def register_user(username, email, password, full_name=""):
    salt = secrets.token_hex(32)
    pw_hash = _hash_password(password, salt)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, email, password_hash, salt, full_name) VALUES (?, ?, ?, ?, ?)",
            (username.lower().strip(), email.lower().strip(), pw_hash, salt, full_name)
        )
        conn.commit()
        return True, c.lastrowid
    except sqlite3.IntegrityError as e:
        if "username" in str(e): return False, "Username already taken."
        if "email" in str(e): return False, "An account with this email already exists."
        return False, "Registration failed."
    finally:
        conn.close()


def login_user(username_or_email, password):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    identifier = username_or_email.lower().strip()
    c.execute("SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier))
    user = c.fetchone()
    if not user or _hash_password(password, user["salt"]) != user["password_hash"]:
        conn.close()
        return False, "Invalid username or password."

    token = secrets.token_urlsafe(48)
    expires_at = datetime.now().replace(hour=23, minute=59, second=59).isoformat()
    c.execute(
        "INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user["id"], expires_at)
    )
    conn.commit()
    conn.close()
    return True, {
        "token": token,
        "user_id": user["id"],
        "full_name": user["full_name"],
        "username": user["username"]
    }


def validate_token(token):
    if not token:
        return None
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT user_id, expires_at FROM auth_sessions WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    if not row or datetime.fromisoformat(row["expires_at"]) < datetime.now():
        return None
    return row["user_id"]


def logout_user(token):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# INTERVIEWS
# ─────────────────────────────────────────────

def create_session(session_id, name, role, user_id=None, language='en',
                   resume_text=None, job_description=None):
    """Creates a new interview session with optional resume and job description context."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO interviews "
        "(session_id, user_id, candidate_name, target_role, start_time, status, language, resume_text, job_description) "
        "VALUES (?, ?, ?, ?, ?, 'IN_PROGRESS', ?, ?, ?)",
        (session_id, user_id, name, role, datetime.now().isoformat(),
         language, resume_text, job_description)
    )
    conn.commit()
    conn.close()


def mark_session_completed(session_id: str):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE interviews SET status = 'COMPLETED' WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


def save_response(session_id, q_index, question, question_type, transcript,
                  audio_metrics, video_metrics, timeline, ai_feedback, ai_score):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO responses
        (session_id, question_index, question_text, question_type, transcript,
         audio_metrics, video_metrics, timeline_json, ai_feedback, ai_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        session_id, q_index, question, question_type, transcript,
        json.dumps(audio_metrics), json.dumps(video_metrics),
        json.dumps(timeline), ai_feedback, ai_score
    ))
    conn.commit()
    conn.close()


def get_chat_history(session_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT question_text as q_text, question_type, transcript, ai_score FROM responses "
        "WHERE session_id = ? ORDER BY question_index ASC",
        (session_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [{"q_text": r["q_text"], "q_type": r["question_type"],
             "transcript": r["transcript"], "score": r["ai_score"]} for r in rows]


def get_session_info(session_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM interviews WHERE session_id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_full_session_data(session_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM interviews WHERE session_id = ?", (session_id,))
    session_row = c.fetchone()
    if not session_row:
        conn.close()
        return None, []
    session = dict(session_row)
    c.execute(
        "SELECT * FROM responses WHERE session_id = ? ORDER BY question_index ASC",
        (session_id,)
    )
    responses = [dict(r) for r in c.fetchall()]
    conn.close()
    return session, responses


# ─────────────────────────────────────────────
# REPORT STORAGE
# ─────────────────────────────────────────────

def save_report(session_id: str, report_data: dict):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO reports (session_id, report_json, generated_at) VALUES (?, ?, ?)",
        (session_id, json.dumps(report_data), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_stored_report(session_id: str):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT report_json FROM reports WHERE session_id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row["report_json"])
    except Exception:
        return None


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

def get_user_interviews(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT  i.session_id,
                i.candidate_name,
                i.target_role,
                i.start_time,
                i.status,
                i.language,
                CASE WHEN i.resume_text IS NOT NULL AND i.resume_text != '' THEN 1 ELSE 0 END AS has_resume,
                CASE WHEN i.job_description IS NOT NULL AND i.job_description != '' THEN 1 ELSE 0 END AS has_jd,
                COUNT(r.id)              AS response_count,
                ROUND(AVG(r.ai_score),1) AS avg_score
        FROM interviews i
        LEFT JOIN responses r ON i.session_id = r.session_id
        WHERE i.user_id = ?
        GROUP BY i.session_id
        HAVING response_count > 0
        ORDER BY i.start_time DESC
        """,
        (user_id,)
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ─────────────────────────────────────────────
# PDF REPORT STORAGE
# ─────────────────────────────────────────────

def save_pdf_report(session_id: str, pdf_bytes: bytes, analytics: dict):
    """Stores the generated PDF binary and its analytics data."""
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO pdf_reports "
        "(session_id, pdf_data, analytics_json, generated_at) VALUES (?, ?, ?, ?)",
        (session_id, pdf_bytes, json.dumps(analytics), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_pdf_report(session_id: str) -> tuple:
    """
    Returns (pdf_bytes, analytics_dict) or (None, None) if not found.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c    = conn.cursor()
    c.execute(
        "SELECT pdf_data, analytics_json FROM pdf_reports WHERE session_id = ?",
        (session_id,)
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None, None
    analytics = {}
    try:
        analytics = json.loads(row['analytics_json'])
    except Exception:
        pass
    return bytes(row['pdf_data']), analytics