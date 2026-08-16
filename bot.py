#!/usr/bin/env python3
"""
VPS Buddy — OmniRoute + Telegram Bot
Moslangan versiya: Ollama o'rniga OmniRoute, SSH o'rniga local shell
"""

import os
import sys
import json
import logging
import subprocess
import re
import shutil
import uuid
from datetime import datetime
from dotenv import load_dotenv

import requests
import aiohttp

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============ .env yuklash ============
load_dotenv()

# ============ Konfiguratsiya ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# 3 ta admin ID (vergul bilan ajratilgan)
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "0")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]

OMNI_URL = os.getenv("OMNI_URL", "http://localhost:20128/v1/chat/completions")
OMNI_KEY = os.getenv("OMNI_KEY", "not-needed")
OMNI_MODEL = os.getenv("OMNI_MODEL", "gpt-4o-mini")

PROJECT_DIR = os.getenv("PROJECT_DIR", "/root/antigravity-project")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/root/antigravity-project/bot-output")
CHAT_DIR = os.path.join(PROJECT_DIR, "chats")
TASK_DIR = os.path.join(PROJECT_DIR, "tasks")

MAX_HISTORY = 20
TELEGRAM_MAX_MSG = 4096

# Papkalarni yaratish
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CHAT_DIR, exist_ok=True)
os.makedirs(TASK_DIR, exist_ok=True)

# ============ Logging ============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============ Xavfsizlik ============
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"mkfs\.",
    r"dd\s+if=",
    r":\(\)\s*\{\s*:\|\s*:",
    r"\bpoweroff\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bshutdown\b",
    r">?\s*/dev/[sh]da",
    r"chmod\s+-R\s+777\s+/",
    r"curl\s+.*\s*\|\s*sh",
    r"wget\s+.*\s*\|\s*sh",
    r"kill\s+-9\s+-1",
    r"\bsu\b",
    r":\(\)\{\s*:\|\s*:\s*\}&",
]

UNSAFE_COMMANDS = [
    "halt", "shutdown -h now", "dd if=/dev/zero",
    ":(){ :|: & };:", "poweroff", "reboot",
]

INTERACTIVE_COMMANDS = [
    "htop", "top", "nano", "vim", "vi", "less", "more", "watch",
]

INTERACTIVE_COMMAND_MESSAGE = (
    "Buyruq `{command}` interaktiv va bu kontekstda ishga tushirish mumkin emas. "
    "Alternativadan foydalaning (masalan, `ps aux` yoki `top -b -n 1`)."
)

# ============ Yordamchi funksiyalar ============

def is_admin(user_id: int) -> bool:
    if not ADMIN_IDS or ADMIN_IDS == [0]:
        return True
    return user_id in ADMIN_IDS


def is_dangerous(command: str) -> bool:
    cmd_lower = command.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd_lower):
            return True
    for unsafe in UNSAFE_COMMANDS:
        if unsafe in cmd_lower:
            return True
    return False


def detect_extension(text: str) -> str:
    t = text.lower()
    if "```python" in t or "```py" in t:
        return "py"
    if "```bash" in t or "```sh" in t:
        return "sh"
    if "```javascript" in t or "```js" in t:
        return "js"
    if "```html" in t:
        return "html"
    if "```css" in t:
        return "css"
    if "```go" in t:
        return "go"
    if "```rust" in t:
        return "rs"
    if "```cpp" in t or "```c++" in t:
        return "cpp"
    if "```java" in t:
        return "java"
    return "txt"


async def send_to_admins(context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode="HTML"):
    """Barcha adminlarga xabar yuborish"""
    for admin_id in ADMIN_IDS:
        if admin_id and admin_id != 0:
            try:
                await context.bot.send_message(chat_id=admin_id, text=text, parse_mode=parse_mode)
            except Exception as e:
                logger.error(f"Admin {admin_id} ga xabar yuborishda xatolik: {e}")


async def send_output_in_chunks(reply_func, output: str, prefix: str = ""):
    """Uzun natijani bo'laklarga bo'lib yuborish"""
    if not output:
        await reply_func(f"{prefix}(bo'sh natija)")
        return
    lines = output.splitlines()
    current_chunk = prefix
    for line in lines:
        line_with_newline = line + "\n"
        if len(current_chunk) + len(line_with_newline) > TELEGRAM_MAX_MSG:
            if current_chunk != prefix:
                await reply_func(current_chunk.rstrip())
            current_chunk = prefix + line_with_newline
        else:
            current_chunk += line_with_newline
    if current_chunk != prefix:
        await reply_func(current_chunk.rstrip())


