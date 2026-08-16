#!/usr/bin/env python3
"""VPS Buddy — OmniRoute (Ollama) + Telegram Bot"""
import os, sys, json, logging, subprocess, re, shutil, atexit
from datetime import datetime
from dotenv import load_dotenv
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest, Conflict, NetworkError

# ============================================================
# PID LOCK — faqat bitta instansiya ishlashi uchun
# ============================================================
PIDFILE = "/root/antigravity-project/vps_bot/bot.pid"

def check_single_instance():
    if os.path.exists(PIDFILE):
        try:
            with open(PIDFILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)  # jarayon mavjudmi?
            print(f"[XATO] Bot allaqachon ishlayapti (PID {old_pid}). Ikkinchi nusxa ishga tushirish mumkin emas.")
            sys.exit(1)
        except (OSError, ValueError):
            pass  # eski PID, faylni yangilaymiz
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.remove(PIDFILE) if os.path.exists(PIDFILE) else None)

check_single_instance()

# ============================================================
# Konfiguratsiya
# ============================================================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip()]
OMNI_URL = os.getenv("OMNI_URL", "http://localhost:20128/api/generate")
OMNI_KEY = os.getenv("OMNI_KEY", "not-needed")
OMNI_MODEL = os.getenv("OMNI_MODEL", "auto/best-coding")
PROJECT_DIR = os.getenv("PROJECT_DIR", "/root/antigravity-project")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/root/antigravity-project/bot-output")
CHAT_DIR = os.path.join(PROJECT_DIR, "chats")
for d in [OUTPUT_DIR, CHAT_DIR]:
    os.makedirs(d, exist_ok=True)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

DANGEROUS = [
    r"rm\s+-rf\s+/", r"mkfs\.", r"dd\s+if=",
    r":\(\)\s*\{\s*:\|\s*:", r"\bpoweroff\b", r"\breboot\b",
    r"\bshutdown\b", r">?\s*/dev/[sh]da",
    r"chmod\s+-R\s+777\s+/",
    r"curl\s+.*\s*\|\s*sh", r"wget\s+.*\s*\|\s*sh",
    r"kill\s+-9\s+-1"
]
UNSAFE = ["halt", "shutdown -h now", "dd if=/dev/zero", ":(){ :|: & };:", "poweroff", "reboot"]
INTERACTIVE = ["htop", "top", "nano", "vim", "vi", "less", "more", "watch"]
MAX_HIST = 20

# ============================================================
# Yordamchi funksiyalar
# ============================================================
def is_admin(uid):
    return (not ADMIN_IDS or ADMIN_IDS == [0]) or uid in ADMIN_IDS

def is_dangerous(cmd):
    c = cmd.lower()
    return any(re.search(p, c) for p in DANGEROUS) or any(u in c for u in UNSAFE)

def detect_ext(t):
    t = t.lower()
    return (
        "py" if "```python" in t or "```py" in t else
        "sh" if "```bash" in t or "```sh" in t else
        "js" if "```javascript" in t or "```js" in t else
        "html" if "```html" in t else
        "css" if "```css" in t else
        "go" if "```go" in t else
        "rs" if "```rust" in t else
        "cpp" if "```cpp" in t or "```c++" in t else
        "java" if "```java" in t else
        "txt"
    )

