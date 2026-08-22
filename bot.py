#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shaxsiy AI Yordamchi v4.0 — Xavfsiz va Zavqli Edition
Barcha qo'shimcha kutubxonalar kerak bo'lganda yuklanadi.

Minimal requirements:
    pip install aiogram aiohttp python-dotenv aiosqlite

Qo'shimcha (ixtiyoriy):
    pip install gtts matplotlib cryptography scikit-learn

.env namunasi:
    BOT_TOKEN=...
    ADMIN_PASSWORD=...          # MAJBURIY, default yo'q
    AI_BASE_URL=http://localhost:8000/v1
    AI_API_KEY=not-needed
    CHANNEL_ID=@mening_kanalim  # ixtiyoriy
    TZ=Asia/Tashkent            # eslatmalar shu vaqt zonasida hisoblanadi
"""

import os
import sys
import ast
import asyncio
import base64
import json
import re
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile,
)
from dotenv import load_dotenv

# ============== OPTIONAL IMPORTS (lazy) ==============
_gtts = None
_matplotlib = None
_Fernet = None
_sklearn_tfidf = None
_sklearn_cosine = None


def _get_gtts():
    global _gtts
    if _gtts is None:
        try:
            from gtts import gTTS
            _gtts = gTTS
        except ImportError:
            pass
    return _gtts


def _get_matplotlib():
    global _matplotlib
    if _matplotlib is None:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            _matplotlib = plt
        except ImportError:
            pass
    return _matplotlib


def _get_fernet():
    global _Fernet
    if _Fernet is None:
        try:
            from cryptography.fernet import Fernet
            _Fernet = Fernet
        except ImportError:
            pass
    return _Fernet


def _get_tfidf():
    global _sklearn_tfidf, _sklearn_cosine
    if _sklearn_tfidf is None:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            _sklearn_tfidf = TfidfVectorizer
            _sklearn_cosine = cosine_similarity
        except ImportError:
            pass
    return _sklearn_tfidf, _sklearn_cosine


# ============== LOGGING ==============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ============== KONFIGURATSIYA ==============
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
AI_BASE_URL = os.getenv("AI_BASE_URL")
AI_API_KEY = os.getenv("AI_API_KEY", "not-needed")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DB_PATH = "memory.db"

if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN .env faylida ko'rsatilishi shart!")

if not ADMIN_PASSWORD:
    raise SystemExit(
        "❌ ADMIN_PASSWORD .env faylida ko'rsatilishi shart!\n"
        "Xavfsizlik uchun standart parol olib tashlandi — o'zingiz kuchli parol qo'ying.\n"
        "Masalan: ADMIN_PASSWORD=" + secrets.token_urlsafe(12)
    )

if not AI_BASE_URL:
    raise SystemExit(
        "❌ AI_BASE_URL .env faylida ko'rsatilishi shart!\n"
        "Masalan: AI_BASE_URL=http://localhost:8000/v1"
    )

MODELS = [
    os.getenv("AI_MODEL", "openai/gpt-oss-120b"),
    os.getenv("AI_MODEL_FALLBACK1", "openai/gpt-4o-mini"),
    os.getenv("AI_MODEL_FALLBACK2", "anthropic/claude-3-haiku"),
]

# ============== ZAVQLI QISM: EFFEKTLAR ==============
# Telegram shaxsiy chatlarda xabar effektlari — Premium shart emas, bepul 6 tasi:
EFFECT_FIRE = "5104841245755180586"       # 🔥
EFFECT_PARTY = "5046509860389126442"      # 🎉
EFFECT_HEART = "5159385139981059251"      # ❤️
EFFECT_THUMBS_UP = "5107584321108051014"  # 👍
EFFECT_THUMBS_DOWN = "5104858069142078462"  # 👎
EFFECT_POOP = "5046589136895476101"       # 💩 (xatolar uchun kulgili variant, xohlasangiz)

# ============== AUTH (parol urinish limiti bilan) ==============
authenticated_chats: set[int] = set()
_failed_attempts: dict[int, list[float]] = {}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 daqiqa


def is_authenticated(chat_id: int) -> bool:
    return chat_id in authenticated_chats


def is_locked_out(chat_id: int) -> Optional[int]:
    """Agar bloklangan bo'lsa, qolgan soniyalarni qaytaradi, aks holda None."""
    now = datetime.now().timestamp()
    attempts = _failed_attempts.get(chat_id, [])
    attempts = [t for t in attempts if now - t < LOCKOUT_SECONDS]
    _failed_attempts[chat_id] = attempts
    if len(attempts) >= MAX_ATTEMPTS:
        remaining = LOCKOUT_SECONDS - (now - attempts[0])
        return max(1, int(remaining))
    return None


def register_failed_attempt(chat_id: int):
    _failed_attempts.setdefault(chat_id, []).append(datetime.now().timestamp())


def clear_failed_attempts(chat_id: int):
    _failed_attempts.pop(chat_id, None)


# ============== SHIFRLASH ==============
_ENCRYPTION_KEY: Optional[bytes] = None


def _get_cipher():
    Fernet = _get_fernet()
    if Fernet is None:
        return None
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is None:
        key_path = ".secret_key"
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                _ENCRYPTION_KEY = f.read()
        else:
            _ENCRYPTION_KEY = Fernet.generate_key()
            with open(key_path, "wb") as f:
                f.write(_ENCRYPTION_KEY)
    return Fernet(_ENCRYPTION_KEY)


# ============== SQLITE BAZA (async, aiosqlite) ==============
async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                topic TEXT DEFAULT 'general',
                mood_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                profile_text TEXT NOT NULL DEFAULT '',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                message_count INTEGER DEFAULT 0,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mood_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                score REAL NOT NULL,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS weekly_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                once_at TEXT NOT NULL,
                sent INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS authorized_chats (
                chat_id INTEGER PRIMARY KEY,
                authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Tezlik uchun indexlar
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_chat_topic ON messages(chat_id, topic)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_created ON messages(created_at)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(once_at)")

        await conn.execute("INSERT OR IGNORE INTO daily_profile (id, profile_text) VALUES (1, '')")
        await conn.execute("INSERT OR IGNORE INTO topics (name, description) VALUES ('general', 'Umumiy suhbatlar')")

        # MIGRATSIYA: eski 'reminders' jadvalida 'sent' ustuni bo'lmasligi mumkin
        cur = await conn.execute("PRAGMA table_info(reminders)")
        cols = [row[1] for row in await cur.fetchall()]
        if "sent" not in cols:
            await conn.execute("ALTER TABLE reminders ADD COLUMN sent INTEGER NOT NULL DEFAULT 0")
            logger.info("✅ Migratsiya: reminders.sent ustuni qo'shildi")

        # ESKI BOTDAN XOTIRANI BIR MARTA IMPORT QILISH (agar eski 'memory' jadvali mavjud bo'lsa)
        try:
            cur = await conn.execute("SELECT compressed_text FROM memory WHERE id = 1")
            old_row = await cur.fetchone()
            if old_row and old_row[0] and old_row[0].strip():
                old_text = old_row[0].strip()
                cur = await conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE role = 'system' AND content LIKE '%[ESKI XOTIRA%'"
                )
                already = (await cur.fetchone())[0]
                if already == 0:
                    await conn.execute(
                        "INSERT INTO messages (chat_id, role, content, topic) VALUES (?, ?, ?, ?)",
                        (0, "system", f"[ESKI XOTIRA — AVVALGI BOTDAN]:\n{old_text}", "general")
                    )
                    logger.info(f"✅ Eski xotira import qilindi ({len(old_text)} belgi)")
        except Exception as e:
            logger.info(f"Eski xotira import qilinmadi (jadval yo'q yoki bo'sh): {e}")

        await conn.commit()
    logger.info("✅ Baza v4.0 initializatsiya qilindi (indexlar bilan)")


