#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Requirements:
    pip install aiogram aiohttp python-dotenv
"""

import os
import sys
import asyncio
import sqlite3
import json as json_mod
import subprocess
import shlex
import re
import traceback
import logging
from datetime import datetime

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

AI_BASE_URL = "https://punctured-old-playmaker.ngrok-free.dev/v1"
AI_MODEL = "openai/gpt-oss-120b"
AI_API_KEY = os.getenv("AI_API_KEY", "not-needed")
DB_PATH = "memory.db"

if ADMIN_PASSWORD != "Yil-2002":
    raise SystemExit("ADMIN_PASSWORD .env da 'Yil-2002' bo'lishi shart!")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN .env da ko'rsatilishi shart!")

# ============== AUTH ==============
authenticated_chats = set()


def is_authenticated(chat_id: int) -> bool:
    return chat_id in authenticated_chats


# ============== SQLITE BAZA ==============
def init_db():
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
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT compressed_text FROM memory WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def update_memory(text: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE memory SET compressed_text = ? WHERE id = 1", (text,))
    conn.commit()
    conn.close()


# ============== AI CLIENT (MUSTAHKAM) ==============
async def ai_chat(messages: list, temperature: float = 0.7) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_API_KEY}",
    }
    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 4000,
        "stream": False,
    }

    last_error = ""
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{AI_BASE_URL}/chat/completions", headers=headers, json=payload
                ) as resp:
                    text = await resp.text()

                    if resp.status == 429:
                        last_error = text[:500]
                        logger.warning(f"429 Rate Limit (attempt {attempt+1}): {last_error}")
                        # Kutish va retry
                        wait = 5 * (attempt + 1)
                        logger.info(f"{wait}s kutib retry...")
                        await asyncio.sleep(wait)
                        continue

                    if resp.status != 200:
                        raise RuntimeError(f"AI API xato {resp.status}: {text[:500]}")

                    # Try regular JSON first
                    try:
                        data = json_mod.loads(text)
                        return data["choices"][0]["message"]["content"].strip()
                    except json_mod.JSONDecodeError:
                        pass

                    # Parse SSE format
                    full_content = ""
                    for line in text.split("\n"):
                        line = line.strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json_mod.loads(data_str)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    choice = chunk["choices"][0]
                                    if "delta" in choice and "content" in choice["delta"]:
                                        full_content += choice["delta"]["content"]
                                    elif "message" in choice and "content" in choice["message"]:
                                        full_content += choice["message"]["content"]
                            except:
                                continue

                    if full_content:
                        return full_content.strip()

                    raise RuntimeError(f"Javobni tushunish mumkin emas: {text[:500]}")

        except RuntimeError:
            raise
        except Exception as e:
            last_error = str(e)
            logger.warning(f"AI ulanish xatosi (attempt {attempt+1}): {e}")
            await asyncio.sleep(3)

    raise RuntimeError(f"AI 3 marta urinib bo'ldi, ishlamadi. Oxirgi xato: {last_error}")


async def compress_memory(old_memory: str, user_msg: str, assistant_msg: str) -> str:
    old_mem_text = old_memory if old_memory else "[Bo'sh]"
    prompt = (
        "Siz xotira zichlashtirish tizimisiz. Eski xotira va yangi suhbatni "
        "EXTREMELY concise, qisqa fakt va xulosa shaklida birlashtiring. "
        "Faqat muhim ma'lumotlar, user preferences, va kontekstni saqlang. "
        "Ortiqcha so'zlarsiz, to'g'ridan-to'g'ri matn chiqaring.\n\n"
        f"Eski xotira:\n{old_mem_text}\n\n"
        f"Yangi suhbat:\nUser: {user_msg}\n"
        f"Assistant: {assistant_msg}\n\n"
        "ZICHLANGAN XOTIRA (faqat matn):"
    )

    messages = [
        {
            "role": "system",
            "content": (
                "Siz xotira zichlashtiruvchisiz. Javobingiz faqatgina "
                "zichlangan xotira matnidan iborat bo'lsin, hech qanday izohsiz."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    return await ai_chat(messages, temperature=0.3)


# ============== VPS TOOL'LARI ==============
async def tool_read_file(path: str) -> str:
    try:
        if not os.path.exists(path):
            return f"❌ Fayl topilmadi: {path}"
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if len(content) > 8000:
            content = content[:8000] + "\n\n... (fayl juda katta, qisqartirildi)"
        return f"📄 {path}:\n```\n{content}\n```"
    except Exception as e:
        return f"❌ Xato: {e}"


async def tool_write_file(path: str, content: str) -> str:
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ {path} ga yozildi ({len(content)} belgi)"
    except Exception as e:
        return f"❌ Xato: {e}"


async def tool_execute_shell(command: str) -> str:
    try:
        dangerous = ["rm -rf /", "mkfs.", ":(){ :|:& };:", "dd if=/dev/zero", "> /dev/sda"]
        for d in dangerous:
            if d in command:
                return "🚫 Xavfli buyruq bloklandi!"

        result = subprocess.run(
            command, shell=True, capture_output=True, 
            text=True, timeout=60, cwd="/root"
        )
        output = result.stdout
        if result.stderr:
            output += f"\n\nSTDERR:\n{result.stderr}"
        if len(output) > 6000:
            output = output[:6000] + "\n\n... (natija qisqartirildi)"
        return output if output.strip() else "✅ Buyruq muvaffaqiyatli bajarildi (bo'sh natija)"
    except subprocess.TimeoutExpired:
        return "⏰ Buyruq 60 soniyada bajarilmadi"
    except Exception as e:
        return f"❌ Xato: {e}"


async def tool_list_files(path: str = ".") -> str:
    try:
        result = subprocess.run(
            f"ls -lah {shlex.quote(path)}", 
            shell=True, capture_output=True, text=True, timeout=10
        )
        return result.stdout if result.stdout else result.stderr
    except Exception as e:
        return f"❌ Xato: {e}"


async def tool_search_code(path: str, pattern: str) -> str:
    try:
        result = subprocess.run(
            f"grep -rn {shlex.quote(pattern)} {shlex.quote(path)} 2>/dev/null | head -30",
            shell=True, capture_output=True, text=True, timeout=15
        )
        return result.stdout if result.stdout else "Hech narsa topilmadi"
    except Exception as e:
        return f"❌ Xato: {e}"


# ============== AGENT SYSTEM ==============
AGENT_SYSTEM_PROMPT = """Siz "OmniAgent" avtonom VPS yordamchisisiz. Foydalanuvchi topshirig'ini VPS ichida bajarish uchun tool'lardan foydalanasiz.

