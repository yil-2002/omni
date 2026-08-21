#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shaxsiy AI Yordamchi v3.2 — Robust Edition
- Eski xotirani avtomatik import qiladi
- AI sekin bo'lsa, foydalanuvchini xabardor qiladi
- Mood analysis bloklamaydi (background'da)
- Qisqa timeout (30s), kam retry (2 ta)

Requirements:
    pip install aiogram aiohttp python-dotenv
"""

import os
import sys
import asyncio
import sqlite3
import json
import re
import traceback
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
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
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://punctured-old-playmaker.ngrok-free.dev/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "not-needed")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DB_PATH = "memory.db"

OWNER_CHAT_ID: Optional[int] = None

MODELS = [
    os.getenv("AI_MODEL", "openai/gpt-oss-120b"),
    os.getenv("AI_MODEL_FALLBACK1", "openai/gpt-4o-mini"),
    os.getenv("AI_MODEL_FALLBACK2", "anthropic/claude-3-haiku"),
]

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

# ============== SQLITE BAZA + ESKI XOTIRA MIGRATSIYA ==============
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Yangi jadvallar
    cur.execute("""
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            profile_text TEXT NOT NULL DEFAULT '',
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            message_count INTEGER DEFAULT 0,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mood_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            score REAL NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS weekly_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            once_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ESKI XOTIRANI IMPORT QILISH (faqat bir marta)
    try:
        cur.execute("SELECT compressed_text FROM memory WHERE id = 1")
        old_row = cur.fetchone()
        if old_row and old_row[0] and old_row[0].strip():
            old_text = old_row[0].strip()
            # Tekshirish: allaqachon import qilinganmi?
            cur.execute("SELECT COUNT(*) FROM messages WHERE role = 'system' AND content LIKE ?", ("%[ESKI XOTIRA]%",))
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "INSERT INTO messages (chat_id, role, content, topic) VALUES (?, ?, ?, ?)",
                    (0, "system", f"[ESKI XOTIRA — AVVALGI BOTDAN]:\\n{old_text}", "general")
                )
                logger.info(f"✅ Eski xotira import qilindi ({len(old_text)} belgi)")
    except Exception as e:
        logger.info(f"Eski xotira import (memory jadvali yo'q yoki bo'sh): {e}")

    cur.execute("INSERT OR IGNORE INTO daily_profile (id, profile_text) VALUES (1, '')")
    cur.execute("INSERT OR IGNORE INTO topics (name, description) VALUES ('general', 'Umumiy suhbatlar')")
    conn.commit()
    conn.close()
    logger.info("✅ Baza v3.2 initializatsiya qilindi")


def save_message(chat_id: int, role: str, content: str, topic: str = "general", mood: float = None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (chat_id, role, content, topic, mood_score) VALUES (?, ?, ?, ?, ?)",
        (chat_id, role, content, topic, mood)
    )
    cur.execute(
        "UPDATE topics SET message_count = message_count + 1, last_active = CURRENT_TIMESTAMP WHERE name = ?",
        (topic,)
    )
    conn.commit()
    conn.close()


def get_recent_messages(chat_id: int, limit: int = 50, topic: str = None) -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if topic and topic != "general":
        cur.execute(
            "SELECT role, content FROM messages WHERE chat_id = ? AND topic = ? ORDER BY id DESC LIMIT ?",
            (chat_id, topic, limit)
        )
    else:
        cur.execute(
            "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)
        )
    rows = cur.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def get_all_topics(chat_id: int) -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT topic FROM messages WHERE chat_id = ? ORDER BY topic", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def search_messages(chat_id: int, keyword: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content, created_at FROM messages WHERE chat_id = ? AND content LIKE ? ORDER BY id DESC LIMIT 20",
        (chat_id, f"%{keyword}%")
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_daily_profile() -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT profile_text FROM daily_profile WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def update_daily_profile(text: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE daily_profile SET profile_text = ?, last_updated = CURRENT_TIMESTAMP WHERE id = 1",
        (text,)
    )
    conn.commit()
    conn.close()


