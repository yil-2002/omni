#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shaxsiy AI Yordamchi v6.0 — Premium & Professional Edition
- Voice (gTTS) butunlay O'CHIRILDI
- To'liq Inline Keyboard (Menyu) tizimi
- Zichlangan xotira (/xotira) qo'shildi
- Professional Loading va Status animatsiyalari
- OmniRouter Combo uchun optimallashtirilgan
"""

import os
import sys
import asyncio
import sqlite3
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import contextmanager

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile,
)
from dotenv import load_dotenv

# ============== OPTIONAL IMPORTS ==============
_matplotlib = None
_Fernet = None

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
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Yil-2002")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "not-needed")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DB_PATH = os.getenv("DB_PATH", "memory.db")

OWNER_CHAT_ID: Optional[int] = None

MODELS = [os.getenv("AI_MODEL", "openai/gpt-oss-120b")]

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN .env da ko'rsatilishi shart!")

# ============== AUTH ==============
authenticated_chats = set()

def is_authenticated(chat_id: int) -> bool:
    return chat_id in authenticated_chats

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

# ============== DB KONTEXT-MENEDJER ==============
@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()

def _exec(cur, sql: str, params=()):
    try:
        cur.execute(sql, params)
    except sqlite3.Error as e:
        logger.error(f"SQL error: {e} | SQL: {sql} | Params: {params}")
        raise

# ============== SOZLAMALAR ==============
def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

def set_setting(key: str, value: str):
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

# ============== BAZA + XOTIRA ==============
def init_db():
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            topic TEXT DEFAULT 'general',
            mood_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS daily_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            profile_text TEXT NOT NULL DEFAULT '',
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            message_count INTEGER DEFAULT 0,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS mood_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            score REAL NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS weekly_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            once_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        cur.execute("""CREATE INDEX IF NOT EXISTS idx_msg_chat_topic ON messages(chat_id, topic)""")
        cur.execute("""CREATE INDEX IF NOT EXISTS idx_msg_created ON messages(created_at)""")
        cur.execute("""CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(once_at)""")

        try:
            cur.execute("SELECT compressed_text FROM memory WHERE id = 1")
            old_row = cur.fetchone()
            if old_row and old_row[0] and old_row[0].strip():
                old_text = old_row[0].strip()
                cur.execute("SELECT COUNT(*) FROM messages WHERE role = 'system' AND content LIKE ?", ("%[ESKI XOTIRA]%",))
                if cur.fetchone()[0] == 0:
                    _exec(cur, "INSERT INTO messages (chat_id, role, content, topic) VALUES (?, ?, ?, ?)", (0, "system", f"[ESKI XOTIRA — AVVALGI BOTDAN]:\n{old_text}", "general"))
        except Exception as e:
            logger.info(f"Eski xotira import: {e}")

        _exec(cur, "INSERT OR IGNORE INTO daily_profile (id, profile_text) VALUES (1, '')")
        _exec(cur, "INSERT OR IGNORE INTO topics (name, description) VALUES ('general', 'Umumiy suhbatlar')")
        conn.commit()

    logger.info("✅ Baza v6.0 initializatsiya qilindi")

def save_message(chat_id: int, role: str, content: str, topic: str = "general", mood: float = None):
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "INSERT INTO messages (chat_id, role, content, topic, mood_score) VALUES (?, ?, ?, ?, ?)", (chat_id, role, content, topic, mood))
        _exec(cur, "UPDATE topics SET message_count = message_count + 1, last_active = CURRENT_TIMESTAMP WHERE name = ?", (topic,))
        conn.commit()

def get_recent_messages(chat_id: int, limit: int = 50, topic: str = None) -> list:
    with get_conn() as conn:
        cur = conn.cursor()
        if topic and topic != "general":
            _exec(cur, "SELECT role, content FROM messages WHERE chat_id = ? AND topic = ? ORDER BY id DESC LIMIT ?", (chat_id, topic, limit))
        else:
            _exec(cur, "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?", (chat_id, limit))
        rows = cur.fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def get_all_topics(chat_id: int) -> list:
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "SELECT DISTINCT topic FROM messages WHERE chat_id = ? ORDER BY topic", (chat_id,))
        rows = cur.fetchall()
    return [r[0] for r in rows]

def search_messages(chat_id: int, keyword: str) -> list:
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "SELECT role, content, created_at FROM messages WHERE chat_id = ? AND content LIKE ? ORDER BY id DESC LIMIT 20", (chat_id, f"%{keyword}%"))
        rows = cur.fetchall()
    return rows

def get_daily_profile() -> str:
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "SELECT profile_text FROM daily_profile WHERE id = 1")
        row = cur.fetchone()
    return row[0] if row else ""

def update_daily_profile(text: str):
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "UPDATE daily_profile SET profile_text = ?, last_updated = CURRENT_TIMESTAMP WHERE id = 1", (text,))
        conn.commit()

def get_stats(chat_id: int) -> dict:
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = 'user'", (chat_id,))
        user_count = cur.fetchone()[0]
        _exec(cur, "SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = 'assistant'", (chat_id,))
        ai_count = cur.fetchone()[0]
        _exec(cur, "SELECT COUNT(DISTINCT topic) FROM messages WHERE chat_id = ?", (chat_id,))
        topic_count = cur.fetchone()[0]
        _exec(cur, "SELECT created_at FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (chat_id,))
        last_msg = cur.fetchone()
    return {"user_msgs": user_count, "ai_msgs": ai_count, "topics": topic_count, "last_active": last_msg[0] if last_msg else "Noma'lum"}

def get_mood_history(chat_id: int, days: int = 14) -> list:
    with get_conn() as conn:
        cur = conn.cursor()
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        _exec(cur, "SELECT DATE(created_at), AVG(score), COUNT(*) FROM mood_scores WHERE chat_id = ? AND created_at >= ? GROUP BY DATE(created_at) ORDER BY DATE(created_at)", (chat_id, since))
        rows = cur.fetchall()
    return rows

def save_mood(chat_id: int, score: float, note: str = ""):
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "INSERT INTO mood_scores (chat_id, score, note) VALUES (?, ?, ?)", (chat_id, score, note))
        conn.commit()

def get_weekly_summary(week_start: str) -> Optional[str]:
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "SELECT summary FROM weekly_summaries WHERE week_start = ?", (week_start,))
        row = cur.fetchone()
    return row[0] if row else None

def save_weekly_summary(week_start: str, summary: str):
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "INSERT OR REPLACE INTO weekly_summaries (week_start, summary) VALUES (?, ?)", (week_start, summary))
        conn.commit()

def load_owner_chat_id() -> Optional[int]:
    val = get_setting("owner_chat_id", "")
    return int(val) if val else None

def persist_owner_chat_id(chat_id: int):
    set_setting("owner_chat_id", str(chat_id))

# ============== AI CLIENT (OmniRouter) ==============
async def ai_chat(messages: list, temperature: float = 0.7, max_tokens: int = 4000, model_idx: int = 0) -> str:
    if model_idx >= len(MODELS):
        raise RuntimeError("AI model topilmadi. .env faylidagi AI_MODEL ni tekshiring.")

    model = MODELS[model_idx]
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {AI_API_KEY}"}
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": False}

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{AI_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    text = await resp.text()
                    if resp.status == 429:
                        wait = min(2 ** attempt * 2, 10)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status in [401, 402, 403]:
                        return "❌ OmniRouter'da kredit tugagan, kalit bloklangan yoki ruxsat yo'q. Iltimos, panelni tekshiring."
                    if resp.status != 200:
                        raise RuntimeError(f"AI API xato ({resp.status}): {text[:300]}")
                    data = json.loads(text)
                    content = data["choices"][0]["message"]["content"].strip()
                    if content:
                        return content
                    raise RuntimeError("Bo'sh javob qaytdi.")
        except asyncio.TimeoutError:
            if attempt < 2:
                await asyncio.sleep(min(2 ** attempt, 4))
                continue
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(min(2 ** attempt, 4))
                continue

    raise RuntimeError("AI so'rovi bajarilmadi. OmniRouter Combo holatini tekshiring.")

# ============== MOOD (BACKGROUND) ==============
async def analyze_mood_bg(chat_id: int, text: str):
    prompt = f"""Quyidagi matnning kayfiyatini -1 dan 1 gacha ball bilan baholang. FAQAT raqam.\n\nMatn: {text[:500]}\n\nBall:"""
    try:
        result = await ai_chat([{"role": "system", "content": "Sentiment analiz. Faqat raqam."}, {"role": "user", "content": prompt}], temperature=0.0, max_tokens=10)
        score = float(re.findall(r"[-+]?[0-9]*\.?[0-9]+", result)[0])
        score = max(-1.0, min(1.0, score))
        save_mood(chat_id, score, text[:50])
    except Exception as e:
        logger.debug(f"Mood tahlil xatosi: {e}")

# ============== CODE SANDBOX ==============
async def run_code_sandbox(code: str) -> str:
    blocked = ["import os", "import sys", "open(", "__import__", "subprocess", "eval(", "exec(", "compile(", "input(", "raw_input"]
    for b in blocked:
        if b in code.lower():
            return f"🚫 Bloklangan: '{b}'"
    try:
        proc = await asyncio.create_subprocess_exec(sys.executable, "-c", code, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd="/tmp")
        try:
            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            out = stdout_data.decode("utf-8", errors="ignore")[:3000]
            err = stderr_data.decode("utf-8", errors="ignore")[:2000]
            result = f"📤 STDOUT:\n{out}" if out else ""
            if err:
                result += f"\n\n⚠️ STDERR:\n{err}"
            return result or "✅ Kod bajarildi (bo'sh natija)"
        except asyncio.TimeoutError:
            proc.kill()
            return "⏰ Kod 10 soniyada bajarilmadi"
    except Exception as e:
        return f"❌ Xato: {e}"

# ============== DAILY BACKUP ==============
async def send_daily_backup(chat_id: int):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "SELECT role, content, topic, mood_score, created_at FROM messages WHERE chat_id = ? AND DATE(created_at) = ? ORDER BY id", (chat_id, yesterday))
        rows = cur.fetchall()

    if not rows:
        old_msgs = get_recent_messages(chat_id, limit=1)
        if not old_msgs:
            await bot.send_message(chat_id, f"📭 {yesterday} — suhbat bo'lmagan.\nAfsuski, avvalgi suhbat ma'lumotlari mavjud emas.")
            return
        await bot.send_message(chat_id, f"📭 {yesterday} — suhbat bo'lmagan.\nLekin avvalgi suhbatlar saqlangan. /xotira bilan ko'rishingiz mumkin.")
        return

    history = "\n".join([f"{'👤' if r[0]=='user' else '🤖'} {r[1][:120]}" for r in rows])
    prompt = f"Quyidagi suhbatlarni 10 ta qisqa punkt bilan xulosa qiling (emoji bilan):\n\n{history}"
    try:
        summary = await ai_chat([{"role": "system", "content": "Kundalik xulosa."}, {"role": "user", "content": prompt}], temperature=0.4, max_tokens=1500)
    except:
        summary = "[Xulosa yaratilmadi — AI band]"

    profile = get_daily_profile()
    text = f"📅 {yesterday} KUNLIK ARXIV\n{'='*35}\n\n📝 XULOSA:\n{summary}\n\n🧠 PROFIL:\n{profile[:600]}{'...' if len(profile)>600 else ''}\n\n📊 Statistika: {len(rows)} ta xabar"
    await bot.send_message(chat_id, text)

    filename = f"backup_{yesterday}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"=== {yesterday} KUNLIK ARXIV ===\n\n")
        f.write(f"XULOSA:\n{summary}\n\n")
        f.write("TO'LIQ SUHBATLAR:\n")
        for r in rows:
            mood = f" [kayfiyat: {r[3]}]" if r[3] else ""
            f.write(f"[{r[4]} | {r[2]}]{mood}\n{r[0].upper()}: {r[1]}\n{'='*50}\n")
    await bot.send_document(chat_id, FSInputFile(filename), caption=f"📥 {yesterday} to'liq arxiv")
    os.remove(filename)
    await update_learning_profile(chat_id)

# ============== WEEKLY ==============
async def send_weekly_analysis(chat_id: int):
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    cached = get_weekly_summary(week_start)
    if cached:
        await bot.send_message(chat_id, f"📊 BU HAFTALIK TAHLIL (kesh):\n\n{cached}")
        return
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "SELECT role, content, created_at FROM messages WHERE chat_id = ? AND created_at >= ? ORDER BY id", (chat_id, since))
        rows = cur.fetchall()
    if not rows:
        await bot.send_message(chat_id, "📭 Bu hafta suhbat bo'lmagan.")
        return
    history = "\n".join([f"{'👤' if r[0]=='user' else '🤖'} [{r[2]}] {r[1][:150]}" for r in rows])
    prompt = f"""Quyidagi haftalik suhbatlarni CHUQUR tahlil qiling:\n1. Foydalanuvchi bu hafta nimalar bilan shug'ullangan?\n2. Qanday mavzular ustida ishlagan?\n3. Qanday texnologiyalar/qiziqishlar ko'rinib turibdi?\n4. Qanday muammolar yoki g'oyalar bor?\n5. Keyingi hafta uchun tavsiyalar\n\nSuhbatlar:\n{history}\n\nTAHLIL:"""
    try:
        analysis = await ai_chat([{"role": "system", "content": "Siz haftalik tahlilchi. Chuqur va foydali tahlil bering."}, {"role": "user", "content": prompt}], temperature=0.5, max_tokens=3000)
        save_weekly_summary(week_start, analysis)
        await bot.send_message(chat_id, f"📊 BU HAFTALIK CHUQUR TAHLIL\n{'='*35}\n\n{analysis}")
    except Exception as e:
        await bot.send_message(chat_id, f"❌ Tahlil xatosi: {e}")

