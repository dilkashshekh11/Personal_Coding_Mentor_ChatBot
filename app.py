import hashlib
import html
import os
import re
import secrets
import socket
import sqlite3
import threading
import time
import traceback
import webbrowser
from contextlib import closing
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, send_from_directory, session, stream_with_context, url_for)
from google import genai
from google.genai import types
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv(override=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "dilkash.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
FALLBACKS = [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash,gemini-2.5-flash-lite").split(",") if m.strip()]
MODEL_LIST = list(dict.fromkeys([MODEL] + FALLBACKS))  # main model first, then backups
PORT = int(os.getenv("PORT", "5000"))

HAS_KEY = bool(API_KEY) and API_KEY != "your_api_key_here"
MAX_CODE_CHARS = 20000
MAX_MESSAGE_CHARS = 8000
MAX_PHOTO_BYTES = 2 * 1024 * 1024
HISTORY_LIMIT = 10  # fewer earlier messages means a faster answer
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")

LANGUAGES = ["English", "Nepali", "Hindi"]

# ---------- what each mode does ----------
MODES = {
    "chat": {
        "label": "Chat", "color": "#2563eb",
        "hint": "Ask anything, for example: why is the sky blue?",
        "prompt": "You are a friendly assistant. Answer general questions clearly.",
    },
    "generate": {
        "label": "Generate code", "color": "#16a34a",
        "hint": "Describe the program you need, for example: a Python program that checks if a number is prime",
        "prompt": ("You write code from the user's instructions. Give the complete working code in one "
                   "fenced code block, then two or three short lines on how to run it. "
                   "If the language is not named, use Python."),
    },
    "explain": {
        "label": "Explain code", "color": "#111827",
        "hint": "Paste the code you want explained",
        "prompt": ("You explain code to beginners. Go through the code line by line (or small group of lines). "
                   "Show each line or group in a code block followed by a plain explanation. "
                   "End with a one-sentence summary of what the whole program does."),
    },
    "fix": {
        "label": "Fix errors", "color": "#dc2626",
        "hint": "Paste your code. You can add the error you got below it, but you do not have to.",
        "prompt": ("You find and fix mistakes in code. First say in simple words what is wrong and why. "
                   "Then give the full corrected code in a fenced code block. "
                   "If there is no mistake, say so."),
    },
    "tutor": {
        "label": "Programming tutor", "color": "#7c3aed",
        "hint": "Ask about a concept, for example: what is recursion?",
        "prompt": ("You are a patient programming tutor. Explain the concept in simple words, then give "
                   "one or two short examples in fenced code blocks, then a small exercise the student can try."),
    },
    "summarize": {
        "label": "Summarize text", "color": "#d97706",
        "hint": "Paste the text you want summarized",
        "prompt": ("You summarize text. Reply with a one-sentence overview, then five to eight short bullet "
                   "points with the key ideas. Do not add facts that are not in the text."),
    },
    "quiz": {
        "label": "Quiz generator", "color": "#0891b2",
        "hint": "Give a topic, for example: Python lists. Add a number if you want, like 8 questions.",
        "prompt": ("You make practice quizzes. Write 5 questions on the topic (or the number the user asks for), "
                   "mixing multiple choice and short answer. Number the questions. "
                   "Put all answers in a separate section called Answers at the end."),
    },
    "notes": {
        "label": "Study notes", "color": "#be185d",
        "hint": "Give a topic, for example: photosynthesis, or the French Revolution",
        "prompt": ("You write study notes. Use short headings, bullet points, key terms in bold, "
                   "and a few lines at the end with the most important things to remember."),
    },
}

COMMON_RULES = (
    "Use simple words. Be short and direct; give more detail only if the user asks. "
    "Use Markdown: put all code in fenced code blocks with the language name. "
    "If the user asks a follow-up, use the earlier messages in this conversation. "
)


def build_system(mode, language):
    text = MODES[mode]["prompt"] + " " + COMMON_RULES
    if language == "English":
        return text + "Reply in English."
    return (text + f"Reply in {language}. Write {language} in its own script (Devanagari). "
            "Keep code, commands and technical keywords in English.")


FIX_PROMPT = """You are a Python code fixer for beginners.
The user sends Python code. Look for the mistakes yourself.
Reply in exactly this format and write nothing else:

[[ERROR]]
Say in one to three simple sentences what is wrong and why it happens.
Mention the line number if you can. Do not use technical error names.
If the code has no mistake, write: No error found.
[[FIX]]
Give two to four short numbered steps that show how to fix it.
[[CODE]]
Write the full corrected Python code only. No markdown fences and no explanation.

Rules: use simple words, keep the answer short, plain text only (no bold, no headings).
Keep the user's own names and style. If the text is not Python code,
write that in the ERROR part and leave the CODE part empty."""


def load_secret_key():
    """Keep the same secret between restarts so people stay logged in."""
    from_env = os.getenv("SECRET_KEY", "").strip()
    if from_env:
        return from_env
    path = os.path.join(BASE_DIR, ".secret_key")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(path, "w") as f:
        f.write(key)
    return key


app = Flask(__name__)
app.secret_key = load_secret_key()
app.config.update(SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=3 * 1024 * 1024,
                  PERMANENT_SESSION_LIFETIME=timedelta(days=30))


# ---------- database ----------
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql, args=(), one=False):
    with closing(get_db()) as conn:
        rows = conn.execute(sql, args).fetchall()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    """Run one write and return the new row id."""
    with closing(get_db()) as conn:
        cursor = conn.execute(sql, args)
        conn.commit()
        return cursor.lastrowid


def add_column(table, column, definition):
    names = [r["name"] for r in query(f"PRAGMA table_info({table})")]
    if column not in names:
        execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def setup_database():
    execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            photo TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )"""
    )
    execute(
        """CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL,
            filename TEXT,
            code TEXT NOT NULL,
            error_text TEXT,
            fingerprint TEXT NOT NULL,
            answer TEXT NOT NULL,
            has_error INTEGER NOT NULL,
            seconds REAL NOT NULL
        )"""
    )
    execute(
        """CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            title TEXT NOT NULL,
            mode TEXT NOT NULL,
            language TEXT NOT NULL
        )"""
    )
    execute(
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    # databases from the older version get the new column
    add_column("checks", "user_id", "INTEGER")
    add_column("chats", "user_id", "INTEGER")
    execute("CREATE INDEX IF NOT EXISTS idx_fingerprint ON checks(fingerprint)")
    execute("CREATE INDEX IF NOT EXISTS idx_checks_user ON checks(user_id)")
    execute("CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id)")
    execute("CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id)")


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- login ----------
@app.before_request
def load_user():
    g.user = None
    if request.endpoint == "static":
        return
    user_id = session.get("uid")
    if user_id:
        g.user = query("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
        if g.user is None:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                return Response("[[FAILED]]Your session ended. Please log in again.", mimetype="text/plain")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def start_session(user_id):
    session.clear()
    session["uid"] = user_id
    session.permanent = True


@app.context_processor
def inject_globals():
    return {"me": g.get("user"), "has_key": HAS_KEY}


# ---------- answer helpers ----------
def clean_code(code):
    code = re.sub(r"^```[a-zA-Z]*\n?", "", code.strip())
    return re.sub(r"\n?```\s*$", "", code)


def split_answer(text):
    """Split the code fixer answer into error, fix and code."""
    parts = {"error": "", "fix": "", "code": ""}
    pieces = re.split(r"\[\[(ERROR|FIX|CODE)\]\]", text)
    if len(pieces) == 1:
        parts["error"] = text.strip()
        return parts
    for i in range(1, len(pieces) - 1, 2):
        parts[pieces[i].lower()] = pieces[i + 1].strip()
    parts["code"] = clean_code(parts["code"])
    return parts


BUSY_WORDS = ("503", "unavailable", "overloaded", "high demand", "429", "quota", "exhausted")


def friendly_error(e):
    text = str(e)
    low = text.lower()
    if any(w in low for w in BUSY_WORDS):
        return "The AI service is very busy right now. Backup models were tried too. Please try again in a minute."
    if "api key" in low or "api_key" in low or "401" in low or "403" in low:
        return "Your API key was not accepted. Check GEMINI_API_KEY in the .env file."
    if "404" in low or "not found" in low:
        return f"The model '{MODEL}' is not available. Change GEMINI_MODEL in the .env file and restart."
    if "timed out" in low or "timeout" in low or "connect" in low:
        return "Could not reach Google. Check your internet connection and try again."
    return "Something went wrong: " + text[:200]


# ---------- gemini ----------
_client = None


def get_client():
    global _client
    if _client is None and HAS_KEY:
        _client = genai.Client(
            api_key=API_KEY, http_options=types.HttpOptions(timeout=45000)
        )
    return _client


def stream_from_gemini(contents, system, temperature=0.3, max_tokens=2000):
    """Yield the answer in small pieces.
    Thinking is turned off for speed. If a model is busy, it is tried once more
    and then the next backup model takes over, so a busy model does not stop the answer."""
    client = get_client()
    base = {"system_instruction": system, "temperature": temperature,
            "max_output_tokens": max_tokens}
    last_error = None
    for model in MODEL_LIST:
        thinking_off = True
        tries = 0
        while tries < 2:
            if thinking_off:
                config = types.GenerateContentConfig(
                    **base, thinking_config=types.ThinkingConfig(thinking_budget=0))
            else:
                config = types.GenerateContentConfig(**base)
            started = False
            try:
                for chunk in client.models.generate_content_stream(
                    model=model, contents=contents, config=config
                ):
                    if chunk.text:
                        started = True
                        yield chunk.text
                return
            except Exception as e:
                last_error = e
                low = str(e).lower()
                if started:
                    raise
                if thinking_off and "think" in low:
                    thinking_off = False  # this model does not allow it, try without
                    continue
                if any(w in low for w in BUSY_WORDS):
                    tries += 1
                    if tries < 2:
                        time.sleep(0.7)
                    continue
                if "404" in low or "not found" in low:
                    break  # this model name does not exist, go to the next one
                raise
    raise last_error


def make_content(role, text):
    return types.Content(role=role, parts=[types.Part(text=text)])


# ---------- page data ----------
def nice_date(text, pattern="%d %b %Y, %H:%M"):
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").strftime(pattern)


def load_checks(user_id, limit):
    items = []
    rows = query("SELECT * FROM checks WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    for row in rows:
        parts = split_answer(row["answer"])
        first_line = next((l.strip() for l in row["code"].splitlines() if l.strip()), "")
        summary = parts["error"].replace("\n", " ")
        bad = bool(row["has_error"])
        items.append({
            "kind": "check", "id": row["id"], "stamp": row["created_at"],
            "date": nice_date(row["created_at"]),
            "title": row["filename"] or first_line[:50] or "Pasted code",
            "tag": "Mistake found" if bad else "Looks good",
            "color": "#dc2626" if bad else "#16a34a",
            "note": summary[:100] + ("..." if len(summary) > 100 else ""),
        })
    return items


def load_chats(user_id, limit):
    rows = query(
        """SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.chat_id = c.id) AS total
           FROM chats c WHERE c.user_id = ? ORDER BY c.id DESC LIMIT ?""", (user_id, limit))
    items = []
    for r in rows:
        mode = MODES.get(r["mode"], MODES["chat"])
        items.append({
            "kind": "chat", "id": r["id"], "stamp": r["created_at"],
            "date": nice_date(r["created_at"]), "title": r["title"],
            "tag": mode["label"], "color": mode["color"],
            "note": f"{r['total']} messages, {r['language']}",
        })
    return items


def load_activity(user_id, limit):
    items = load_checks(user_id, limit) + load_chats(user_id, limit)
    items.sort(key=lambda x: x["stamp"], reverse=True)
    return items[:limit]


def get_stats(user_id):
    row = query("SELECT COUNT(*) AS total, SUM(has_error) AS errors FROM checks WHERE user_id = ?",
                (user_id,), one=True)
    chats = query("SELECT COUNT(*) AS n FROM chats WHERE user_id = ?", (user_id,), one=True)["n"]
    asked = query("""SELECT COUNT(*) AS n FROM messages m JOIN chats c ON c.id = m.chat_id
                     WHERE c.user_id = ? AND m.role = 'user'""", (user_id,), one=True)["n"]
    return {"checks": row["total"] or 0, "errors": row["errors"] or 0, "chats": chats, "asked": asked}


# ---------- sign up, log in, log out ----------
@app.route("/")
def landing():
    if g.user:
        return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="register", error="", form={})


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET" or g.user:
        return redirect(url_for("landing"))
    name = request.form.get("display_name", "").strip()[:40]
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")
    error = ""
    if not USERNAME_RE.match(username):
        error = "Username must be 3 to 20 letters, numbers or underscores."
    elif len(password) < 6:
        error = "Password must have at least 6 characters."
    elif password != confirm:
        error = "The two passwords do not match."
    elif query("SELECT id FROM users WHERE username = ?", (username,), one=True):
        error = "That username is taken. Try another one."
    if not error:
        first_user = query("SELECT COUNT(*) AS n FROM users", one=True)["n"] == 0
        try:
            user_id = execute(
                "INSERT INTO users (username, display_name, password_hash, photo, created_at) "
                "VALUES (?, ?, ?, '', ?)",
                (username, name or username, generate_password_hash(password), now_text()))
        except sqlite3.IntegrityError:
            error = "That username is taken. Try another one."
    if error:
        return render_template("auth.html", mode="register", error=error,
                               form={"username": username, "display_name": name})
    if first_user:  # the first account takes over history saved before accounts existed
        execute("UPDATE checks SET user_id = ? WHERE user_id IS NULL", (user_id,))
        execute("UPDATE chats SET user_id = ? WHERE user_id IS NULL", (user_id,))
    start_session(user_id)
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "GET":
        return render_template("auth.html", mode="login", error="", form={})
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    user = query("SELECT * FROM users WHERE username = ?", (username,), one=True)
    if user is None or not check_password_hash(user["password_hash"], password):
        time.sleep(0.5)
        return render_template("auth.html", mode="login", error="Wrong username or password.",
                               form={"username": username})
    start_session(user["id"])
    return redirect(url_for("dashboard"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- profile ----------
def sniff_image(data):
    """Find the real image type from the first bytes, not from the file name."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] == b"GIF8":
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def remove_photo_file(name):
    if name:
        try:
            os.remove(os.path.join(UPLOAD_DIR, os.path.basename(name)))
        except OSError:
            pass