async def notify_admins(context, text):
    for aid in ADMIN_IDS:
        if aid and aid != 0:
            try:
                await context.bot.send_message(chat_id=aid, text=text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Admin {aid} ga xabar yuborib bo'lmadi: {e}")

async def safe_reply(update, text, parse_mode="Markdown", **kwargs):
    """Markdown xato bo'lsa, oddiy matn bilan yuboradi"""
    try:
        await update.message.reply_text(text, parse_mode=parse_mode, **kwargs)
    except BadRequest as e:
        logger.warning(f"Markdown xato: {e}. Oddiy matn yuborilmoqda.")
        await update.message.reply_text(text, **kwargs)
    except Exception as e:
        logger.error(f"Xabar yuborishda xato: {e}")

# ============================================================
# OmniRoute (Ollama) API
# ============================================================
def omni_generate(prompt, system=""):
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    payload = {"model": OMNI_MODEL, "prompt": full_prompt, "stream": False}
    headers = {"Content-Type": "application/json"}
    if OMNI_KEY and OMNI_KEY != "not-needed":
        headers["Authorization"] = f"Bearer {OMNI_KEY}"
    r = requests.post(OMNI_URL, json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json().get("response", "")

# ============================================================
# Shell
# ============================================================
def local_run(cmd, cwd=PROJECT_DIR, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        o = r.stdout + r.stderr
        return o if o.strip() else "(bo'sh natija)"
    except subprocess.TimeoutExpired:
        return "⏰ 30s dan oshdi"
    except Exception as e:
        return f"❌ {e}"

# ============================================================
# Suhbat tarixi
# ============================================================
def load_chat(uid):
    f = os.path.join(CHAT_DIR, f"{uid}.json")
    try:
        with open(f) as fh:
            return json.load(fh)
    except:
        return []

def save_chat(uid, conv):
    f = os.path.join(CHAT_DIR, f"{uid}.json")
    if len(conv) > MAX_HIST:
        conv = conv[-MAX_HIST:]
    with open(f, "w") as fh:
        json.dump(conv, fh, indent=2)

# ============================================================
# Buyruqlar
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    await update.message.reply_text(
        "🤖 <b>VPS Buddy</b>\n\n"
        "📋 <b>Buyruqlar:</b>\n"
        "• /code &lt;vazifa&gt; — AI dan kod\n"
        "• /run &lt;buyruq&gt; — Shell\n"
        "• /models — Modellar\n"
        "• /status — VPS holati\n"
        "• /myid — ID ingiz\n"
        "• /stop — To'xtatish\n\n"
        "💬 Matn yuboring — AI suhbat",
        parse_mode="HTML"
    )
    await update.message.reply_text(
        "📝 <b>Kod yozishni xohlaysizmi?</b>\n"
        "Misol: <code>/code python telegram bot</code>",
        parse_mode="HTML"
    )
    await notify_admins(context, f"🔔 <b>Yangi foydalanuvchi</b>\nID: <code>{u.id}</code>\nIsm: {u.first_name}")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    t = f"🆔 <b>ID:</b> <code>{u.id}</code>\nIsm: {u.first_name}"
    if u.username:
        t += f"\n@{u.username}"
    await update.message.reply_text(t, parse_mode="HTML")

async def code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id):
        return
    if not context.args:
        await update.message.reply_text(
            "❌ Foydalanish: <code>/code python telegram bot yoza oladimi</code>",
            parse_mode="HTML"
        )
        return
    prompt = " ".join(context.args)
    await update.message.reply_text("⏰ Kod yozilmoqda...")
    try:
        system = "You are an expert programmer. Write clean, well-commented code. Use markdown code blocks with language identifier."
        ans = omni_generate(f"Write code for: {prompt}", system)
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = detect_ext(ans)
    fn = f"code_{ts}.{ext}"
    fp = os.path.join(OUTPUT_DIR, fn)
    header = f"# Vazifa: {prompt}\n# Vaqt: {datetime.now().isoformat()}\n# User: {u.id}\n\n"
    with open(fp, "w", encoding="utf-8") as f:
        f.write(header + ans)
    # Markdown xavfsiz yuborish
    await safe_reply(update, f"✅ Kod tayyor!\n\n{ans[:3500]}", parse_mode="Markdown")
    with open(fp, "rb") as f:
        await update.message.reply_document(document=f, caption=f"📁 {fn}")
    await notify_admins(context, f"📝 <b>Kod</b>\nUser: <code>{u.id}</code>\n{prompt[:100]}")

async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id):
        return
    if not context.args:
        await update.message.reply_text(
            "❌ Foydalanish: <code>/run ls -la</code>",
            parse_mode="HTML"
        )
        return
    cmd = " ".join(context.args)
    if is_dangerous(cmd):
        await update.message.reply_text("🚫 Xavfli buyruq bloklandi!")
        await notify_admins(context, f"🚨 <b>Xavfli!</b>\nUser: <code>{u.id}</code>\n<code>{cmd}</code>")
        return
    base = cmd.split()[0] if cmd else ""
    if base in INTERACTIVE:
        await update.message.reply_text(
            f"Buyruq `{cmd}` interaktiv. Alternativadan foydalaning.",
            parse_mode="Markdown"
        )
        return
    await update.message.reply_text(f"⚡ <code>{cmd}</code>", parse_mode="HTML")
    out = local_run(cmd)
    if len(out) > 4000:
        out = out[:4000] + "\n\n... (qisqartirildi)"
    await update.message.reply_text(f"📤 <pre>{out}</pre>", parse_mode="HTML")
    await notify_admins(context, f"⚡ <b>Shell</b>\nUser: <code>{u.id}</code>\n<code>{cmd}</code>")

async def models_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("⏰ Yuklanmoqda...")
    try:
        url = OMNI_URL.replace("/api/generate", "/api/tags")
        h = {}
        if OMNI_KEY and OMNI_KEY != "not-needed":
            h["Authorization"] = f"Bearer {OMNI_KEY}"
        r = requests.get(url, headers=h, timeout=10)
        if r.status_code == 200:
            data = r.json().get("models", [])
            t = f"🤖 <b>Modellar ({len(data)} ta):</b>\n\n"
            for x in data[:50]:
                name = x.get("name", x.get("model", "?"))
                t += f"• <code>{name}</code>\n"
            if len(data) > 50:
                t += f"\n... va yana {len(data)-50} ta"
        else:
            t = f"❌ /api/tags ishlamadi (status {r.status_code})"
    except Exception as e:
        t = f"❌ Xatolik: {str(e)}"
    await update.message.reply_text(t, parse_mode="HTML")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        load = os.getloadavg()
        ls = f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}"
    except:
        ls = "?"
    try:
        d = shutil.disk_usage("/")
        ds = f"{(d.used/d.total)*100:.1f}% ({d.used//(1024**3)}GB / {d.total//(1024**3)}GB)"
    except:
        ds = "?"
    mem = local_run("free -h", timeout=5)
    omni = "❌"
    try:
        base = OMNI_URL.replace("/api/generate", "")
        r = requests.get(base, timeout=5)
        if r.status_code in (200, 307, 404):
            omni = "✅"
    except:
        pass
    await update.message.reply_text(
        f"📊 <b>VPS Status</b>\n"
        f"🌐 <code>77.42.77.60</code>\n"
        f"⚡ Load: {ls}\n"
        f"💾 Disk: {ds}\n"
        f"📝 Xotira:\n<pre>{mem}</pre>\n\n"
        f"🔗 <b>OmniRoute:</b> {omni}\n"
        f"🤖 Model: <code>{OMNI_MODEL}</code>",
        parse_mode="HTML"
    )

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🛑 To'xtatildi.")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id):
        return
    if not update.message or not update.message.text or update.message.text.startswith("/"):
        return
    msg = update.message.text
    await update.message.reply_text("⏰ O'ylayapman...")
    conv = load_chat(u.id)
    conv.append({"role": "user", "content": msg})
    history = "\n".join([
        f"{'User' if c['role']=='user' else 'AI'}: {c['content']}"
        for c in conv[-MAX_HIST:]
    ])
    prompt = f"You are VPS Buddy, helpful AI on a VPS. Be concise.\n\n{history}\nAI:"
    try:
        ans = omni_generate(prompt)
        conv.append({"role": "assistant", "content": ans})
        save_chat(u.id, conv)
        # Markdown xavfsiz yuborish (kesilgan bo'lsa ham xato bermaydi)
        await safe_reply(update, ans[:4000], parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")

# ============================================================
# Xatoliklarni ushlash
# ============================================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xatolik: {context.error}", exc_info=context.error)
    if isinstance(context.error, Conflict):
        logger.error("❌ Conflict: boshqa bot instansi ishlayapti! Bot to'xtatilmoqda...")
        # PID faylni o'chirmasdan to'xtatamiz (boshqa instance ishlasin)
        sys.exit(1)
    elif isinstance(context.error, NetworkError):
        logger.warning(f"Tarmoq xatosi: {context.error}")
    elif update and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("❌ Ichki xatolik yuz berdi. Qayta urinib ko'ring.")
        except:
            pass

# ============================================================
# Main
# ============================================================
def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.error("BOT_TOKEN sozlanmagan!"); sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("code", code_cmd))
    app.add_handler(CommandHandler("run", run_cmd))
    app.add_handler(CommandHandler("models", models_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    app.add_error_handler(error_handler)

    logger.info("Bot ishga tushdi... (PID: %s)", os.getpid())
    app.run_polling()

if __name__ == "__main__":
    main()