async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
    return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await conn.commit()


async def load_authorized_chats() -> set[int]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT chat_id FROM authorized_chats")
        rows = await cur.fetchall()
    return {r[0] for r in rows}


async def persist_authorized_chat(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("INSERT OR IGNORE INTO authorized_chats (chat_id) VALUES (?)", (chat_id,))
        await conn.commit()


async def save_message(chat_id: int, role: str, content: str, topic: str = "general", mood: float = None) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO messages (chat_id, role, content, topic, mood_score) VALUES (?, ?, ?, ?, ?)",
            (chat_id, role, content, topic, mood)
        )
        await conn.execute(
            "UPDATE topics SET message_count = message_count + 1, last_active = CURRENT_TIMESTAMP WHERE name = ?",
            (topic,)
        )
        await conn.commit()
        return cur.lastrowid


async def update_message_mood(message_id: int, score: float):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("UPDATE messages SET mood_score = ? WHERE id = ?", (score, message_id))
        await conn.commit()


async def get_recent_messages(chat_id: int, limit: int = 50, topic: str = None) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        if topic and topic != "general":
            cur = await conn.execute(
                "SELECT role, content FROM messages WHERE chat_id = ? AND topic = ? ORDER BY id DESC LIMIT ?",
                (chat_id, topic, limit)
            )
        else:
            cur = await conn.execute(
                "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
                (chat_id, limit)
            )
        rows = await cur.fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


async def get_all_topics(chat_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT DISTINCT topic FROM messages WHERE chat_id = ? ORDER BY topic", (chat_id,))
        rows = await cur.fetchall()
    return [r[0] for r in rows]


async def search_messages(chat_id: int, keyword: str) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT role, content, created_at FROM messages WHERE chat_id = ? AND content LIKE ? ORDER BY id DESC LIMIT 20",
            (chat_id, f"%{keyword}%")
        )
        return await cur.fetchall()


async def get_daily_profile() -> str:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT profile_text FROM daily_profile WHERE id = 1")
        row = await cur.fetchone()
    return row[0] if row else ""


async def update_daily_profile(text: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE daily_profile SET profile_text = ?, last_updated = CURRENT_TIMESTAMP WHERE id = 1",
            (text,)
        )
        await conn.commit()


async def get_stats(chat_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = 'user'", (chat_id,))
        user_count = (await cur.fetchone())[0]
        cur = await conn.execute("SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = 'assistant'", (chat_id,))
        ai_count = (await cur.fetchone())[0]
        cur = await conn.execute("SELECT COUNT(DISTINCT topic) FROM messages WHERE chat_id = ?", (chat_id,))
        topic_count = (await cur.fetchone())[0]
        cur = await conn.execute("SELECT created_at FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (chat_id,))
        last_msg = await cur.fetchone()
    return {
        "user_msgs": user_count,
        "ai_msgs": ai_count,
        "topics": topic_count,
        "last_active": last_msg[0] if last_msg else "Noma'lum"
    }


async def get_mood_history(chat_id: int, days: int = 14) -> list:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT DATE(created_at), AVG(score), COUNT(*) FROM mood_scores "
            "WHERE chat_id = ? AND created_at >= ? GROUP BY DATE(created_at) ORDER BY DATE(created_at)",
            (chat_id, since)
        )
        return await cur.fetchall()


async def save_mood(chat_id: int, score: float, note: str = ""):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO mood_scores (chat_id, score, note) VALUES (?, ?, ?)",
            (chat_id, score, note)
        )
        await conn.commit()


async def get_weekly_summary(week_start: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT summary FROM weekly_summaries WHERE week_start = ?", (week_start,))
        row = await cur.fetchone()
    return row[0] if row else None


async def save_weekly_summary(week_start: str, summary: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO weekly_summaries (week_start, summary) VALUES (?, ?)",
            (week_start, summary)
        )
        await conn.commit()


async def add_reminder(chat_id: int, title: str, content: str, once_at: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO reminders (chat_id, title, content, once_at) VALUES (?, ?, ?, ?)",
            (chat_id, title, content, once_at)
        )
        await conn.commit()


async def get_due_reminders(now_str: str) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT id, chat_id, content FROM reminders WHERE sent = 0 AND once_at <= ?",
            (now_str,)
        )
        return await cur.fetchall()


async def mark_reminder_sent(reminder_id: int):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
        await conn.commit()


async def get_full_history(chat_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT role, content, topic, mood_score, created_at FROM messages WHERE chat_id = ? ORDER BY id",
            (chat_id,)
        )
        return await cur.fetchall()


async def search_relevant_history(chat_id: int, query: str, exclude_last_n: int = 12, top_k: int = 5) -> list:
    """TF-IDF asosida butun tarixdan so'rovga eng mos keladigan eski xabarlarni topadi.
    Bu oxirgi N xabardan tashqaridagi (eskirоq) suhbatlarni qamrab oladi — 'uzoq muddatli xotira'."""
    TfidfVectorizer, cosine_similarity = _get_tfidf()
    if TfidfVectorizer is None:
        return []

    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT id, role, content, created_at FROM messages WHERE chat_id = ? AND role IN ('user','assistant') ORDER BY id",
            (chat_id,)
        )
        rows = await cur.fetchall()

    if len(rows) <= exclude_last_n + 3:
        return []

    # Oxirgi N tasi allaqachon asosiy kontekstda bor — ularni chiqarib tashlaymiz
    candidates = rows[:-exclude_last_n] if exclude_last_n else rows
    if len(candidates) < 3:
        return []

    texts = [r[2] for r in candidates]
    try:
        vectorizer = TfidfVectorizer(max_features=3000)
        matrix = vectorizer.fit_transform(texts + [query])
        sims = cosine_similarity(matrix[-1], matrix[:-1])[0]
        top_idx = sims.argsort()[::-1][:top_k]
        results = []
        for i in top_idx:
            if sims[i] > 0.05:  # butunlay bog'liqsizlarni filtrlash
                r = candidates[i]
                results.append({"role": r[1], "content": r[2], "created_at": r[3]})
        return results
    except Exception as e:
        logger.debug(f"TF-IDF qidiruv xatosi: {e}")
        return []