SIZNING TOOL'LARINGIZ (har bir javobda FAQAT BITTA tool ishlating):

1. read_file - Faylni o'qish
   FORMAT: {"tool": "read_file", "path": "/root/speedpro/bot.py"}

2. write_file - Faylga yozish
   FORMAT: {"tool": "write_file", "path": "/root/speedpro/bot.py", "content": "import os\n..."}

3. execute_shell - Shell buyruqni bajarish
   FORMAT: {"tool": "execute_shell", "command": "ls -la /root/speedpro"}

4. list_files - Fayllar ro'yxatini ko'rish
   FORMAT: {"tool": "list_files", "path": "/root/speedpro"}

5. search_code - Kod ichidan qidirish
   FORMAT: {"tool": "search_code", "path": "/root/speedpro", "pattern": "def main"}

QOIDALAR:
- Har bir javobda FAQAT BITTA JSON obyekt bo'lishi kerak
- Agar vazifa tugagan bo'lsa, {"done": true, "answer": "yakuniy xabar"} formatida javob bering
- write_file da content ichida \\n yangi qatorni anglatadi
- Xavfsizlik: rm -rf / kabi buyruqlarni BAJARMAGAN BO'LING
- Avval faylni o'qing, keyin tahlil qiling, keyin tuzating
- Har bir qadamda nima qilayotganingizni tushuntiring (THOUGHT: ... bilan boshlang)