# ============== MOOD CHART ==============
async def generate_mood_chart(chat_id: int) -> Optional[str]:
    plt = _get_matplotlib()
    if plt is None:
        return None
    rows = get_mood_history(chat_id, days=14)
    if len(rows) < 2:
        return None
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
    filename = f"mood_chart_{chat_id}.png"
    plt.savefig(filename, dpi=150)
    plt.close()
    return filename

# ============== LEARNING PROFILE ==============
async def update_learning_profile(chat_id: int):
    recent = get_recent_messages(chat_id, limit=50)
    if len(recent) < 5:
        return
    old_profile = get_daily_profile()
    history_text = "\n".join([f"{'User' if m['role'] == 'user' else 'AI'}: {m['content'][:200]}" for m in recent[-20:]])
    prompt = f"""Siz foydalanuvchining shaxsiy AI yordamchisisiz. Quyidagi suhbatlar asosida FOYDALANUVCHI HAQIDA yangi ma'lumotlarni o'rganing va mavjud profilni yangilang.\n\nESKI PROFIL:\n{old_profile if old_profile else '[Hali profil yoq]'}\n\nOXIRGI SUHBATLAR:\n{history_text}\n\nQOIDALAR:\n1. Foydalanuvchining ishtirok etgan loyihalari, texnologiyalar, qiziqishlari\n2. Uning xususiy xohishlari\n3. Vaqt rejimi\n4. HECH QANDAY izohsiz, FAQAT profil matnini chiqaring\n\nYANGI PROFIL:"""
    try:
        new_profile = await ai_chat([{"role": "system", "content": "Siz profil analizchisisiz. Faqat profil matnini chiqaring."}, {"role": "user", "content": prompt}], temperature=0.3, max_tokens=2000)
        update_daily_profile(new_profile)
    except Exception as e:
        logger.error(f"Profil yangilash xatosi: {e}")

