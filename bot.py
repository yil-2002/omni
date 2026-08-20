#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Requirements:
    pip install aiogram aiohttp python-dotenv
"""

import os
import asyncio
import sqlite3
from datetime import datetime
from typing import Optional

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from dotenv import load_dotenv

# ============== KONFIGURATSIYA ==============
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

AI_BASE_URL = "https://punctured-old-playmaker.ngrok-free.dev/v1"
AI_MODEL = "openai/gpt-oss-120b"
AI_API_KEY = os.getenv("AI_API_KEY", "not-needed")
DB_PATH = "memory.db"

# Xavfsizlik: ADMIN_PASSWORD faqat "Yil-2002" bo'lganda bot ishga tushadi
if ADMIN_PASSWORD != "Yil-2002":
    raise SystemExit("❌ XATOLIK: ADMIN_PASSWORD .env da 'Yil-2002' bo'lishi shart!")

if not BOT_TOKEN or not ADMIN_ID_RAW:
    raise SystemExit("❌ XATOLIK: BOT_TOKEN va ADMIN_ID .env da ko'rsatilishi shart!")

ADMIN_ID = int(ADMIN_ID_RAW)


# ============== SQLITE BAZA (ZICHLANGAN XOTIRA) ==============
def init_db():
    """Bazani ishga tushirish — faqat 1 ta qator (id=1) saqlanadi"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            compressed_text TEXT NOT NULL DEFAULT ''
        )
    """)
    cur.execute("INSERT OR IGNORE INTO memory (id, compressed_text) VALUES (1, '')")
    conn.commit()
    conn.close()


def get_memory() -> str:
    """Zichlangan xotirani o'qish"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT compressed_text FROM memory WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def update_memory(text: str):
    """Zichlangan xotirani yangilash (eskinining o'rniga)"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE memory SET compressed_text = ? WHERE id = 1", (text,))
    conn.commit()
    conn.close()


# ============== AI CLIENT ==============
async def ai_chat(messages: list, temperature: float = 0.7) -> str:
    """OpenAI-compatible API ga so'rov"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_API_KEY}",
    }
    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 2000,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{AI_BASE_URL}/chat/completions", headers=headers, json=payload
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"AI API xato {resp.status}: {body}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"].strip()


async def compress_memory(old_memory: str, user_msg: str, assistant_msg: str) -> str:
    """
    Eski xotira + yangi suhbatni AI ga yuborib,
    bitta zichlangan matn (summary/facts) qilib qaytarish
    """
    prompt = f"""Siz xotira zichlashtirish tizimisiz. Eski xotira va yangi suhbatni EXTREMELY concise, qisqa fakt va xulosa shaklida birlashtiring. Faqat muhim ma'lumotlar, user preferences, va kontekstni saqlang. Ortiqcha so'zlarsiz, to'g'ridan-to'g'ri matn chiqaring.

Eski xotira:
{old_memory if old_memory else "[Bo'sh]"}

Yangi suhbat:
User: {user_msg}
Assistant: {assistant_msg}

ZICHLANGAN XOTIRA (faqat matn):"""

    messages = [
        {
            "role": "system",
            "content": "Siz xotira zichlashtiruvchisiz. Javobingiz faqatgina zichlangan xotira matnidan iborat bo'lsin, hech qanday izohsiz.",
        },
        {"role": "user", "content": prompt},
    ]
    return await ai_chat(messages, temperature=0.3)


# ============== VPS BOSHQARUV SKILL'LARI (PLACEHOLDER) ==============
async def vps_skill_restart(server_id: str):
    """Bu yerga VPS skill'lar tushadi"""
    pass


async def vps_skill_status(server_id: str):
    """Bu yerga VPS skill'lar tushadi"""
    pass


async def vps_skill_execute(server_id: str, command: str):
    """Bu yerga VPS skill'lar tushadi"""
    pass


async def vps_skill_deploy(server_id: str, repo_url: str):
    """Bu yerga VPS skill'lar tushadi"""
    pass


# ============== TELEGRAM BOT ==============
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def is_admin(event: Message | CallbackQuery) -> bool:
    """Faqat ADMIN_ID ga tegishli foydalanuvchiga ruxsat"""
    return event.from_user.id == ADMIN_ID


# --- Handlerlar ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message):
        return
    await message.answer(
        "👋 Bot ishga tushdi.\n\n"
        "✍️ Suhbatlashish uchun xabar yozing.\n"
        "🧠 Xotirani ko'rish/yuklash uchun /xotira"
    )


@dp.message(Command("xotira"))
async def cmd_memory(message: Message):
    if not is_admin(message):
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Yuklash", callback_data="download_memory")]
        ]
    )
    await message.answer("🧠 Xotira bo'limi:", reply_markup=kb)


@dp.callback_query(F.data == "download_memory")
async def download_memory(callback: CallbackQuery):
    if not is_admin(callback):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return

    await callback.answer()

    # Xotira matnini .txt fayl sifatida yuborish
    memory_text = get_memory()
    if not memory_text.strip():
        memory_text = "[Xotira hali bo'sh]"

    filename = f"memory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("=== ZICHLANGAN DOIMIY XOTIRA ===\n\n")
        f.write(memory_text)

    await callback.message.answer_document(
        FSInputFile(filename), caption="🧠 Sizning zichlangan xotirangiz"
    )
    os.remove(filename)


@dp.message(F.text)
async def handle_message(message: Message):
    if not is_admin(message):
        return

    user_text = message.text
    old_memory = get_memory()

    # 1) AI ga system prompt + user xabari yuborish
    system_prompt = (
        f"Siz foydalanuvchining shaxsiy yordamchisisiz. "
        f"Quyidagi matn sizning doimiy xotirangizdir. Unga asoslanib javob bering.\n\n"
        f"XOTIRA:\n{old_memory if old_memory else '[Hali xotira yo\\'q]'}"
    )

    try:
        assistant_text = await ai_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ]
        )
    except Exception as e:
        await message.answer(f"❌ AI xatolik: {e}")
        return

    # 2) Javobni foydalanuvchiga yuborish
    await message.answer(assistant_text)

    # 3) Suhbatdan so'ng xotirani fonda zichlashtirish va yangilash
    asyncio.create_task(
        _background_compress_and_save(old_memory, user_text, assistant_text)
    )


async def _background_compress_and_save(
    old_memory: str, user_msg: str, assistant_msg: str
):
    """Har bir suhbatdan so'ng eski xotira + yangi dialogni zichlashtirish"""
    try:
        new_memory = await compress_memory(old_memory, user_msg, assistant_msg)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, update_memory, new_memory)
    except Exception as e:
        print(f"[XOTIRA XATOSI] {datetime.now()}: {e}")


# ============== MAIN ==============
async def main():
    init_db()
    print(f"✅ Bot ishga tushdi. Admin ID: {ADMIN_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