@app.route("/profile")
@login_required
def profile():
    s = get_stats(g.user["id"])
    return render_template("profile.html", active="profile", stats=s,
                           joined=nice_date(g.user["created_at"], "%d %b %Y"))


@app.route("/avatar")
@login_required
def avatar():
    if not g.user["photo"]:
        abort(404)
    return send_from_directory(UPLOAD_DIR, g.user["photo"], max_age=86400)


@app.route("/profile/update", methods=["POST"])
@login_required
def profile_update():
    name = request.form.get("display_name", "").strip()[:40]
    if not name:
        flash("Please enter a name.", "error")
        return redirect(url_for("profile"))
    photo = g.user["photo"]
    upload = request.files.get("photo")
    if upload and upload.filename:
        data = upload.read(MAX_PHOTO_BYTES + 1)
        ext = sniff_image(data)
        if len(data) > MAX_PHOTO_BYTES:
            flash("The photo is bigger than 2 MB.", "error")
            return redirect(url_for("profile"))
        if ext is None:
            flash("Please choose a PNG, JPG, GIF or WebP image.", "error")
            return redirect(url_for("profile"))
        new_name = f"user{g.user['id']}_{int(time.time())}.{ext}"
        with open(os.path.join(UPLOAD_DIR, new_name), "wb") as f:
            f.write(data)
        remove_photo_file(photo)
        photo = new_name
    execute("UPDATE users SET display_name = ?, photo = ? WHERE id = ?", (name, photo, g.user["id"]))
    flash("Profile saved.", "ok")
    return redirect(url_for("profile"))