def get_stats(chat_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = 'user'", (chat_id,))
    user_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = 'assistant'", (chat_id,))
    ai_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT topic) FROM messages WHERE chat_id = ?", (chat_id,))
    topic_count = cur.fetchone()[0]
    cur.execute("SELECT created_at FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT 1", (chat_id,))
    last_msg = cur.fetchone()
    conn.close()
    return {
        "user_msgs": user_count,
        "ai_msgs": ai_count,
        "topics": topic_count,
        "last_active": last_msg[0] if last_msg else "Noma'lum"
    }


def get_mood_history(chat_id: int, days: int = 14) -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cur.execute(
        "SELECT DATE(created_at), AVG(score), COUNT(*) FROM mood_scores WHERE chat_id = ? AND created_at >= ? GROUP BY DATE(created_at) ORDER BY DATE(created_at)",
        (chat_id, since)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def save_mood(chat_id: int, score: float, note: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO mood_scores (chat_id, score, note) VALUES (?, ?, ?)",
        (chat_id, score, note)
    )
    conn.commit()
    conn.close()


def get_weekly_summary(week_start: str) -> Optional[str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT summary FROM weekly_summaries WHERE week_start = ?", (week_start,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def save_weekly_summary(week_start: str, summary: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO weekly_summaries (week_start, summary) VALUES (?, ?)",
        (week_start, summary)
    )
    conn.commit()
    conn.close()


# ============== AI CLIENT (TEZKOR + KAM RETRY) ==============
async def ai_chat(messages: list, temperature: float = 0.7, max_tokens: int = 4000, model_idx: int = 0) -> str:
    if model_idx >= len(MODELS):
        raise RuntimeError("Barcha modellar ishlamadi. Keyinroq urinib ko'ring.")

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

    # FAQAT 2 ta urinish (tezroq fail qilsin)
    for attempt in range(2):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{AI_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)  # 30 soniya (avval 120 edi)
                ) as resp:
                    text = await resp.text()

                    if resp.status == 429:
                        wait = min(2 ** attempt * 2, 10)  # Maks 10 soniya
                        logger.warning(f"[{model}] 429, {wait}s kutish...")
                        await asyncio.sleep(wait)
                        continue

                    if resp.status != 200:
                        raise RuntimeError(f"AI API xato {resp.status}: {text[:300]}")

                    data = json.loads(text)
                    content = data["choices"][0]["message"]["content"].strip()
                    if content:
                        return content
                    raise RuntimeError("Bo'sh javob")

        except asyncio.TimeoutError:
            logger.warning(f"[{model}] Timeout (30s)")
            break  # Keyingi modelga o'tish
        except Exception as e:
            logger.warning(f"[{model}] xato: {e}")
            break  # Keyingi modelga o'tish

    # Keyingi modelga o'tish
    return await ai_chat(messages, temperature, max_tokens, model_idx + 1)


# ============== MOOD ANALYSIS (BACKGROUND, BLOKLAMAYDI) ==============
async def analyze_mood_bg(chat_id: int, text: str):
    """Background'da kayfiyatni tahlil qiladi, javobni kutmaydi"""
    prompt = f"""Quyidagi matnning kayfiyatini -1 dan 1 gacha ball bilan baholang. FAQAT raqam.

Matn: {text[:500]}

Ball:"""
    try:
        result = await ai_chat([
            {"role": "system", "content": "Sentiment analiz. Faqat raqam."},
            {"role": "user", "content": prompt}
        ], temperature=0.0, max_tokens=10)
        score = float(re.findall(r"[-+]?[0-9]*\.?[0-9]+", result)[0])
        score = max(-1.0, min(1.0, score))
        save_mood(chat_id, score, text[:50])
    except Exception as e:
        logger.debug(f"Mood tahlil xatosi: {e}")


# ============== VOICE GENERATION ==============
async def generate_voice(text: str, lang: str = "uz") -> Optional[str]:
    gTTS = _get_gtts()
    if gTTS is None:
        return None
    filename = f"voice_{datetime.now().strftime('%H%M%S')}.mp3"
    try:
        tts = gTTS(text=text[:500], lang=lang, slow=False)
        tts.save(filename)
        return filename
    except Exception as e:
        logger.error(f"Voice xato: {e}")
        return None