# ============ OmniRoute API ============

def omni_chat(messages: list, temperature: float = 0.7) -> str:
    """OmniRoute API orqali suhbat"""
    payload = {
        "model": OMNI_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {"Content-Type": "application/json"}
    if OMNI_KEY and OMNI_KEY != "not-needed":
        headers["Authorization"] = f"Bearer {OMNI_KEY}"
    try:
        resp = requests.post(OMNI_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OmniRoute xatosi: {e}")
        raise


# ============ Shell buyruqlari ============

def local_execute(command: str, cwd: str = PROJECT_DIR, timeout: int = 30) -> str:
    """Local shell buyruq bajarish"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        output = result.stdout + result.stderr
        return output if output.strip() else "(bo'sh natija)"
    except subprocess.TimeoutExpired:
        return "⏰ Buyruq 30 soniyadan oshiq vaqt davomida bajarildi."
    except Exception as e:
        return f"❌ Xatolik: {str(e)}"


# ============ Suhbat tarixi ============

def load_conversation(user_id: int) -> list:
    chat_file = os.path.join(CHAT_DIR, f"{user_id}.json")
    if os.path.exists(chat_file):
        try:
            with open(chat_file, "r") as f:
                return json.load(f)
        except:
            return []
    return []


def save_conversation(user_id: int, conversation: list):
    chat_file = os.path.join(CHAT_DIR, f"{user_id}.json")
    if len(conversation) > MAX_HISTORY:
        conversation = conversation[-MAX_HISTORY:]
    with open(chat_file, "w") as f:
        json.dump(conversation, f, indent=2)


# ============ Buyruq handlerlari ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return

    text = (
        "🤖 <b>VPS Buddy</b> (OmniRoute Edition)\n\n"
        "📋 <b>Buyruqlar:</b>\n"
        "• /code &lt;vazifa&gt; — AI dan kod yozish\n"
        "• /run &lt;buyruq&gt; — VPS da shell buyruq\n"
        "• /models — AI modellar ro'yxati\n"
        "• /status — VPS va OmniRoute holati\n"
        "• /myid — Telegram ID ingiz\n"
        "• /stop — Joriy vazifani to'xtatish\n\n"
        "💬 Shunchaki matn yuboring — AI suhbat"
    )
    await update.message.reply_text(text, parse_mode="HTML")

    # Adminlarga xabar
    await send_to_admins(
        context,
        f"🔔 <b>Yangi foydalanuvchi</b>\n"
        f"ID: <code>{user.id}</code>\n"
        f"Ism: {user.first_name}\n"
        f"@{user.username or 'noma\'lum'}"
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"Ism: {user.first_name}"
    )
    if user.username:
        text += f"\n@{user.username}"
    await update.message.reply_text(text, parse_mode="HTML")


async def code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    if not context.args:
        await update.message.reply_text("❌ Foydalanish: /code python telegram bot yoza oladimi")
        return

    prompt = " ".join(context.args)
    await update.message.reply_text("⏰ Kod yozilmoqda...")

    try:
        messages = [
            {"role": "system", "content": "You are an expert programmer. Write clean, well-commented code. Use markdown code blocks with language identifier."},
            {"role": "user", "content": f"Write code for: {prompt}"},
        ]
        answer = omni_chat(messages)
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")
        return

    # Faylga saqlash
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = detect_extension(answer)
    filename = f"code_{ts}.{ext}"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Vazifa: {prompt}\n")
        f.write(f"# Vaqt: {datetime.now().isoformat()}\n")
        f.write(f"# Foydalanuvchi: {user.id}\n\n")
        f.write(answer)

    # Javob yuborish
    await update.message.reply_text(f"✅ Kod tayyor!\n\n{answer[:3500]}", parse_mode="Markdown")
    with open(filepath, "rb") as doc:
        await update.message.reply_document(document=doc, caption=f"📁 {filename}")

    # Adminlarga xabar
    await send_to_admins(
        context,
        f"📝 <b>Kod so'rovi</b>\n"
        f"Foydalanuvchi: <code>{user.id}</code>\n"
        f"Vazifa: {prompt[:100]}"
    )


async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    if not context.args:
        await update.message.reply_text("❌ Foydalanish: /run ls -la")
        return

    command = " ".join(context.args)

    if is_dangerous(command):
        await update.message.reply_text("🚫 Xavfli buyruq aniqlandi! Bajarish rad etildi.")
        # Adminlarga xabar
        await send_to_admins(
            context,
            f"🚨 <b>Xavfli buyruq urinishi!</b>\n"
            f"Foydalanuvchi: <code>{user.id}</code>\n"
            f"Buyruq: <code>{command}</code>"
        )
        return

    cmd_base = command.split()[0] if command else ""
    if cmd_base in INTERACTIVE_COMMANDS:
        await update.message.reply_text(
            INTERACTIVE_COMMAND_MESSAGE.format(command=command),
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(f"⚡ Bajarilmoqda:\n<code>{command}</code>", parse_mode="HTML")

    output = local_execute(command)

    if len(output) > 4000:
        output = output[:4000] + "\n\n... (qisqartirildi)"

    await update.message.reply_text(f"📤 Natija:\n<pre>{output}</pre>", parse_mode="HTML")

    # Adminlarga xabar
    await send_to_admins(
        context,
        f"⚡ <b>Shell buyruq</b>\n"
        f"Foydalanuvchi: <code>{user.id}</code>\n"
        f"Buyruq: <code>{command}</code>"
    )


async def models_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    await update.message.reply_text("⏰ Modellar ro'yxati yuklanmoqda...")

    try:
        models_url = OMNI_URL.replace("/chat/completions", "/models")
        headers = {}
        if OMNI_KEY and OMNI_KEY != "not-needed":
            headers["Authorization"] = f"Bearer {OMNI_KEY}"
        resp = requests.get(models_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("data", [])
            text = f"🤖 <b>Mavjud modellar ({len(models)} ta):</b>\n\n"
            for m in models[:50]:
                text += f"• <code>{m.get('id', 'noma\'lum')}</code>\n"
            if len(models) > 50:
                text += f"\n... va yana {len(models)-50} ta"
        else:
            text = "❌ /models endpoint ishlamadi. Lekin OmniRoute ishlayapti."
    except Exception as e:
        text = f"❌ Xatolik: {str(e)}\nOmniRoute ishlayotganini tekshiring."

    await update.message.reply_text(text, parse_mode="HTML")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return

    try:
        load = os.getloadavg()
        load_str = f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}"
    except:
        load_str = "Noma'lum"

    try:
        disk = shutil.disk_usage("/")
        disk_pct = (disk.used / disk.total) * 100
        disk_str = f"{disk_pct:.1f}% ishlatilgan ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"
    except:
        disk_str = "Noma'lum"

    try:
        mem = shutil.disk_usage("/")
        mem_info = local_execute("free -h", timeout=5)
    except:
        mem_info = "Noma'lum"

    omni_status = "❌ O'chiq"
    try:
        resp = requests.get(
            OMNI_URL.replace("/v1/chat/completions", ""),
            timeout=5,
        )
        if resp.status_code in (200, 307, 404):
            omni_status = "✅ Ishlayapti"
    except:
        pass

    text = (
        f"📊 <b>VPS Status</b>\n"
        f"🌐 IP: <code>77.42.77.60</code>\n"
        f"⚡ Load: {load_str}\n"
        f"💾 Disk: {disk_str}\n"
        f"📝 Xotira:\n<pre>{mem_info}</pre>\n\n"
        f"🔗 <b>OmniRoute:</b> {omni_status}\n"
        f"🤖 Model: <code>{OMNI_MODEL}</code>\n"
        f"📝 URL: <code>{OMNI_URL}</code>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    await update.message.reply_text("🛑 Vazifa to'xtatildi (agar mavjud bo'lsa).")


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    if not update.message or not update.message.text:
        return
    if update.message.text.startswith("/"):
        return

    user_message = update.message.text
    await update.message.reply_text("⏰ O'ylayapman...")

    # Suhbat tarixini yuklash
    conversation = load_conversation(user.id)
    conversation.append({"role": "user", "content": user_message})

    messages = [
        {"role": "system", "content": "You are VPS Buddy, a helpful AI assistant running on a VPS. Be concise but informative."},
    ] + conversation[-MAX_HISTORY:]

    try:
        answer = omni_chat(messages)
        conversation.append({"role": "assistant", "content": answer})
        save_conversation(user.id, conversation)

        await update.message.reply_text(answer[:4000], parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")


# ============ Main ============

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.error("BOT_TOKEN sozlanmagan! .env faylni tekshiring.")
        sys.exit(1)

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("code", code_cmd))
    application.add_handler(CommandHandler("run", run_cmd))
    application.add_handler(CommandHandler("models", models_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("stop", stop_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    logger.info("VPS Buddy ishga tushdi...")
    application.run_polling()


if __name__ == "__main__":
    main()