async def get_messages_since(chat_id: int, since: str) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT role, content, topic, mood_score, created_at FROM messages "
            "WHERE chat_id = ? AND DATE(created_at) >= DATE(?) ORDER BY id",
            (chat_id, since)
        )
        return await cur.fetchall()


async def get_messages_on_date(chat_id: int, date_str: str) -> list:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT role, content, topic, mood_score, created_at FROM messages "
            "WHERE chat_id = ? AND DATE(created_at) = ? ORDER BY id",
            (chat_id, date_str)
        )
        return await cur.fetchall()


# ============== AI CLIENT (MULTI-MODEL FALLBACK) ==============
class NonRetryableAIError(RuntimeError):
    pass


async def ai_chat(messages: list, temperature: float = 0.7, max_tokens: int = 4000, model_idx: int = 0) -> str:
    if model_idx >= len(MODELS):
        raise RuntimeError("Barcha modellar ishlamadi.")

    model = MODELS[model_idx]
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_API_KEY}",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    last_error = None
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    text = await resp.text()

                    if resp.status == 429:
                        wait = min(2 ** attempt * 2, 10)
                        logger.warning(f"[{model}] 429 (urinish {attempt + 1}), {wait}s kutish...")
                        await asyncio.sleep(wait)
                        continue

                    if resp.status in (400, 401, 403, 404):
                        # Bu xatolar qayta urinishda tuzalmaydi — darhol keyingi modelga o'tamiz
                        raise NonRetryableAIError(f"AI API xato {resp.status}: {text[:300]}")

                    if resp.status != 200:
                        raise RuntimeError(f"AI API xato {resp.status}: {text[:500]}")

                    data = json.loads(text)
                    content = data["choices"][0]["message"]["content"].strip()
                    if content:
                        return content
                    raise RuntimeError("Bo'sh javob")

        except NonRetryableAIError as e:
            last_error = e
            break
        except asyncio.TimeoutError:
            last_error = "Timeout (30s)"
            logger.warning(f"[{model}] Timeout — urinish {attempt + 1}")
            if attempt < 2:
                await asyncio.sleep(min(2 ** attempt, 4))
                continue
        except Exception as e:
            last_error = e
            if attempt < 2:
                await asyncio.sleep(min(2 ** attempt, 4))
                continue

    logger.warning(f"[{model}] ishlamadi: {last_error}. Fallback...")
    return await ai_chat(messages, temperature, max_tokens, model_idx + 1)


# ============== MOOD ANALYSIS (BACKGROUND — javobni bloklamaydi) ==============
async def analyze_mood_bg(chat_id: int, message_id: int, text: str):
    """Kayfiyatni fonda tahlil qiladi, AI javobini kutmaydi/sekinlashtirmaydi."""
    prompt = f"""Quyidagi matnning kayfiyatini -1 (juda yomon) dan 1 (juda yaxshi) gacha ball bilan baholang. FAQAT raqam chiqaring, izohsiz.

Matn: {text[:500]}

Ball:"""
    try:
        result = await ai_chat([
            {"role": "system", "content": "Siz sentiment analizchisisiz. Faqat raqam chiqaring."},
            {"role": "user", "content": prompt}
        ], temperature=0.0, max_tokens=10)
        score = max(-1.0, min(1.0, float(re.findall(r"[-+]?[0-9]*\.?[0-9]+", result)[0])))
        await update_message_mood(message_id, score)
        await save_mood(chat_id, score, text[:50])
    except Exception as e:
        logger.debug(f"Mood tahlil xatosi: {e}")


# ============== VOICE GENERATION ==============
async def generate_voice(text: str, lang: str = "uz") -> Optional[str]:
    gTTS = _get_gtts()
    if gTTS is None:
        return None
    filename = f"voice_{datetime.now().strftime('%H%M%S_%f')}.mp3"
    try:
        tts = gTTS(text=text[:500], lang=lang, slow=False)
        await asyncio.to_thread(tts.save, filename)
        return filename
    except Exception as e:
        logger.error(f"Voice xato: {e}")
        return None


# ============== KOD SANDBOX (AST asosida, blocklistdan ko'ra ishonchliroq) ==============
_BLOCKED_NAMES = {
    "eval", "exec", "compile", "__import__", "open", "input", "globals",
    "locals", "vars", "getattr", "setattr", "delattr", "breakpoint",
    "exit", "quit", "help", "memoryview",
}


class _UnsafeCode(Exception):
    pass