@app.route("/profile/photo/remove", methods=["POST"])
@login_required
def profile_photo_remove():
    remove_photo_file(g.user["photo"])
    execute("UPDATE users SET photo = '' WHERE id = ?", (g.user["id"],))
    flash("Photo removed.", "ok")
    return redirect(url_for("profile"))


@app.route("/profile/password", methods=["POST"])
@login_required
def profile_password():
    current = request.form.get("current", "")
    new = request.form.get("new", "")
    confirm = request.form.get("confirm", "")
    if not check_password_hash(g.user["password_hash"], current):
        flash("Your current password is not correct.", "error")
    elif len(new) < 6:
        flash("The new password needs at least 6 characters.", "error")
    elif new != confirm:
        flash("The two new passwords do not match.", "error")
    else:
        execute("UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new), g.user["id"]))
        flash("Password changed.", "ok")
    return redirect(url_for("profile"))


# ---------- pages ----------
@app.route("/dashboard")
@login_required
def dashboard():
    s = get_stats(g.user["id"])
    tiles = [
        {"label": "Code checks", "value": s["checks"], "color": "#2563eb"},
        {"label": "Mistakes found", "value": s["errors"], "color": "#dc2626"},
        {"label": "Chats", "value": s["chats"], "color": "#16a34a"},
        {"label": "Questions asked", "value": s["asked"], "color": "#111827"},
    ]
    return render_template("dashboard.html", active="dashboard", tiles=tiles,
                           modes=MODES, items=load_activity(g.user["id"], 6))


@app.route("/assistant")
@app.route("/assistant/<int:chat_id>")
@login_required
def assistant(chat_id=None):
    mode = request.args.get("mode", "chat")
    language = "English"
    messages = []
    if chat_id:
        chat = query("SELECT * FROM chats WHERE id = ? AND user_id = ?",
                     (chat_id, g.user["id"]), one=True)
        if chat is None:
            abort(404)
        mode, language = chat["mode"], chat["language"]
        messages = query("SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,))
    if mode not in MODES:
        mode = "chat"
    return render_template("assistant.html", active="assistant", modes=MODES, mode=mode,
                           language=language, languages=LANGUAGES,
                           chat_id=chat_id or "", messages=messages)


@app.route("/fix")
@login_required
def fix():
    return render_template("fix.html", active="fix")


@app.route("/history")
@login_required
def history():
    return render_template("history.html", active="history", items=load_activity(g.user["id"], 200))


@app.route("/history/<int:check_id>")
@login_required
def check_detail(check_id):
    row = query("SELECT * FROM checks WHERE id = ? AND user_id = ?", (check_id, g.user["id"]), one=True)
    if row is None:
        abort(404)
    return render_template("detail.html", active="history", row=row,
                           date=nice_date(row["created_at"]), parts=split_answer(row["answer"]))


@app.route("/history/<int:check_id>/delete", methods=["POST"])
@login_required
def delete_check(check_id):
    execute("DELETE FROM checks WHERE id = ? AND user_id = ?", (check_id, g.user["id"]))
    return redirect(url_for("history"))


@app.route("/chats/<int:chat_id>/delete", methods=["POST"])
@login_required
def delete_chat(chat_id):
    execute("DELETE FROM messages WHERE chat_id IN (SELECT id FROM chats WHERE id = ? AND user_id = ?)",
            (chat_id, g.user["id"]))
    execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, g.user["id"]))
    return redirect(url_for("history"))