# ============== CODE SANDBOX ==============
async def run_code_sandbox(code: str) -> str:
    blocked = ["import os", "import sys", "open(", "__import__", "subprocess", "eval(", "exec(", "compile(", "input(", "raw_input"]
    for b in blocked:
        if b in code.lower():
            return f"🚫 Bloklangan: '{b}'"

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp"
        )
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

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content, topic, mood_score, created_at FROM messages WHERE chat_id = ? AND DATE(created_at) = ? ORDER BY id",
        (chat_id, yesterday)
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        # Eski xotirani tekshirish
        old_msgs = get_recent_messages(chat_id, limit=1)
        if not old_msgs:
            await bot.send_message(chat_id, f"📭 {yesterday} — suhbat bo'lmagan.\\nAfsuski, avvalgi suhbat ma'lumotlari mavjud emas.")
            return
        await bot.send_message(chat_id, f"📭 {yesterday} — suhbat bo'lmagan.\\nLekin avvalgi suhbatlar saqlangan. /tariz bilan ko'rishingiz mumkin.")
        return

    history = "\n".join([f"{'👤' if r[0]=='user' else '🤖'} {r[1][:120]}" for r in rows])
    prompt = f"Quyidagi suhbatlarni 10 ta qisqa punkt bilan xulosa qiling (emoji bilan):\n\n{history}"
    try:
        summary = await ai_chat([
            {"role": "system", "content": "Kundalik xulosa."},
            {"role": "user", "content": prompt}
        ], temperature=0.4, max_tokens=1500)
    except:
        summary = "[Xulosa yaratilmadi — AI band]"

    profile = get_daily_profile()

    text = (
        f"📅 {yesterday} KUNLIK ARXIV\n"
        f"{'='*35}\n\n"
        f"📝 XULOSA:\n{summary}\n\n"
        f"🧠 PROFIL:\n{profile[:600]}{'...' if len(profile)>600 else ''}\n\n"
        f"📊 Statistika: {len(rows)} ta xabar"
    )

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


# ============== WEEKLY ANALYSIS ==============
async def send_weekly_analysis(chat_id: int):
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    cached = get_weekly_summary(week_start)
    if cached:
        await bot.send_message(chat_id, f"📊 BU HAFTALIK TAHLIL (kesh):\n\n{cached}")
        return

    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content, created_at FROM messages WHERE chat_id = ? AND created_at >= ? ORDER BY id",
        (chat_id, since)
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await bot.send_message(chat_id, "📭 Bu hafta suhbat bo'lmagan.")
        return

    history = "\n".join([f"{'👤' if r[0]=='user' else '🤖'} [{r[2]}] {r[1][:150]}" for r in rows])
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
    history_text = "\n".join([
        f"{'User' if m['role'] == 'user' else 'AI'}: {m['content'][:200]}"
        for m in recent[-20:]
    ])

    prompt = f"""Siz foydalanuvchining shaxsiy AI yordamchisisiz. Quyidagi suhbatlar asosida FOYDALANUVCHI HAQIDA yangi ma'lumotlarni o'rganing va mavjud profilni yangilang.

ESKI PROFIL:
{old_profile if old_profile else '[Hali profil yoq]'}

OXIRGI SUHBATLAR:
{history_text}

QOIDALAR:
1. Foydalanuvchining ishtirok etgan loyihalari, texnologiyalar, qiziqishlari
2. Uning xususiy xohishlari (qisqa javob, batafsil, o'zbek tilida, va h.k.)
3. Vaqt rejimi, faol soatlari
4. Oldingi topshiriqlardan o'rganilgan darslar
5. HECH QANDAY izohsiz, FAQAT profil matnini chiqaring

YANGI PROFIL:"""

    try:
        new_profile = await ai_chat([
            {"role": "system", "content": "Siz profil analizchisisiz. Faqat profil matnini chiqaring."},
            {"role": "user", "content": prompt}
        ], temperature=0.3, max_tokens=2000)
        update_daily_profile(new_profile)
        logger.info("✅ Learning profile yangilandi")
    except Exception as e:
        logger.error(f"Profil yangilash xatosi: {e}")