# ============== ENCRYPTED EXPORT ==============
async def export_encrypted(chat_id: int) -> Optional[str]:
    cipher = _get_cipher()
    if cipher is None:
        return None
    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "SELECT role, content, topic, mood_score, created_at FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,))
        rows = cur.fetchall()
    data = {"exported_at": datetime.now().isoformat(), "chat_id": chat_id, "messages": [{"role": r[0], "content": r[1], "topic": r[2], "mood": r[3], "time": r[4]} for r in rows], "profile": get_daily_profile()}
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    encrypted = cipher.encrypt(json_bytes)
    filename = f"encrypted_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
    with open(filename, "wb") as f:
        f.write(encrypted)
    return filename

# ============== MIRROR ==============
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
async def send_long_message(chat_id: int, text: str):
    try:
        if len(text) <= 4096:
            await bot.send_message(chat_id, text)
        else:
            filename = f"result_{datetime.now().strftime('%H%M%S')}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text)
            await bot.send_document(chat_id, FSInputFile(filename), caption="📄 Natija juda uzun")
            os.remove(filename)
    except Exception as e:
        logger.error(f"send_long_message xato: {e}")

# ============== PROFESSIONAL LOADING ANIMATSIYASI ==============
async def typing_indicator(chat_id: int):
    while True:
        try:
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(4)
        except:
            break