# ---------- code fixer ----------
@app.route("/api/fix", methods=["POST"])
@login_required
def api_fix():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    source = "upload" if data.get("source") == "upload" else "paste"
    filename = (data.get("filename") or "")[:100]
    user_id = g.user["id"]

    def plain(text):
        return Response(text, mimetype="text/plain")

    if not code:
        return plain("[[FAILED]]Please paste or upload your code first.")
    if len(code) > MAX_CODE_CHARS:
        return plain("[[FAILED]]That is too much text. Please send a smaller piece of code.")
    if get_client() is None:
        return plain("[[FAILED]]API key missing. Put your key in the .env file and restart the app.")

    # the same code was checked before, so answer from the saved copy
    fingerprint = hashlib.sha256((MODEL + "\n" + code + "\n").encode()).hexdigest()
    saved = query("SELECT answer FROM checks WHERE fingerprint = ? AND user_id = ? ORDER BY id DESC LIMIT 1",
                  (fingerprint, user_id), one=True)
    if saved:
        return plain(saved["answer"])

    contents = [make_content("user", "My Python code:\n" + code)]

    def generate():
        started = time.time()
        answer = ""
        try:
            for piece in stream_from_gemini(contents, FIX_PROMPT, 0.2, 2000):
                answer += piece
                yield piece
        except Exception as e:
            yield "\n[[FAILED]]" + friendly_error(e)
            return
        if not answer.strip():
            yield "[[FAILED]]No answer came back. Please try again."
            return
        parts = split_answer(answer)
        has_error = bool(parts["error"]) and not parts["error"].lower().startswith("no error")
        execute(
            """INSERT INTO checks (created_at, source, filename, code, error_text,
                                   fingerprint, answer, has_error, seconds, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now_text(), source, filename, code, "", fingerprint, answer,
             int(has_error), time.time() - started, user_id),
        )

    response = Response(stream_with_context(generate()), mimetype="text/plain")
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Cache-Control"] = "no-cache"
    return response


# ---------- assistant chat ----------
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()
    mode = data.get("mode") if data.get("mode") in MODES else "chat"
    language = data.get("language") if data.get("language") in LANGUAGES else "English"
    user_id = g.user["id"]

    def plain(message):
        return Response(message, mimetype="text/plain")

    if not text:
        return plain("[[FAILED]]Please type a message first.")
    if len(text) > MAX_MESSAGE_CHARS:
        return plain("[[FAILED]]That message is too long. Please send a shorter one.")
    if get_client() is None:
        return plain("[[FAILED]]API key missing. Put your key in the .env file and restart the app.")

    # find the chat, or start a new one
    chat = None
    try:
        chat_id = int(data.get("chat_id") or 0)
    except (TypeError, ValueError):
        chat_id = 0
    if chat_id:
        chat = query("SELECT id FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id), one=True)
    is_new = chat is None
    if is_new:
        title = " ".join(text.split())[:50]
        chat_id = execute(
            "INSERT INTO chats (created_at, title, mode, language, user_id) VALUES (?, ?, ?, ?, ?)",
            (now_text(), title, mode, language, user_id))
    else:
        execute("UPDATE chats SET mode = ?, language = ? WHERE id = ?", (mode, language, chat_id))

    # earlier messages let the AI answer follow-up questions
    earlier = query("SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
                    (chat_id, HISTORY_LIMIT))
    contents = [make_content("user" if r["role"] == "user" else "model", r["content"])
                for r in reversed(earlier)]
    contents.append(make_content("user", text))
    system = build_system(mode, language)

    def generate():
        answer = ""
        try:
            for piece in stream_from_gemini(contents, system, 0.5):
                answer += piece
                yield piece
        except Exception as e:
            yield "\n[[FAILED]]" + friendly_error(e)
            if is_new:
                execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            return
        if not answer.strip():
            yield "[[FAILED]]No answer came back. Please try again."
            if is_new:
                execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            return
        stamp = now_text()
        execute("INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
                (chat_id, text, stamp))
        execute("INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
                (chat_id, answer, stamp))

    response = Response(stream_with_context(generate()), mimetype="text/plain")
    response.headers["X-Chat-Id"] = str(chat_id)
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Cache-Control"] = "no-cache"
    return response


# ---------- if something breaks, show the reason instead of a blank error ----------
@app.errorhandler(Exception)
def show_error(e):
    if isinstance(e, HTTPException):
        return e
    details = traceback.format_exc()
    print(details)
    page = ("<body style='font-family:Arial;padding:24px'><h2>Something went wrong</h2>"
            "<p>Please copy the text below and send it to get help:</p>"
            "<pre style='background:#f4f7fb;padding:16px;white-space:pre-wrap'>"
            + html.escape(details) + "</pre></body>")
    return Response(page, status=500, mimetype="text/html")


setup_database()
if HAS_KEY:
    get_client()  # connect now so the first question is not slower


def find_free_port(start):
    """Use the first port that is really free, so an old copy of the app cannot get in the way."""
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test:
            try:
                test.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def self_check():
    """Open the public pages once at start-up so a problem shows here, not later in the browser."""
    for folder in ("templates", "static"):
        if not os.path.isdir(os.path.join(BASE_DIR, folder)):
            print(f"PROBLEM: the '{folder}' folder is missing next to app.py. "
                  "Unzip the whole project and keep all folders together.")
    client = app.test_client()
    bad = [p for p in ("/", "/login") if client.get(p).status_code != 200]
    print("Page check:", "all pages OK" if not bad else "PROBLEM on " + ", ".join(bad) + " (see the error above)")


if __name__ == "__main__":
    port = find_free_port(PORT)
    url = f"http://127.0.0.1:{port}"
    self_check()
    if not HAS_KEY:
        print("Note: no API key found in the .env file yet.")
    print(f"Dilkash AI is running at {url}  (press Ctrl+C to stop)")
    print("Models in order:", ", ".join(MODEL_LIST))
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