SIZNING XOTIRANGIZ:
"""


async def agent_execute(chat_id: int, user_request: str, memory: str) -> str:
    system_msg = AGENT_SYSTEM_PROMPT + (memory if memory else "[Bo'sh]")
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": f"TOPSHIRIQ: {user_request}\n\nIltimos, THOUGHT bilan boshlang va keyin JSON formatida action bajaring."}
    ]

    max_steps = 15
    step = 0
    logs = []

    while step < max_steps:
        step += 1
        try:
            response = await ai_chat(messages, temperature=0.2)
        except Exception as e:
            return f"❌ AI bilan bog'lanishda xato: {e}\n\nBajarilgan qadamlar:\n" + "\n".join(logs)

        logs.append(f"\n--- Qadam {step} ---")
        logs.append(response[:500])

        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if not json_match:
            logs.append("(JSON topilmadi, yakuniy javob sifatida qabul qilindi)")
            return f"✅ Agent javobi ({step} qadam):\n\n{response}\n\n---\nBajarilgan qadamlar:\n" + "\n".join(logs)

        try:
            data = json_mod.loads(json_match.group())
        except:
            logs.append("(JSON parse xatosi)")
            return f"⚠️ Agent to'xtadi ({step} qadam)\n\n{response[:1000]}\n\n---\nBajarilgan qadamlar:\n" + "\n".join(logs)

        # Check if done
        if data.get("done"):
            answer = data.get("answer", "Vazifa tugallandi")
            return f"✅ Vazifa tugallandi ({step} qadam)\n\n📋 NATIJA:\n{answer}\n\n---\nBajarilgan qadamlar:\n" + "\n".join(logs)

        # Execute tool
        tool_name = data.get("tool")
        params = data

        if tool_name == "read_file":
            result = await tool_read_file(params.get("path", ""))
        elif tool_name == "write_file":
            result = await tool_write_file(params.get("path", ""), params.get("content", ""))
        elif tool_name == "execute_shell":
            result = await tool_execute_shell(params.get("command", ""))
        elif tool_name == "list_files":
            result = await tool_list_files(params.get("path", "."))
        elif tool_name == "search_code":
            result = await tool_search_code(params.get("path", ""), params.get("pattern", ""))
        else:
            result = f"❌ Noma'lum tool: {tool_name}"

        logs.append(f"🔧 Natija: {result[:300]}...")

        messages.append({"role": "assistant", "content": response})
        messages.append({
            "role": "user", 
            "content": f"TOOL NATIJASI:\n{result}\n\nDavom eting. Agar vazifa tugagan bo'lsa {{'done': true, 'answer': '...'}} formatida javob bering."
        })

    return f"⚠️ {max_steps} qadamdan oshib ketdi.\n\nBajarilganlar:\n" + "\n".join(logs)


# ============== YORDAMCHI ==============
async def send_long_message(message: Message, text: str):
    try:
        if len(text) <= 4096:
            await message.answer(text)
        else:
            filename = f"result_{datetime.now().strftime('%H%M%S')}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text)
            await message.answer_document(FSInputFile(filename), caption="📄 Natija juda uzun")
            os.remove(filename)
    except Exception as e:
        logger.error(f"send_long_message xato: {e}")
        await message.answer(f"❌ Xabar yuborishda xato: {e}")


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


@dp.message(Command("start"))
async def cmd_start(message: Message):
    try:
        if not is_authenticated(message.chat.id):
            await message.answer("🔐 Botdan foydalanish uchun parolni kiriting:")
            return
        await message.answer(
            "👋 Xush kelibsiz!\n\n"
            "✍️ Suhbatlashish uchun xabar yozing.\n"
            "🤖 Agent rejimi: 'speedpro bot ni tekshir va tuzat' deb yozing\n"
            "📁 /fayl <yo'l> - faylni o'qish\n"
            "💻 /buyruq <command> - shell buyruq\n"
            "🔍 /qidir <yo'l> <pattern> - kod qidirish\n"
            "📊 /status - bot holati"
        )
    except Exception as e:
        logger.error(f"/start xato: {e}")
        await message.answer("❌ Xatolik yuz berdi. Log: bot.log")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    try:
        if not is_authenticated(message.chat.id):
            await message.answer("🔐 Avval parolni kiriting:")
            return

        # AI health check
        ai_status = "✅ AI ulanish OK"
        try:
            await ai_chat([
                {"role": "system", "content": "Hi"},
                {"role": "user", "content": "Hi"}
            ], temperature=0.1)
        except Exception as e:
            ai_status = f"❌ AI ulanishda muammo: {str(e)[:200]}"

        mem_size = len(get_memory())

        await message.answer(
            f"📊 Bot holati:\n"
            f"✅ Bot: Online\n"
            f"{ai_status}\n"
            f"🧠 Xotira hajmi: {mem_size} belgi\n"
            f"💾 DB: {DB_PATH}"
        )
    except Exception as e:
        logger.error(f"/status xato: {e}")
        await message.answer(f"❌ Status olishda xato: {e}")


@dp.message(Command("xotira"))
async def cmd_memory(message: Message):
    try:
        if not is_authenticated(message.chat.id):
            await message.answer("🔐 Avval parolni kiriting:")
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📥 Yuklash", callback_data="download_memory")]
            ]
        )
        await message.answer("🧠 Xotira bo'limi:", reply_markup=kb)
    except Exception as e:
        logger.error(f"/xotira xato: {e}")
        await message.answer(f"❌ Xatolik: {e}")


@dp.callback_query(F.data == "download_memory")
async def download_memory(callback: CallbackQuery):
    try:
        if not is_authenticated(callback.message.chat.id):
            await callback.answer("🔐 Avval parolni kiriting!", show_alert=True)
            return

        await callback.answer()

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
    except Exception as e:
        logger.error(f"download_memory xato: {e}")
        await callback.message.answer(f"❌ Xatolik: {e}")


@dp.message(Command("fayl"))
async def cmd_file(message: Message):
    try:
        if not is_authenticated(message.chat.id):
            await message.answer("🔐 Avval parolni kiriting:")
            return
        args = message.text.split(" ", 1)
        if len(args) < 2:
            await message.answer("📁 Foydalanish: /fayl <yo'l>\nMasalan: /fayl /root/speedpro/bot.py")
            return
        result = await tool_read_file(args[1])
        await send_long_message(message, result)
    except Exception as e:
        logger.error(f"/fayl xato: {e}")
        await message.answer(f"❌ Xatolik: {e}")


@dp.message(Command("buyruq"))
async def cmd_shell(message: Message):
    try:
        if not is_authenticated(message.chat.id):
            await message.answer("🔐 Avval parolni kiriting:")
            return
        args = message.text.split(" ", 1)
        if len(args) < 2:
            await message.answer("💻 Foydalanish: /buyruq <command>\nMasalan: /buyruq ls -la")
            return
        await message.answer("⏳ Buyruq bajarilmoqda...")
        result = await tool_execute_shell(args[1])
        await send_long_message(message, result)
    except Exception as e:
        logger.error(f"/buyruq xato: {e}")
        await message.answer(f"❌ Xatolik: {e}")


@dp.message(Command("qidir"))
async def cmd_search(message: Message):
    try:
        if not is_authenticated(message.chat.id):
            await message.answer("🔐 Avval parolni kiriting:")
            return
        args = message.text.split(" ", 2)
        if len(args) < 3:
            await message.answer("🔍 Foydalanish: /qidir <yo'l> <pattern>\nMasalan: /qidir /root/speedpro def main")
            return
        result = await tool_search_code(args[1], args[2])
        await send_long_message(message, result)
    except Exception as e:
        logger.error(f"/qidir xato: {e}")
        await message.answer(f"❌ Xatolik: {e}")


@dp.message(F.text)
async def handle_message(message: Message):
    try:
        chat_id = message.chat.id
        user_text = message.text

        # Parol tekshiruvi
        if not is_authenticated(chat_id):
            if user_text == ADMIN_PASSWORD:
                authenticated_chats.add(chat_id)
                await message.answer(
                    "✅ Parol tasdiqlandi!\n\n"
                    "✍️ Suhbatlashish uchun xabar yozing.\n"
                    "🤖 Agent rejimi: 'speedpro bot ni tekshir va tuzat'\n"
                    "📁 /fayl <yo'l> - faylni o'qish\n"
                    "💻 /buyruq <command> - shell buyruq\n"
                    "🔍 /qidir <yo'l> <pattern> - kod qidirish\n"
                    "📊 /status - bot holati"
                )
            else:
                await message.answer("❌ Noto'g'ri parol. Qayta urinib ko'ring:")
            return

        old_memory = get_memory()

        # Agent rejimini tekshirish
        agent_keywords = ["tekshir", "tuzat", "xatoni top", "fix", "debug", "bajar", "yozib ber", "yarat", "yangil", "update", "o'qib ber"]
        is_agent_request = any(kw in user_text.lower() for kw in agent_keywords) and len(user_text) > 10

        if is_agent_request:
            await message.answer("🤖 Agent ishga tushdi. Bu bir necha daqiqa olishi mumkin...")
            try:
                result = await agent_execute(chat_id, user_text, old_memory)
                await send_long_message(message, result)

                asyncio.create_task(
                    _background_compress_and_save(old_memory, user_text, result)
                )
            except Exception as e:
                logger.error(f"Agent xato: {e}")
                await message.answer(f"❌ Agent xatosi: {e}")
            return

        # Oddiy suhbat
        mem_block = old_memory if old_memory else "[Hali xotira yo'q]"

        system_prompt = (
            "Siz foydalanuvchining shaxsiy yordamchisisiz. "
            "Quyidagi matn sizning doimiy xotirangizdir. Unga asoslanib javob bering.\n\n"
            f"XOTIRA:\n{mem_block}"
        )

        try:
            assistant_text = await ai_chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ]
            )
        except RuntimeError as e:
            if "429" in str(e) or "Rate limit" in str(e):
                await message.answer(
                    "⏳ AI hozircha band (Rate Limit).\n"
                    "Iltimos, 1-2 daqiqa kutib qayta urinib ko'ring.\n\n"
                    "📊 /status - bot holatini ko'rish\n"
                    "🧠 /xotira - xotira bilan ishlash (AI talab qilmaydi)"
                )
            else:
                await message.answer(f"❌ AI xatolik: {e}")
            return
        except Exception as e:
            logger.error(f"AI suhbat xato: {e}")
            await message.answer(f"❌ AI xatolik: {e}")
            return

        await send_long_message(message, assistant_text)

        asyncio.create_task(
            _background_compress_and_save(old_memory, user_text, assistant_text)
        )
    except Exception as e:
        logger.error(f"handle_message umumiy xato: {e}\n{traceback.format_exc()}")
        try:
            await message.answer("❌ Kutilmagan xatolik. Log: bot.log")
        except:
            pass


async def _background_compress_and_save(
    old_memory: str, user_msg: str, assistant_msg: str
):
    try:
        new_memory = await compress_memory(old_memory, user_msg, assistant_msg)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, update_memory, new_memory)
    except Exception as e:
        logger.error(f"[XOTIRA XATOSI] {datetime.now()}: {e}")


# ============== MAIN ==============
async def main():
    init_db()
    logger.info("✅ Bot ishga tushdi.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