# ============== REMINDER ==============
async def reminder_worker():
    logger.info("⏰ Reminder worker ishga tushdi")
    while True:
        try:
            now = datetime.utcnow().isoformat()
            with get_conn() as conn:
                cur = conn.cursor()
                _exec(cur, "SELECT id, chat_id, title, content FROM reminders WHERE once_at <= ?", (now,))
                due = cur.fetchall()
                for rid, cid, title, cnt in due:
                    try:
                        await bot.send_message(cid, f"🔔 {title}\n{cnt}")
                    except Exception as e:
                        logger.error(f"Eslatma yuborish xatosi (chat_id={cid}): {e}")
                    _exec(cur, "DELETE FROM reminders WHERE id = ?", (rid,))
                if due:
                    conn.commit()
        except Exception as e:
            logger.error(f"Reminder worker xatosi: {e}")
        await asyncio.sleep(30)

async def weekly_summary_job():
    logger.info("📊 Weekly summary job ishga tushdi")
    last_run = ""
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            if now.weekday() == 0 and now.hour == 9 and now.minute >= 30 and last_run != today_str:
                owner = load_owner_chat_id()
                if owner:
                    try:
                        await send_weekly_analysis(owner)
                        await mirror_to_channel(f"📊 Weekly analysis: {today_str}")
                    except Exception as e:
                        logger.error(f"Weekly cron xato: {e}")
                    last_run = today_str
                    await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Weekly job xatosi: {e}")
        await asyncio.sleep(30)