# ============== ENCRYPTED EXPORT ==============
async def export_encrypted(chat_id: int) -> Optional[str]:
    cipher = _get_cipher()
    if cipher is None:
        return None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content, topic, mood_score, created_at FROM messages WHERE chat_id = ? ORDER BY id",
        (chat_id,)
    )
    rows = cur.fetchall()
    conn.close()

    data = {
        "exported_at": datetime.now().isoformat(),
        "chat_id": chat_id,
        "messages": [
            {"role": r[0], "content": r[1], "topic": r[2], "mood": r[3], "time": r[4]}
            for r in rows
        ],
        "profile": get_daily_profile(),
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


async def typing_indicator(chat_id: int):
    while True:
        try:
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(4)
        except:
            break


# ============== CRON SCHEDULER ==============
async def cron_scheduler():
    while True:
        now = datetime.now()

        if now.hour == 9 and now.minute == 0 and OWNER_CHAT_ID:
            try:
                await send_daily_backup(OWNER_CHAT_ID)
                await mirror_to_channel(f"📅 Daily backup: {now.strftime('%Y-%m-%d')}")
            except Exception as e:
                logger.error(f"Daily cron xato: {e}")
            await asyncio.sleep(60)

        if now.weekday() == 0 and now.hour == 9 and now.minute == 30 and OWNER_CHAT_ID:
            try:
                await send_weekly_analysis(OWNER_CHAT_ID)
                await mirror_to_channel(f"📊 Weekly analysis: {now.strftime('%Y-%m-%d')}")
            except Exception as e:
                logger.error(f"Weekly cron xato: {e}")
            await asyncio.sleep(60)

        await asyncio.sleep(30)


# ============== TELEGRAM BOT ==============
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

current_topics = {}
voice_mode = set()


def _feature_status() -> str:
    features = []
    features.append(f"🧠 AI: {'✅' if MODELS[0] else '❌'}")
    features.append(f"🔊 Voice: {'✅' if _get_gtts() else '❌ pip install gtts'}")
    features.append(f"📊 Charts: {'✅' if _get_matplotlib() else '❌ pip install matplotlib'}")
    features.append(f"🔐 Encrypt: {'✅' if _get_fernet() else '❌ pip install cryptography'}")
    features.append(f"📡 Mirror: {'✅' if CHANNEL_ID else '❌ CHANNEL_ID yoq'}")
    return "\n".join(features)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    global OWNER_CHAT_ID
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        await message.answer("🔐 Parolni kiriting:")
        return

    OWNER_CHAT_ID = chat_id
    stats = get_stats(chat_id)
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
        f"/run <kod> — Python kod bajarish\n"
        f"/kayfiyat — 14 kunlik kayfiyat grafigi\n"
        f"/eslatma <vaqt> <xabar> — Eslatma\n"
        f"/haftalik — Haftalik chuqur tahlil\n"
        f"/xotira — Kunlik xotira (qo'lda)\n"
        f"/export — Shifrlangan eksport\n"
        f"/clear — Sessiyani tozalash\n"
        f"/status — Bot holati"
    )


@dp.message(Command("status"))
async def cmd_status(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        await message.answer("🔐 Avval parol:")
        return

    stats = get_stats(chat_id)
    profile = get_daily_profile()
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
        await message.answer("❌ gTTS o'rnatilmagan.\n`pip install gtts`")
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
            "⚠️ Xavfli operatsiyalar bloklangan."
        )
        return

    code = args[1]
    if code.startswith("```"):
        code = re.sub(r"^```(?:python)?\n?", "", code)
        code = re.sub(r"\n?```$", "", code)

    await message.answer(f"⏳ Kod bajarilmoqda...\n```\n{code[:100]}\n```", parse_mode="Markdown")
    result = await run_code_sandbox(code)
    await send_long_message(chat_id, f"💻 NATIJA:\n```\n{result}\n```")