def _check_ast_safety(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise _UnsafeCode(f"import taqiqlangan: {ast.dump(node)[:60]}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise _UnsafeCode(f"dunder atributga kirish taqiqlangan: .{node.attr}")
        if isinstance(node, ast.Name) and node.id in _BLOCKED_NAMES:
            raise _UnsafeCode(f"taqiqlangan nom ishlatildi: {node.id}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise _UnsafeCode(f"dunder nomga murojaat taqiqlangan: {node.id}")


def _preexec_limits():
    """POSIX tizimlarda subprocess uchun CPU/xotira chegarasi qo'yadi."""
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    except Exception:
        pass


async def run_code_sandbox(code: str) -> str:
    try:
        tree = ast.parse(code)
        _check_ast_safety(tree)
    except SyntaxError as e:
        return f"❌ Sintaksis xatosi: {e}"
    except _UnsafeCode as e:
        return f"🚫 Bloklangan: {e}\n\n⚠️ Eslatma: bu sandbox faqat beparvo xatolardan himoyalaydi, to'liq izolyatsiya emas."

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-c", code,  # -I: isolated mode, sys.path va env ta'sirini kamaytiradi
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",
            env={"PATH": "/usr/bin:/bin"},
            preexec_fn=_preexec_limits if os.name == "posix" else None,
        )
        try:
            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            out = stdout_data.decode("utf-8", errors="ignore")[:3000]
            err = stderr_data.decode("utf-8", errors="ignore")[:2000]
            result = f"📤 STDOUT:\n{out}" if out else ""
            if err:
                result += f"\n\n⚠️ STDERR:\n{err}"
            return result or "✅ Kod muvaffaqiyatli bajarildi (natija yo'q)"
        except asyncio.TimeoutError:
            proc.kill()
            return "⏰ Kod 10 soniyada bajarilmadi (timeout)"
    except Exception as e:
        return f"❌ Xato: {e}"


# ============== DAILY BACKUP ==============
async def send_daily_backup(chat_id: int):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = await get_messages_on_date(chat_id, yesterday)

    if not rows:
        await bot.send_message(chat_id, f"📭 {yesterday} — suhbat bo'lmagan.")
        return

    await bot.send_chat_action(chat_id, "typing")
    history = "\n".join([f"{'👤' if r[0] == 'user' else '🤖'} {r[1][:120]}" for r in rows])
    prompt = f"Quyidagi suhbatlarni 10 ta qisqa punkt bilan xulosa qiling (emoji bilan):\n\n{history}"
    try:
        summary = await ai_chat([
            {"role": "system", "content": "Kundalik xulosa."},
            {"role": "user", "content": prompt}
        ], temperature=0.4, max_tokens=1500)
    except Exception:
        summary = "[Xulosa yaratilmadi]"

    profile = await get_daily_profile()

    text = (
        f"📅 {yesterday} KUNLIK ARXIV\n"
        f"{'=' * 35}\n\n"
        f"📝 XULOSA:\n{summary}\n\n"
        f"🧠 PROFIL:\n{profile[:600]}{'...' if len(profile) > 600 else ''}\n\n"
        f"📊 Statistika: {len(rows)} ta xabar"
    )

    await bot.send_message(chat_id, text, message_effect_id=EFFECT_PARTY)

    filename = f"backup_{yesterday}_{chat_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"=== {yesterday} KUNLIK ARXIV ===\n\n")
        f.write(f"XULOSA:\n{summary}\n\n")
        f.write("TO'LIQ SUHBATLAR:\n")
        for r in rows:
            mood = f" [kayfiyat: {r[3]}]" if r[3] else ""
            f.write(f"[{r[4]} | {r[2]}]{mood}\n{r[0].upper()}: {r[1]}\n{'=' * 50}\n")

    await bot.send_document(chat_id, FSInputFile(filename), caption=f"📥 {yesterday} to'liq arxiv")
    os.remove(filename)

    await update_learning_profile(chat_id)


# ============== WEEKLY ANALYSIS ==============
async def send_weekly_analysis(chat_id: int):
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    cached = await get_weekly_summary(week_start)
    if cached:
        await bot.send_message(chat_id, f"📊 BU HAFTALIK TAHLIL (kesh):\n\n{cached}")
        return

    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = await get_messages_since(chat_id, since)

    if not rows:
        await bot.send_message(chat_id, "📭 Bu hafta suhbat bo'lmagan.")
        return

    await bot.send_chat_action(chat_id, "typing")
    history = "\n".join([f"{'👤' if r[0] == 'user' else '🤖'} [{r[4]}] {r[1][:150]}" for r in rows])
    prompt = f"""Quyidagi haftalik suhbatlarni CHUQUR tahlil qiling:

1. Foydalanuvchi bu hafta nimalar bilan shug'ullangan?
2. Qanday mavzular ustida ishlagan?
3. Qanday texnologiyalar/qiziqishlar ko'rinib turibdi?
4. Qanday muammolar yoki g'oyalar bor?
5. Keyingi hafta uchun tavsiyalar

Suhbatlar:
{history}

TAHLIL:"""

    try:
        analysis = await ai_chat([
            {"role": "system", "content": "Siz haftalik tahlilchi. Chuqur va foydali tahlil bering."},
            {"role": "user", "content": prompt}
        ], temperature=0.5, max_tokens=3000)

        await save_weekly_summary(week_start, analysis)
        await bot.send_message(
            chat_id, f"📊 BU HAFTALIK CHUQUR TAHLIL\n{'=' * 35}\n\n{analysis}",
            message_effect_id=EFFECT_FIRE
        )
    except Exception as e:
        await bot.send_message(chat_id, f"❌ Tahlil xatosi: {e}")


# ============== MOOD CHART ==============
def _build_mood_chart(rows, filename):
    plt = _get_matplotlib()
    dates = [r[0] for r in rows]
    scores = [r[1] for r in rows]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, scores, marker="o", linewidth=2, color="#4CAF50")
    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    ax.fill_between(dates, scores, 0, alpha=0.2, color="#4CAF50")
    ax.set_title("📈 14 Kunlik Kayfiyat Dinamikasi", fontsize=14, fontweight="bold")
    ax.set_xlabel("Sana", fontsize=10)
    ax.set_ylabel("Kayfiyat (-1 dan 1 gacha)", fontsize=10)
    ax.set_ylim(-1.1, 1.1)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()


async def generate_mood_chart(chat_id: int) -> Optional[str]:
    if _get_matplotlib() is None:
        return None

    rows = await get_mood_history(chat_id, days=14)
    if len(rows) < 2:
        return None

    filename = f"mood_chart_{chat_id}.png"
    await asyncio.to_thread(_build_mood_chart, rows, filename)
    return filename


# ============== LEARNING PROFILE ==============
async def update_learning_profile(chat_id: int):
    recent = await get_recent_messages(chat_id, limit=40)
    if len(recent) < 5:
        return

    old_profile = await get_daily_profile()
    history_text = "\n".join([
        f"{'User' if m['role'] == 'user' else 'AI'}: {m['content'][:250]}"
        for m in recent[-30:]
    ])

    prompt = f"""Siz foydalanuvchining shaxsiy AI yordamchisisiz. Quyidagi suhbatlar asosida FOYDALANUVCHI HAQIDA yangi ma'lumotlarni o'rganing va mavjud profilni YANGILANG (eskisini o'chirmang, faqat yangi ma'lumot bilan boyiting).

ESKI PROFIL:
{old_profile if old_profile else '[Hali profil yoq]'}

OXIRGI SUHBATLAR:
{history_text}

QOIDALAR:
1. Profilni QUYIDAGI TUZILGAN FORMATDA yozing (bo'limlarni saqlang, faqat mazmunni yangilang):

## LOYIHALAR VA TEXNOLOGIYALAR
(foydalanuvchi ishtirok etgan loyihalar, texnologiyalar, VPS/server tafsilotlari va h.k.)

## AFZALLIKLAR VA USLUB
(qisqa/batafsil javob, til, muloqot uslubi va h.k.)

## MUHIM FAKTLAR
(ism, kasb, doimiy takrorlanadigan mavzular, hal qilingan muammolar)

## FAOL VAQT VA ODATLAR
(qachon faol, qanday so'rovlarni ko'p beradi)

2. Eski ma'lumotni O'CHIRMANG, faqat eskirgan/o'zgargan qismini yangilang, yangi faktlarni qo'shing
3. HECH QANDAY qo'shimcha izohsiz, FAQAT profil matnini chiqaring (yuqoridagi 4 bo'lim bilan)

YANGI PROFIL:"""

    try:
        new_profile = await ai_chat([
            {"role": "system", "content": "Siz profil analizchisisiz. Faqat tuzilgan profil matnini chiqaring."},
            {"role": "user", "content": prompt}
        ], temperature=0.3, max_tokens=2500)
        await update_daily_profile(new_profile)
        logger.info("✅ Learning profile yangilandi")
    except Exception as e:
        logger.error(f"Profil yangilash xatosi: {e}")


async def deep_memory_compress(chat_id: int):
    """Haftalik chuqur siqish: BUTUN tarixni katta kontekstli modelga berib,
    profilni to'liq qayta yozdiradi — hech qanday ma'lumot yo'qolmasligi uchun."""
    rows = await get_full_history(chat_id)
    if len(rows) < 15:
        return

    old_profile = await get_daily_profile()
    # Katta hajmdagi tarixni ham cheklab yuboramiz (token limitidan chiqmaslik uchun)
    history_text = "\n".join([
        f"{'User' if r[0] == 'user' else 'AI' if r[0] == 'assistant' else 'SYSTEM'}: {r[1][:300]}"
        for r in rows[-200:]
    ])

    prompt = f"""Siz foydalanuvchining BUTUN suhbat tarixini tahlil qilib, uning haqida ENG TO'LIQ va ZICH profilni yaratishingiz kerak.

ESKI PROFIL (saqlanishi kerak bo'lgan ma'lumotlar):
{old_profile if old_profile else '[Hali profil yoq]'}

BUTUN TARIX (oxirgi 200 xabar):
{history_text}

VAZIFA: Yuqoridagi barcha ma'lumotni birlashtirib, hech narsani yo'qotmasdan, quyidagi tuzilgan formatda ENG TO'LIQ profilni yozing:

## LOYIHALAR VA TEXNOLOGIYALAR
## AFZALLIKLAR VA USLUB
## MUHIM FAKTLAR
## FAOL VAQT VA ODATLAR
## TARIX BO'YICHA XULOSA (qisqa, lekin barcha muhim voqealarni qamrab oladi)

FAQAT profil matnini chiqaring, izohsiz."""

    try:
        # Katta kontekstli model bilan (agar mavjud bo'lsa) — chuqur tahlil uchun
        big_model = os.getenv("AI_MODEL_BIG_CONTEXT", MODELS[0])
        new_profile = await ai_chat([
            {"role": "system", "content": "Siz chuqur profil-siqish tizimisiz. Faqat tuzilgan profil matnini chiqaring."},
            {"role": "user", "content": prompt}
        ], temperature=0.2, max_tokens=3500, model_idx=0)
        await update_daily_profile(new_profile)
        logger.info(f"✅ Haftalik chuqur xotira siqish bajarildi (chat_id={chat_id})")
    except Exception as e:
        logger.error(f"Chuqur xotira siqish xatosi: {e}")


# ============== ENCRYPTED EXPORT ==============
async def export_encrypted(chat_id: int) -> Optional[str]:
    cipher = _get_cipher()
    if cipher is None:
        return None

    rows = await get_full_history(chat_id)
    data = {
        "exported_at": datetime.now().isoformat(),
        "chat_id": chat_id,
        "messages": [
            {"role": r[0], "content": r[1], "topic": r[2], "mood": r[3], "time": r[4]}
            for r in rows
        ],
        "profile": await get_daily_profile(),
    }

    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    encrypted = cipher.encrypt(json_bytes)

    filename = f"encrypted_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
    with open(filename, "wb") as f:
        f.write(encrypted)
    return filename


# ============== MIRROR TO CHANNEL ==============
async def mirror_to_channel(text: str, document_path: str = None):
    if not CHANNEL_ID:
        return
    try:
        if document_path:
            await bot.send_document(CHANNEL_ID, FSInputFile(document_path), caption=text[:1024])
        else:
            await bot.send_message(CHANNEL_ID, text[:4096])
    except Exception as e:
        logger.error(f"Mirror xato: {e}")


# ============== YORDAMCHI ==============
async def send_long_message(chat_id: int, text: str, effect_id: str = None):
    try:
        if len(text) <= 4096:
            await bot.send_message(chat_id, text, message_effect_id=effect_id)
        else:
            filename = f"result_{datetime.now().strftime('%H%M%S_%f')}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text)
            await bot.send_document(chat_id, FSInputFile(filename), caption="📄 Natija juda uzun")
            os.remove(filename)
    except Exception as e:
        logger.error(f"send_long_message xato: {e}")


async def status_indicator(chat_id: int, action: str = "typing"):
    """typing / upload_photo / record_voice / upload_document — kontekstga mos ko'rsatkich."""
    while True:
        try:
            await bot.send_chat_action(chat_id, action)
            await asyncio.sleep(4)
        except Exception:
            break


# ============== CRON SCHEDULER ==============
async def check_reminders():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:00")
    due = await get_due_reminders(now_str)
    for reminder_id, chat_id, content in due:
        try:
            await bot.send_message(chat_id, f"⏰ ESLATMA!\n\n{content}", message_effect_id=EFFECT_PARTY)
        except Exception as e:
            logger.error(f"Eslatma yuborish xatosi: {e}")
        finally:
            await mark_reminder_sent(reminder_id)


async def cron_scheduler():
    last_daily_date = None
    last_weekly_date = None

    while True:
        now = datetime.now()
        try:
            await check_reminders()
        except Exception as e:
            logger.error(f"Reminder cron xato: {e}")

        today = now.strftime("%Y-%m-%d")
        if now.hour == 9 and now.minute == 0 and last_daily_date != today:
            for chat_id in list(authenticated_chats):
                try:
                    await send_daily_backup(chat_id)
                    await mirror_to_channel(f"📅 Daily backup: {today}")
                except Exception as e:
                    logger.error(f"Daily cron xato ({chat_id}): {e}")
            last_daily_date = today

        if now.weekday() == 0 and now.hour == 9 and now.minute == 30 and last_weekly_date != today:
            for chat_id in list(authenticated_chats):
                try:
                    await send_weekly_analysis(chat_id)
                    await deep_memory_compress(chat_id)
                    await mirror_to_channel(f"📊 Weekly analysis: {today}")
                except Exception as e:
                    logger.error(f"Weekly cron xato ({chat_id}): {e}")
            last_weekly_date = today

        await asyncio.sleep(30)


# ============== TELEGRAM BOT ==============
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

current_topics: dict[int, str] = {}
voice_mode: set[int] = set()


def _feature_status() -> str:
    features = []
    features.append(f"🧠 AI: {'✅' if MODELS[0] else '❌'}")
    features.append(f"🔊 Voice (gTTS): {'✅' if _get_gtts() else '❌ pip install gtts'}")
    features.append(f"📊 Charts (matplotlib): {'✅' if _get_matplotlib() else '❌ pip install matplotlib'}")
    features.append(f"🔐 Encrypt (cryptography): {'✅' if _get_fernet() else '❌ pip install cryptography'}")
    features.append(f"🧠 Uzoq muddatli xotira (scikit-learn): {'✅' if _get_tfidf()[0] else '❌ pip install scikit-learn'}")
    features.append(f"📡 Mirror: {'✅' if CHANNEL_ID else '❌ CHANNEL_ID yoq'}")
    return "\n".join(features)


# ---------- AUTH GATE (parol) ----------
@dp.message(F.text, lambda m: not is_authenticated(m.chat.id))
async def handle_password(message: Message):
    chat_id = message.chat.id

    locked_seconds = is_locked_out(chat_id)
    if locked_seconds:
        minutes = locked_seconds // 60 + 1
        await message.answer(f"🔒 Juda ko'p noto'g'ri urinish. {minutes} daqiqadan keyin qayta urinib ko'ring.")
        return

    if message.text == ADMIN_PASSWORD:
        authenticated_chats.add(chat_id)
        clear_failed_attempts(chat_id)
        await persist_authorized_chat(chat_id)
        await message.answer(
            "✅ Parol tasdiqlandi!\n\n"
            "👋 Xush kelibsiz, egam!\n"
            "/start — Bosh menu",
            message_effect_id=EFFECT_HEART,
        )
    else:
        register_failed_attempt(chat_id)
        remaining = MAX_ATTEMPTS - len(_failed_attempts.get(chat_id, []))
        if remaining > 0:
            await message.answer(f"❌ Noto'g'ri parol. Qolgan urinishlar: {remaining}")
        else:
            await message.answer(f"🔒 Urinishlar tugadi. {LOCKOUT_SECONDS // 60} daqiqaga bloklandingiz.")


@dp.message(Command("start"))
async def cmd_start(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        await message.answer("🔐 Parolni kiriting:")
        return

    stats = await get_stats(chat_id)
    features = _feature_status()

    await message.answer(
        f"👋 Xush kelibsiz, egam!\n\n"
        f"📊 Statistika:\n"
        f"• Sizning xabarlaringiz: {stats['user_msgs']}\n"
        f"• AI javoblari: {stats['ai_msgs']}\n"
        f"• Mavzular: {stats['topics']}\n\n"
        f"⚙️ Funksiyalar:\n{features}\n\n"
        f"🛠 Komandalar:\n"
        f"/tarix [N] — Suhbat tarixi\n"
        f"/qidir <so'z> — Eski suhbatlarni qidirish\n"
        f"/mavzu <nomi> — Yangi mavzu\n"
        f"/mavzular — Barcha mavzular\n"
        f"/men — Profilingiz\n"
        f"/voice — Ovozli rejim ON/OFF\n"
        f"/run <kod> — Python kod bajarish (cheklangan sandbox)\n"
        f"/kayfiyat — 14 kunlik kayfiyat grafigi\n"
        f"/eslatma <YYYY-MM-DD> <HH:MM> <matn> — Eslatma qo'shish\n"
        f"/haftalik — Haftalik chuqur tahlil\n"
        f"/xotira — Kunlik xotira (qo'lda)\n"
        f"/chuqurxotira — Butun tarixni chuqur siqish (qo'lda)\n"
        f"/export — Shifrlangan eksport\n"
        f"/stikerid — Forward qilingan stikerning file_id'sini ko'rsatadi\n"
        f"/clear — Sessiyani tozalash\n"
        f"/status — Bot holati",
        message_effect_id=EFFECT_PARTY,
    )


@dp.message(Command("status"))
async def cmd_status(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        await message.answer("🔐 Avval parol:")
        return

    stats = await get_stats(chat_id)
    profile = await get_daily_profile()
    vm = "🔊 ON" if chat_id in voice_mode else "🔇 OFF"
    features = _feature_status()

    await message.answer(
        f"📊 Bot holati:\n"
        f"✅ Bot: Online\n"
        f"🧠 Model: {MODELS[0]}\n"
        f"🔄 Fallback: {', '.join(MODELS[1:])}\n"
        f"💾 Jami xabarlar: {stats['user_msgs'] + stats['ai_msgs']}\n"
        f"📁 Mavzular: {stats['topics']}\n"
        f"🧬 Profil: {len(profile)} belgi\n"
        f"🔊 Ovozli rejim: {vm}\n"
        f"⏰ Avtomatik xotira: Har kuni 09:00\n"
        f"📊 Haftalik tahlil: Dushanba 09:30\n\n"
        f"⚙️ Funksiyalar:\n{features}"
    )


@dp.message(Command("voice"))
async def cmd_voice(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    if _get_gtts() is None:
        await message.answer("❌ gTTS o'rnatilmagan.\n`pip install gtts` deb o'rnating.")
        return
    if chat_id in voice_mode:
        voice_mode.discard(chat_id)
        await message.answer("🔇 Ovozli rejim O'CHIRILDI.")
    else:
        voice_mode.add(chat_id)
        await message.answer("🔊 Ovozli rejim YOQILDI.")


@dp.message(Command("run"))
async def cmd_run(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.answer(
            "💻 Foydalanish: /run <python kodi>\n"
            "Masalan: /run print(2+2)\n\n"
            "⚠️ import, fayl ochish, eval/exec va dunder atributlar bloklangan.\n"
            "Bu 100% xavfsiz izolyatsiya emas — faqat shaxsiy, ishonchli foydalanish uchun."
        )
        return

    code = args[1]
    if code.startswith("```"):
        code = re.sub(r"^```(?:python)?\n?", "", code)
        code = re.sub(r"\n?```$", "", code)

    safe_preview = code[:300].replace("`", "'")
    await message.answer(f"⏳ Kod bajarilmoqda...\n\n{safe_preview}")
    result = await run_code_sandbox(code)
    safe_result = result.replace("```", "'''")
    await send_long_message(chat_id, f"💻 NATIJA:\n\n{safe_result}")


@dp.message(Command("kayfiyat"))
async def cmd_mood(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    if _get_matplotlib() is None:
        await message.answer("❌ Matplotlib o'rnatilmagan.\n`pip install matplotlib` deb o'rnating.")
        return

    status_task = asyncio.create_task(status_indicator(chat_id, "upload_photo"))
    try:
        chart_path = await generate_mood_chart(chat_id)
    finally:
        status_task.cancel()

    if chart_path:
        await message.answer_photo(FSInputFile(chart_path), caption="📈 14 kunlik kayfiyat dinamikasi")
        os.remove(chart_path)
    else:
        await message.answer("📭 Hali yetarlicha kayfiyat ma'lumoti yo'q. Bir nechta suhbatdan keyin ko'rinadi.")


@dp.message(Command("eslatma"))
async def cmd_reminder(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    text = message.text[len("/eslatma "):].strip() if len(message.text) > len("/eslatma") else ""
    if not text:
        await message.answer(
            "⏰ Foydalanish:\n"
            "/eslatma 2026-08-22 15:00 Uchrashuvga borish\n\n"
            "Format qat'iy: YYYY-MM-DD HH:MM matn"
        )
        return

    parts = text.split(" ", 2)
    if len(parts) < 3:
        await message.answer("❌ Format noto'g'ri. Masalan: /eslatma 2026-08-22 15:00 Uchrashuv")
        return

    date_str, time_str, reminder_text = parts[0], parts[1], parts[2]

    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ Sana/vaqt formati noto'g'ri. Masalan: 2026-08-22 15:00")
        return

    if dt <= datetime.now():
        await message.answer("❌ Bu vaqt allaqachon o'tib ketgan. Kelajakdagi vaqtni kiriting.")
        return

    once_at = dt.strftime("%Y-%m-%d %H:%M:00")
    await add_reminder(chat_id, reminder_text[:50], reminder_text, once_at)
    await message.answer(f"✅ Eslatma saqlandi!\n📅 {date_str} {time_str}\n📝 {reminder_text}",
                          message_effect_id=EFFECT_THUMBS_UP)


@dp.message(Command("haftalik"))
async def cmd_weekly(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    await message.answer("⏳ Haftalik tahlil tayyorlanmoqda...")
    await send_weekly_analysis(chat_id)


@dp.message(Command("tarix"))
async def cmd_history(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    args = message.text.split(" ", 1)
    limit = 20
    if len(args) > 1 and args[1].isdigit():
        limit = min(int(args[1]), 100)

    msgs = await get_recent_messages(chat_id, limit=limit)
    if not msgs:
        await message.answer("📭 Hali xabarlar yo'q.")
        return

    text = f"📜 Oxirgi {len(msgs)} ta xabar:\n\n"
    for m in msgs:
        prefix = "👤" if m['role'] == 'user' else '🤖'
        content = m['content'][:300] + "..." if len(m['content']) > 300 else m['content']
        text += f"{prefix} {content}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 To'liq tarixni yuklash", callback_data="download_full_history")]
    ])
    await message.answer(text[:4000], reply_markup=kb)


@dp.callback_query(F.data == "download_full_history")
async def download_history(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    if not is_authenticated(chat_id):
        await callback.answer("🔐 Avval parol kiriting.", show_alert=True)
        return
    await callback.answer()

    rows = await get_full_history(chat_id)

    filename = f"full_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{chat_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("=== TO'LIQ SUHBAT TARIXI ===\n\n")
        for r in rows:
            mood = f" [kayfiyat: {r[3]}]" if r[3] else ""
            f.write(f"[{r[4]} | {r[2]}]{mood}\n{r[0].upper()}: {r[1]}\n{'=' * 50}\n")

    await callback.message.answer_document(
        FSInputFile(filename),
        caption=f"📥 To'liq tarix ({len(rows)} ta xabar)"
    )
    os.remove(filename)


@dp.message(Command("qidir"))
async def cmd_search(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.answer("🔍 Foydalanish: /qidir <so'z>\nMasalan: /qidir docker")
        return

    keyword = args[1]
    results = await search_messages(chat_id, keyword)

    if not results:
        await message.answer(f"🔍 '{keyword}' bo'yicha hech narsa topilmadi.")
        return

    text = f"🔍 '{keyword}' bo'yicha {len(results)} ta natija:\n\n"
    for r in results[:10]:
        role_emoji = "👤" if r[0] == 'user' else '🤖'
        content = r[1][:200] + "..." if len(r[1]) > 200 else r[1]
        text += f"{role_emoji} [{r[2]}]\n{content}\n\n"

    await message.answer(text[:4000])


@dp.message(Command("mavzu"))
async def cmd_topic(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.answer("📂 /mavzu <nomi> — Masalan: /mavzu loyiha_alfa")
        return

    topic = args[1].strip().lower().replace(" ", "_")
    current_topics[chat_id] = topic

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("INSERT OR IGNORE INTO topics (name) VALUES (?)", (topic,))
        await conn.commit()

    await message.answer(f"✅ Yangi mavzu: '{topic}'\nUmumiy suhbatga qaytish: /mavzu general")


@dp.message(Command("mavzular"))
async def cmd_topics(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    topics = await get_all_topics(chat_id)
    current = current_topics.get(chat_id, "general")

    text = "📂 Mavzular:\n\n"
    for t in topics:
        marker = "▶️" if t == current else "•"
        text += f"{marker} {t}\n"

    await message.answer(text or "📭 Hali mavzular yo'q.")


@dp.message(Command("men"))
async def cmd_profile(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    profile = await get_daily_profile()
    if not profile.strip():
        await message.answer("🧬 Hali profilingiz shakllanmagan.")
        return

    await message.answer(f"🧬 SIZNING AI PROFILINGIZ:\n{'=' * 30}\n\n{profile}")


@dp.message(Command("xotira"))
async def cmd_memory(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    await message.answer("⏳ Kunlik xotira tayyorlanmoqda...")
    await send_daily_backup(chat_id)


@dp.message(Command("chuqurxotira"))
async def cmd_deep_memory(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    await message.answer("🧠 Butun tarix chuqur tahlil qilinib, profil qayta yozilmoqda... Bu biroz vaqt olishi mumkin.")
    await deep_memory_compress(chat_id)
    await message.answer("✅ Chuqur xotira siqish yakunlandi. /men orqali yangi profilni ko'ring.")


@dp.message(Command("export"))
async def cmd_export(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    if _get_fernet() is None:
        await message.answer("❌ Cryptography o'rnatilmagan.\n`pip install cryptography` deb o'rnating.")
        return

    status_task = asyncio.create_task(status_indicator(chat_id, "upload_document"))
    try:
        await message.answer("🔐 Ma'lumotlar shifrlanmoqda...")
        filename = await export_encrypted(chat_id)
        if filename:
            await message.answer_document(
                FSInputFile(filename),
                caption="🔐 Shifrlangan eksport. Kalit .secret_key faylida saqlanadi."
            )
            os.remove(filename)
        else:
            await message.answer("❌ Shifrlashda xato.")
    except Exception as e:
        await message.answer(f"❌ Eksport xatosi: {e}")
    finally:
        status_task.cancel()


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    current_topics.pop(chat_id, None)
    await message.answer("🧹 Sessiya tozalandi. Baza xotirasi o'chirilmadi.")


@dp.message(Command("stikerid"))
async def cmd_stickerid(message: Message):
    """Forward qilingan yoki yuborilgan stikerning file_id'sini ko'rsatadi —
    o'zingiz yoqtirgan stikerlarni botga qo'shish uchun qulay."""
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    await message.answer("📎 Endi menga bir dona stiker yuboring — file_id'sini qaytaraman.")


@dp.message(F.sticker)
async def handle_sticker(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    await message.answer(f"🆔 file_id:\n`{message.sticker.file_id}`", parse_mode="Markdown")


# ============== RASM TUSHUNISH (token oqmasligi uchun base64 orqali) ==============
@dp.message(F.photo)
async def handle_photo(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        await message.answer("🔐 Avval parol:")
        return

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes_io = await bot.download_file(file.file_path)
    b64_image = base64.b64encode(file_bytes_io.read()).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64_image}"

    caption = message.caption or "Bu rasmda nima bor?"

    messages = [
        {"role": "system", "content": "Siz rasm tahlilchisisiz. Rasmni tushuntiring."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": caption},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]
        }
    ]

    status_task = asyncio.create_task(status_indicator(chat_id, "typing"))
    try:
        response = await ai_chat(messages, temperature=0.5)
        await save_message(chat_id, "user", f"[RASM] {caption}")
        await save_message(chat_id, "assistant", response)

        if chat_id in voice_mode:
            voice_path = await generate_voice(response)
            if voice_path:
                await bot.send_voice(chat_id, FSInputFile(voice_path), caption="🔊 AI javobi")
                os.remove(voice_path)
            else:
                await send_long_message(chat_id, response)
        else:
            await send_long_message(chat_id, response)

        await mirror_to_channel(f"📷 Rasm tahlili:\n{caption[:100]}\n\nAI: {response[:200]}")

    except Exception as e:
        logger.error(f"Rasm tahlil xatosi: {e}")
        await message.answer(f"❌ Rasmni tushunishda xato. Model vision qo'llamasligi mumkin: {e}")
    finally:
        status_task.cancel()


# ============== ASOSIY XABAR HANDLER ==============
@dp.message(F.text)
async def handle_message(message: Message):
    chat_id = message.chat.id
    user_text = message.text

    if user_text.startswith("/"):
        return

    topic = current_topics.get(chat_id, "general")
    user_msg_id = await save_message(chat_id, "user", user_text, topic)
    # Kayfiyat fonda tahlil qilinadi — javobni sekinlashtirmaydi
    asyncio.create_task(analyze_mood_bg(chat_id, user_msg_id, user_text))

    profile = await get_daily_profile()
    recent_msgs = await get_recent_messages(chat_id, limit=12, topic=topic)
    # Har bir xabarni ham cheklab qo'yamiz — token limitidan chiqib ketmaslik uchun
    for m in recent_msgs:
        if len(m["content"]) > 1500:
            m["content"] = m["content"][:1500] + "... [qisqartirildi]"
    if len(profile) > 1500:
        profile = profile[:1500] + "... [qisqartirildi]"

    # UZOQ MUDDATLI XOTIRA: butun tarixdan hozirgi savolga mos keladigan eski xabarlarni topamiz
    relevant_history = await search_relevant_history(chat_id, user_text, exclude_last_n=12, top_k=5)
    relevant_text = ""
    if relevant_history:
        relevant_text = "\n\nESKI SUHBATLARDAN BOG'LIQ QISMLAR (uzoq muddatli xotiradan topildi):\n"
        for m in relevant_history:
            role_label = "Foydalanuvchi" if m["role"] == "user" else "Siz"
            content = m["content"][:300]
            relevant_text += f"[{m['created_at']}] {role_label}: {content}\n"

    system_prompt = f"""Siz foydalanuvchining SHAXSIY va YAQIN AI yordamchisisiz.

SIZNING VAZIFALARINGIZ:
1. Foydalanuvchining avvalgi suhbatlaridan kontekstni tushunib, mantiqiy davom ettiring
2. Uning so'rovlari ustida FOCUS qiling, boshqa narsalarga chalg'imang
3. O'zbek tilida javob bering (agar boshqa til talab qilinmasa)
4. Qisqa va aniq bo'ling, lekin kerakli ma'lumotni to'liq bering
5. Agar pastda "ESKI SUHBATLARDAN BOG'LIQ QISMLAR" bo'limi bo'lsa, undan albatta foydalaning — bu sizning uzoq muddatli xotirangiz, foydalanuvchi avval nima haqida gaplashganini eslatib turadi

SIZNING PROFILINGIZ:
{profile if profile else '[Hali profil shakllanmagan]'}
{relevant_text}
Joriy mavzu: {topic}
"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(recent_msgs)
    messages.append({"role": "user", "content": user_text})

    action = "record_voice" if chat_id in voice_mode else "typing"
    status_task = asyncio.create_task(status_indicator(chat_id, action))
    notify_task = asyncio.create_task(_notify_if_slow(chat_id))

    try:
        assistant_text = await ai_chat(messages, temperature=0.7)
        notify_task.cancel()
        await save_message(chat_id, "assistant", assistant_text, topic)

        # Profilni yangilash (har 10 xabardan keyin — zichroq xotira uchun)
        stats = await get_stats(chat_id)
        if (stats['user_msgs'] + stats['ai_msgs']) % 10 == 0:
            asyncio.create_task(update_learning_profile(chat_id))

        if chat_id in voice_mode:
            voice_path = await generate_voice(assistant_text)
            if voice_path:
                await bot.send_voice(chat_id, FSInputFile(voice_path), caption="🔊 AI javobi")
                os.remove(voice_path)
                if len(assistant_text) > 500:
                    await send_long_message(chat_id, assistant_text)
            else:
                await send_long_message(chat_id, assistant_text)
        else:
            await send_long_message(chat_id, assistant_text)

        if len(assistant_text) > 100:
            await mirror_to_channel(f"💬 Suhbat:\n👤: {user_text[:100]}\n🤖: {assistant_text[:200]}")

    except RuntimeError as e:
        notify_task.cancel()
        status_task.cancel()
        if "429" in str(e) or "band" in str(e).lower():
            await message.answer("⏳ AI hozircha band. 30 soniyadan keyin avtomatik qayta urinib ko'raman...")
            await asyncio.sleep(30)
            try:
                assistant_text = await ai_chat(messages, temperature=0.7)
                await save_message(chat_id, "assistant", assistant_text, topic)
                await send_long_message(chat_id, assistant_text)
            except Exception as e2:
                await message.answer(f"❌ AI hali ham band: {e2}")
        else:
            await message.answer(f"❌ AI xatolik: {e}")
    except Exception as e:
        notify_task.cancel()
        status_task.cancel()
        logger.error(f"AI suhbat xato: {e}")
        await message.answer(f"❌ Xatolik: {e}")
    finally:
        status_task.cancel()
        notify_task.cancel()


async def _notify_if_slow(chat_id: int):
    """Agar javob 8 soniyadan ko'p ketsa, foydalanuvchini xabardor qiladi."""
    await asyncio.sleep(8)
    try:
        await bot.send_message(chat_id, "⏳ AI javob tayyorlanmoqda... Bu 10-30 soniya olishi mumkin.")
    except Exception:
        pass


# ============== MAIN ==============
async def main():
    global authenticated_chats
    await init_db()
    authenticated_chats = await load_authorized_chats()
    logger.info(f"✅ Bot ishga tushdi (v4.0). Avvaldan avtorizatsiya qilingan chatlar: {len(authenticated_chats)}")

    asyncio.create_task(cron_scheduler())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