async def cron_scheduler():
    logger.info("📅 Cron scheduler ishga tushdi")
    last_run = ""
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            if now.hour == 9 and now.minute >= 0 and last_run != today_str:
                owner = load_owner_chat_id()
                if owner:
                    try:
                        await send_daily_backup(owner)
                        await mirror_to_channel(f"📅 Daily backup: {today_str}")
                    except Exception as e:
                        logger.error(f"Daily cron xato: {e}")
                    last_run = today_str
                    await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Cron scheduler xatosi: {e}")
        await asyncio.sleep(30)

# ============== BOT VA MENYU ==============
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

current_topics = {}
# Voice mode butunlay o'chirildi!

def _feature_status() -> str:
    features = []
    features.append(f"🧠 AI: {'✅' if MODELS[0] else '❌'}")
    features.append(f"📊 Charts: {'✅' if _get_matplotlib() else '❌ pip install matplotlib'}")
    features.append(f"🔐 Encrypt: {'✅' if _get_fernet() else '❌ pip install cryptography'}")
    features.append(f"📡 Mirror: {'✅' if CHANNEL_ID else '❌ CHANNEL_ID yoq'}")
    return "\n".join(features)

# --- MENYU TUGMALARI ---
def get_main_menu_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Zichlangan Xotira", callback_data="cmd_memory"), InlineKeyboardButton(text="📊 Statistika", callback_data="cmd_status")],
        [InlineKeyboardButton(text="📈 Kayfiyat Grafigi", callback_data="cmd_mood"), InlineKeyboardButton(text="🗂 Mavzular", callback_data="cmd_topics")],
        [InlineKeyboardButton(text="🧬 Profilim", callback_data="cmd_profile"), InlineKeyboardButton(text="🔐 Eksport", callback_data="cmd_export")],
        [InlineKeyboardButton(text="⏰ Eslatma qo'shish", callback_data="cmd_reminder"), InlineKeyboardButton(text="📅 Haftalik Tahlil", callback_data="cmd_weekly")],
        [InlineKeyboardButton(text="🔍 Xotirani Qidirish", callback_data="cmd_search")],
    ])
    return kb