@dp.message(Command("kayfiyat"))
async def cmd_mood(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    if _get_matplotlib() is None:
        await message.answer("❌ Matplotlib o'rnatilmagan.\n`pip install matplotlib`")
        return

    chart_path = await generate_mood_chart(chat_id)
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

    text = message.text[len("/eslatma "):].strip()
    if not text:
        await message.answer(
            "⏰ Foydalanish:\n"
            "/eslatma 2026-08-22 15:00 Uchrashuvga borish\n\n"
            "Yoki har kuni:\n"
            "/eslatma daily 09:00 Ertalabki reja"
        )
        return

    parts = text.split(" ", 2)
    if len(parts) < 3:
        await message.answer("❌ Format noto'g'ri. Masalan: /eslatma 2026-08-22 15:00 Uchrashuv")
        return

    date_str, time_str, reminder_text = parts[0], parts[1], parts[2]

    try:
        once_at = f"{date_str}T{time_str}:00+05:00"

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO reminders (chat_id, title, content, once_at) VALUES (?, ?, ?, ?)",
            (chat_id, reminder_text[:50], reminder_text, once_at)
        )
        conn.commit()
        conn.close()

        await message.answer(f"✅ Eslatma saqlandi!\n📅 {date_str} {time_str}\n📝 {reminder_text}")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")


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

    msgs = get_recent_messages(chat_id, limit=limit)
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
    await callback.answer()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content, topic, mood_score, created_at FROM messages WHERE chat_id = ? ORDER BY id",
        (chat_id,)
    )
    rows = cur.fetchall()
    conn.close()

    filename = f"full_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("=== TO'LIQ SUHBAT TARIXI ===\n\n")
        for r in rows:
            mood = f" [kayfiyat: {r[3]}]" if r[3] else ""
            f.write(f"[{r[4]} | {r[2]}]{mood}\n{r[0].upper()}: {r[1]}\n{'='*50}\n")

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

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO topics (name) VALUES (?)", (topic,))
    conn.commit()
    conn.close()

    await message.answer(f"✅ Yangi mavzu: '{topic}'\nUmumiy suhbatga qaytish: /mavzu general")


@dp.message(Command("mavzular"))
async def cmd_topics(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    topics = get_all_topics(chat_id)
    current = current_topics.get(chat_id, "general")

    text = "📂 Mavzular:\n\n"
    for t in topics:
        marker = "▶️" if t == current else "•"
        text += f"{marker} {t}\n"

    await message.answer(text)


@dp.message(Command("men"))
async def cmd_profile(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    profile = get_daily_profile()
    if not profile.strip():
        await message.answer("🧬 Hali profilingiz shakllanmagan.")
        return

    await message.answer(f"🧬 SIZNING AI PROFILINGIZ:\n{'='*30}\n\n{profile}")


@dp.message(Command("xotira"))
async def cmd_memory(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    await message.answer("⏳ Kunlik xotira tayyorlanmoqda...")
    await send_daily_backup(chat_id)


@dp.message(Command("export"))
async def cmd_export(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return

    if _get_fernet() is None:
        await message.answer("❌ Cryptography o'rnatilmagan.\n`pip install cryptography`")
        return

    await message.answer("🔐 Ma'lumotlar shifrlanmoqda...")
    try:
        filename = await export_encrypted(chat_id)
        if filename:
            await message.answer_document(
                FSInputFile(filename),
                caption="🔐 Shifrlangan eksport. Kalit .secret_key faylida."
            )
            os.remove(filename)
        else:
            await message.answer("❌ Shifrlashda xato.")
    except Exception as e:
        await message.answer(f"❌ Eksport xatosi: {e}")


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        return
    await message.answer("🧹 Sessiya tozalandi. Baza xotirasi o'chirilmadi.")


# ============== RASM TUSHUNISH ==============
@dp.message(F.photo)
async def handle_photo(message: Message):
    chat_id = message.chat.id
    if not is_authenticated(chat_id):
        await message.answer("🔐 Avval parol:")
        return

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    caption = message.caption or "Bu rasmda nima bor?"

    messages = [
        {"role": "system", "content": "Siz rasm tahlilchisisiz. Rasmni tushuntiring."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": caption},
                {"type": "image_url", "image_url": {"url": file_url}}
            ]
        }
    ]

    typing_task = asyncio.create_task(typing_indicator(chat_id))
    try:
        response = await ai_chat(messages, temperature=0.5)
        save_message(chat_id, "user", f"[RASM] {caption}")
        save_message(chat_id, "assistant", response)

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
        await message.answer(f"❌ Rasmni tushunishda xato: {e}")
    finally:
        typing_task.cancel()


# ============== ASOSIY XABAR HANDLER ==============
@dp.message(F.text)
async def handle_message(message: Message):
    global OWNER_CHAT_ID
    chat_id = message.chat.id
    user_text = message.text

    # Parol tekshiruvi
    if not is_authenticated(chat_id):
        if user_text == ADMIN_PASSWORD:
            authenticated_chats.add(chat_id)
            OWNER_CHAT_ID = chat_id
            await message.answer(
                "✅ Parol tasdiqlandi!\n\n"
                "👋 Xush kelibsiz, egam!\n"
                "/start — Bosh menu"
            )
        else:
            await message.answer("❌ Noto'g'ri parol.")
        return

    # Komandalarni skip qilish
    if user_text.startswith("/"):
        return

    # MOOD ANALYSIS — BACKGROUND'DA, BLOKLAMAYDI
    asyncio.create_task(analyze_mood_bg(chat_id, user_text))

    # Xabarni saqlash
    topic = current_topics.get(chat_id, "general")
    save_message(chat_id, "user", user_text, topic)

    # Kontekstni yig'ish
    profile = get_daily_profile()
    recent_msgs = get_recent_messages(chat_id, limit=30, topic=topic)

    # Eski xotirani ham qo'shish (agar bor bo'lsa)
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
    # Eski xotirani birinchi qo'shish
    if old_memory_msgs:
        messages.extend(old_memory_msgs)
    messages.extend([m for m in recent_msgs if m['role'] != 'system'])
    messages.append({"role": "user", "content": user_text})

    typing_task = asyncio.create_task(typing_indicator(chat_id))

    # AGAR 10 SONIYADAN KO'P KETSA, FOYDALANUVCHINI XABARDOR QILISH
    notify_task = asyncio.create_task(_notify_if_slow(chat_id))

    try:
        assistant_text = await ai_chat(messages, temperature=0.7)
        notify_task.cancel()
        save_message(chat_id, "assistant", assistant_text, topic)

        # Profilni yangilash (har 20 xabardan keyin)
        stats = get_stats(chat_id)
        if (stats['user_msgs'] + stats['ai_msgs']) % 20 == 0:
            asyncio.create_task(update_learning_profile(chat_id))

        # Ovozli rejim
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

        # Mirror
        if len(assistant_text) > 100:
            await mirror_to_channel(f"💬 Suhbat:\n👤: {user_text[:100]}\n🤖: {assistant_text[:200]}")

    except RuntimeError as e:
        notify_task.cancel()
        if "429" in str(e) or "band" in str(e).lower() or "Rate" in str(e):
            await message.answer(
                "⏳ AI hozircha band (Rate Limit).\n"
                "Iltimos, 1-2 daqiqa kutib qayta urinib ko'ring.\n\n"
                "📊 /status — bot holatini ko'rish"
            )
        else:
            await message.answer(f"❌ AI xatolik: {e}\n\nQayta urinib ko'ring yoki /status ni tekshiring.")
    except Exception as e:
        notify_task.cancel()
        logger.error(f"AI suhbat xato: {e}")
        await message.answer(f"❌ Xatolik: {e}")
    finally:
        typing_task.cancel()


async def _notify_if_slow(chat_id: int):
    """Agar javob 8 soniyadan ko'p ketsa, foydalanuvchini xabardor qiladi"""
    await asyncio.sleep(8)
    try:
        await bot.send_message(
            chat_id,
            "⏳ AI javob tayyorlanmoqda...\n"
            "Bu 10-30 soniya olishi mumkin (model band bo'lsa)."
        )
    except:
        pass


# ============== MAIN ==============
async def main():
    init_db()
    logger.info("✅ Bot ishga tushdi (v3.2 — Robust Edition)")

    asyncio.create_task(cron_scheduler())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