# --- ZICHLANGAN XOTIRA FUNKSIYASI ---
@dp.message(Command("xotira"))
async def cmd_memory_compress(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    with get_conn() as conn:
        cur = conn.cursor()
        _exec(cur, "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,))
        rows = cur.fetchall()

    if not rows:
        await message.answer("📭 Xotira bo'sh.")
        return

    history_text = "\n".join([f"{'User' if r[0]=='user' else 'AI'}: {r[1][:500]}" for r in rows])
    await message.answer("🧠 Xotira zichlanmoqda, biroz kuting... (Bu juda uzun bo'lishi mumkin)")

    prompt = f"""Quyidagi suhbat tarixini o'qing va juda batafsil, hech narsani yo'qotmagan holda, "ZICHLANGAN XOTIRA" formatida yozing.
    
QOIDALAR:
- Foydalanuvchi kim, qanday loyihalar ustida ishlagan, qanday ma'lumotlar bergan (parollar, manzillar, ismlar, kodlar).
- AI qanday maslahatlar bergan.
- Barcha muhim tafsilotlarni saqlang.

SUHBAT TARIXI:
{history_text}

ZICHLANGAN XOTIRA:"""

    try:
        compressed_memory = await ai_chat([
            {"role": "system", "content": "Siz xotira analizchisisiz."},
            {"role": "user", "content": prompt}
        ], temperature=0.3, max_tokens=4000)

        update_daily_profile(compressed_memory)
        await message.answer(f"✅ Xotira muvaffaqiyatli zichlandi va saqlandi!\n\n{compressed_memory[:2000]}")
    except Exception as e:
        await message.answer(f"❌ Xotirani zichlashda xato: {e}")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    global OWNER_CHAT_ID
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        await message.answer("🔐 Parolni kiriting:")
        return

    OWNER_CHAT_ID = chat_id
    persist_owner_chat_id(chat_id)

    await message.answer(
        f"👋 Xush kelibsiz, egam!\n\n"
        f"🛠 Barcha funksiyalar pastdagi menyu orqali boshqariladi.\n"
        f"📌 Yordam uchun /xotira yoki /status buyruqlarini bosing.\n\n"
        f"⚙️ Holat: ✅ Online",
        reply_markup=get_main_menu_kb()
    )

@dp.message(Command("status"))
async def cmd_status(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        await message.answer("🔐 Avval parol:")
        return

    stats = get_stats(chat_id)
    profile = get_daily_profile()
    features = _feature_status()

    await message.answer(
        f"📊 Bot holati:\n"
        f"✅ Bot: Online\n"
        f"🧠 Model: {MODELS[0]}\n"
        f"🔄 Fallback: Yo'q (OmniRouter Combo ishlatilmoqda)\n"
        f"💾 Jami xabarlar: {stats['user_msgs'] + stats['ai_msgs']}\n"
        f"📁 Mavzular: {stats['topics']}\n"
        f"🧬 Profil: {len(profile)} belgi\n"
        f"⏰ Avtomatik xotira: Har kuni 09:00\n"
        f"📊 Haftalik tahlil: Dushanba 09:30\n\n"
        f"⚙️ Funksiyalar:\n{features}"
    )

# --- CALLBACK HANDLERS ---
@dp.callback_query(F.data == "cmd_memory")
async def menu_memory(callback: CallbackQuery):
    await callback.answer()
    await cmd_memory_compress(callback.message)

@dp.callback_query(F.data == "cmd_status")
async def menu_status(callback: CallbackQuery):
    await callback.answer()
    await cmd_status(callback.message)

@dp.callback_query(F.data == "cmd_mood")
async def menu_mood(callback: CallbackQuery):
    await callback.answer()
    if _get_matplotlib() is None:
        await callback.message.answer("❌ Matplotlib o'rnatilmagan.\n`pip install matplotlib`")
        return
    chart_path = await generate_mood_chart(callback.message.chat.id)
    if chart_path:
        await callback.message.answer_photo(FSInputFile(chart_path), caption="📈 14 kunlik kayfiyat dinamikasi")
        os.remove(chart_path)
    else:
        await callback.message.answer("📭 Hali yetarlicha kayfiyat ma'lumoti yo'q.")

@dp.callback_query(F.data == "cmd_topics")
async def menu_topics(callback: CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    topics = get_all_topics(chat_id)
    current = current_topics.get(chat_id, "general")
    text = "📂 Mavzular:\n\n"
    for t in topics:
        marker = "▶️" if t == current else "•"
        text += f"{marker} {t}\n"
    await callback.message.answer(text)

@dp.callback_query(F.data == "cmd_profile")
async def menu_profile(callback: CallbackQuery):
    await callback.answer()
    profile = get_daily_profile()
    if not profile.strip():
        await callback.message.answer("🧬 Hali profilingiz shakllanmagan.")
        return
    await callback.message.answer(f"🧬 SIZNING AI PROFILINGIZ:\n{'='*30}\n\n{profile}")

@dp.callback_query(F.data == "cmd_export")
async def menu_export(callback: CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    if _get_fernet() is None:
        await callback.message.answer("❌ Cryptography o'rnatilmagan.\n`pip install cryptography`")
        return
    await callback.message.answer("🔐 Ma'lumotlar shifrlanmoqda...")
    try:
        filename = await export_encrypted(chat_id)
        if filename:
            await callback.message.answer_document(FSInputFile(filename), caption="🔐 Shifrlangan eksport. Kalit .secret_key faylida.")
            os.remove(filename)
        else:
            await callback.message.answer("❌ Shifrlashda xato.")
    except Exception as e:
        await callback.message.answer(f"❌ Eksport xatosi: {e}")

@dp.callback_query(F.data == "cmd_reminder")
async def menu_reminder(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "⏰ Foydalanish:\n"
        "/eslatma 2026-08-22 15:00 Uchrashuvga borish"
    )

@dp.callback_query(F.data == "cmd_weekly")
async def menu_weekly(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("⏳ Haftalik tahlil tayyorlanmoqda...")
    await send_weekly_analysis(callback.message.chat.id)

@dp.callback_query(F.data == "cmd_search")
async def menu_search(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🔍 Foydalanish: /qidir <so'z>\nMasalan: /qidir docker")

# --- ASOSIY XABAR HANDLER ---
@dp.message(F.text)
async def handle_message(message: Message):
    global OWNER_CHAT_ID
    chat_id = message.chat.id
    user_text = message.text

    if not is_authenticated(chat_id):
        if user_text == ADMIN_PASSWORD:
            authenticated_chats.add(chat_id)
            OWNER_CHAT_ID = chat_id
            persist_owner_chat_id(chat_id)
            await message.answer("✅ Parol tasdiqlandi!\n\n👋 Xush kelibsiz, egam!\n/xotira — Zichlangan xotira")
        else:
            await message.answer("❌ Noto'g'ri parol.")
        return

    if user_text.startswith("/"):
        return

    asyncio.create_task(analyze_mood_bg(chat_id, user_text))

    topic = current_topics.get(chat_id, "general")
    save_message(chat_id, "user", user_text, topic)

    profile = get_daily_profile()
    recent_msgs = get_recent_messages(chat_id, limit=30, topic=topic)

    old_memory_msgs = []
    for m in recent_msgs:
        if m['role'] == 'system' and '[ESKI XOTIRA' in m['content']:
            old_memory_msgs.append(m)

    system_prompt = f"""Siz foydalanuvchining SHAXSIY va YAQIN AI yordamchisisiz.

SIZNING VAZIFALARINGIZ:
1. Foydalanuvchining avvalgi suhbatlaridan kontekstni tushunib, mantiqiy davom ettiring
2. Uning so'rovlari ustida FOCUS qiling, boshqa narsalarga chalg'imang
3. O'zbek tilida javob bering (agar boshqa til talab qilinmasa)
4. Qisqa va aniq bo'ling, lekin kerakli ma'lumotni to'liq bering

SIZNING PROFILINGIZ:
{profile if profile else '[Hali profil shakllanmagan]'}

Joriy mavzu: {topic}
"""

    messages = [{"role": "system", "content": system_prompt}]
    if old_memory_msgs:
        messages.extend(old_memory_msgs)
    messages.extend([m for m in recent_msgs if m['role'] != 'system'])
    messages.append({"role": "user", "content": user_text})

    typing_task = asyncio.create_task(typing_indicator(chat_id))
    notify_task = asyncio.create_task(_notify_if_slow(chat_id))

    try:
        assistant_text = await ai_chat(messages, temperature=0.7)
        notify_task.cancel()
        save_message(chat_id, "assistant", assistant_text, topic)

        stats = get_stats(chat_id)
        if (stats['user_msgs'] + stats['ai_msgs']) % 20 == 0:
            asyncio.create_task(update_learning_profile(chat_id))

        await send_long_message(chat_id, assistant_text)

        if len(assistant_text) > 100:
            await mirror_to_channel(f"💬 Suhbat:\n👤: {user_text[:100]}\n🤖: {assistant_text[:200]}")
    except RuntimeError as e:
        notify_task.cancel()
        await message.answer(f"❌ AI xatolik: {e}\n\nQayta urinib ko'ring yoki /status ni tekshiring.")
    except Exception as e:
        notify_task.cancel()
        logger.error(f"AI suhbat xato: {e}")
        await message.answer(f"❌ Xatolik: {e}")
    finally:
        typing_task.cancel()

async def _notify_if_slow(chat_id: int):
    await asyncio.sleep(8)
    try:
        await bot.send_message(
            chat_id,
            "⏳ AI javob tayyorlanmoqda...\nBu 10-30 soniya olishi mumkin (model band bo'lsa)."
        )
    except:
        pass

# --- QIDIRUV ---
@dp.message(Command("qidir"))
async def cmd_search_command(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.answer("🔍 Foydalanish: /qidir <so'z>\nMasalan: /qidir docker")
        return
    keyword = args[1]
    results = search_messages(chat_id, keyword)
    if not results:
        await message.answer(f"🔍 '{keyword}' bo'yicha hech narsa topilmadi.")
        return
    text = f"🔍 '{keyword}' bo'yicha {len(results)} ta natija:\n\n"
    for r in results[:10]:
        role_emoji = "👤" if r[0] == 'user' else '🤖'
        content = r[1][:200] + "..." if len(r[1]) > 200 else r[1]
        text += f"{role_emoji} [{r[2]}]\n{content}\n\n"
    await message.answer(text[:4000])

# --- ESLATMA ---
@dp.message(Command("eslatma"))
async def cmd_reminder(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    text = message.text[len("/eslatma "):].strip()
    if not text:
        await message.answer("⏰ Foydalanish: /eslatma 2026-08-22 15:00 Uchrashuvga borish")
        return
    parts = text.split(" ", 2)
    if len(parts) < 3:
        await message.answer("❌ Format noto'g'ri. Masalan: /eslatma 2026-08-22 15:00 Uchrashuv")
        return
    date_str, time_str, reminder_text = parts[0], parts[1], parts[2]
    try:
        once_at = f"{date_str}T{time_str}:00+05:00"
        with get_conn() as conn:
            cur = conn.cursor()
            _exec(cur, "INSERT INTO reminders (chat_id, title, content, once_at) VALUES (?, ?, ?, ?)", (chat_id, reminder_text[:50], reminder_text, once_at))
            conn.commit()
        await message.answer(f"✅ Eslatma saqlandi!\n📅 {date_str} {time_str}\n📝 {reminder_text}")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")

# --- MAIN ---
async def main():
    init_db()

    global OWNER_CHAT_ID
    OWNER_CHAT_ID = load_owner_chat_id()
    if OWNER_CHAT_ID:
        authenticated_chats.add(OWNER_CHAT_ID)
        logger.info(f"✅ Owner chat_id tiklandi: {OWNER_CHAT_ID}")

    logger.info("✅ Bot ishga tushdi (v6.0 — Premium Edition)")

    asyncio.create_task(reminder_worker())
    asyncio.create_task(cron_scheduler())
    asyncio.create_task(weekly_summary_job())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
