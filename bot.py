#!/usr/bin/env python3
"""VPS Buddy — OmniRoute (Ollama/OpenAI) + Telegram Bot"""
import os, sys, json, logging, subprocess, re, shutil, atexit
from datetime import datetime
from dotenv import load_dotenv
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest, Conflict, NetworkError

# ============================================================
# PID LOCK — faqat bitta instansiya
# ============================================================
PIDFILE = "/root/antigravity-project/vps_bot/bot.pid"

def check_single_instance():
    if os.path.exists(PIDFILE):
        try:
            with open(PIDFILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            print(f"[XATO] Bot allaqachon ishlayapti (PID {old_pid}).")
            sys.exit(1)
        except (OSError, ValueError):
            pass
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
    try:
        await update.message.reply_text(text, parse_mode=parse_mode, **kwargs)
    except BadRequest as e:
        logger.warning(f"Markdown xato: {e}. Oddiy matn yuborilmoqda.")
        await update.message.reply_text(text, **kwargs)
    except Exception as e:
        logger.error(f"Xabar yuborishda xato: {e}")

# ============================================================
# OmniRoute API — avtomatik format aniqlash
# ============================================================
def _omni_ollama(prompt, system=""):
    """Ollama formatida so'rov"""
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    payload = {"model": OMNI_MODEL, "prompt": full_prompt, "stream": False}
    headers = {"Content-Type": "application/json"}
    if OMNI_KEY and OMNI_KEY != "not-needed":
        headers["Authorization"] = f"Bearer {OMNI_KEY}"
    url = OMNI_URL if "/api/generate" in OMNI_URL else OMNI_URL.rstrip("/") + "/api/generate"
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json().get("response", "")

def _omni_openai(prompt, system=""):
    """OpenAI formatida so'rov"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": OMNI_MODEL, "messages": messages, "stream": False}
    headers = {"Content-Type": "application/json"}
    if OMNI_KEY and OMNI_KEY != "not-needed":
        headers["Authorization"] = f"Bearer {OMNI_KEY}"
    # URLni aniqlash
    base = OMNI_URL.replace("/api/generate", "").replace("/v1/chat/completions", "").rstrip("/")
    url = base + "/v1/chat/completions"
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "choices" in data and len(data["choices"]) > 0:
        return data["choices"][0].get("message", {}).get("content", "")
    return ""

def omni_generate(prompt, system=""):
    """Avval Ollama, xato bo'lsa OpenAI formatida sinaydi"""
    errors = []
    # 1. Ollama formati
    try:
        return _omni_ollama(prompt, system)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            errors.append(f"Ollama (/api/generate) 404")
        else:
            raise
    except Exception as e:
        errors.append(f"Ollama: {e}")
    # 2. OpenAI formati
    try:
        return _omni_openai(prompt, system)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            errors.append(f"OpenAI (/v1/chat/completions) 404")
        else:
            raise
    except Exception as e:
        errors.append(f"OpenAI: {e}")
    # 3. Hech biri ishlamadi
    raise Exception(
        f"OmniRoute endpoint topilmadi.\n"
        f"• {errors[0] if len(errors) > 0 else 'Noma\'lum'}\n"
        f"• {errors[1] if len(errors) > 1 else 'Noma\'lum'}\n\n"
        f"Tekshiring: curl -s http://localhost:20128/api/tags | head -c 200"
    )

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
        "• /code &lt;vazifa&gt; — AI dan kod yozish\n"
        "• /run &lt;buyruq&gt; — Shell buyruq\n"
        "• /models — Mavjud modellar\n"
        "• /status — VPS va OmniRoute holati\n"
        "• /myid — ID ingiz\n"
        "• /stop — To'xtatish\n\n"
        "💬 Shunchaki matn yuboring — AI suhbat",
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
            "❌ <b>Vazifa kiritilmadi!</b>\n\n"
            "Foydalanish:\n"
            "<code>/code python telegram bot yoza oladimi</code>\n"
            "<code>/code flask rest api</code>\n"
            "<code>/code javascript calculator</code>",
            parse_mode="HTML"
        )
        return
    prompt = " ".join(context.args)
    await update.message.reply_text("⏰ Kod yozilmoqda...")
    try:
        system = "You are an expert programmer. Write clean, well-commented code. Use markdown code blocks with language identifier."
        ans = omni_generate(f"Write code for: {prompt}", system)
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik:\n<pre>{str(e)[:500]}</pre>", parse_mode="HTML")
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = detect_ext(ans)
    fn = f"code_{ts}.{ext}"
    fp = os.path.join(OUTPUT_DIR, fn)
    header = f"# Vazifa: {prompt}\n# Vaqt: {datetime.now().isoformat()}\n# User: {u.id}\n\n"
    with open(fp, "w", encoding="utf-8") as f:
        f.write(header + ans)
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
            "❌ <b>Buyruq kiritilmadi!</b>\n\n"
            "Foydalanish:\n"
            "<code>/run ls -la</code>\n"
            "<code>/run df -h</code>\n"
            "<code>/run ps aux | grep python</code>",
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
            f"⚠️ <code>{cmd}</code> interaktiv buyruq.\n"
            f"Alternativa: <code>/run {base} -b</code> yoki <code>/run echo 'done'</code>",
            parse_mode="HTML"
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
        url = OMNI_URL.replace("/api/generate", "").replace("/v1/chat/completions", "").rstrip("/") + "/api/tags"
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
    # OmniRoute holatini tekshirish
    omni_status = "❌"
    omni_detail = ""
    base_url = OMNI_URL.replace("/api/generate", "").replace("/v1/chat/completions", "").rstrip("/")
    try:
        r = requests.get(base_url + "/api/tags", timeout=5)
        if r.status_code == 200:
            omni_status = "✅ Ollama (/api/tags)"
    except:
        pass
    try:
        r = requests.get(base_url + "/v1/models", timeout=5)
        if r.status_code == 200:
            omni_status = "✅ OpenAI (/v1/models)"
    except:
        pass
    # generate endpointini tekshirish
    try:
        r = requests.post(base_url + "/api/generate", json={"model":"test"}, timeout=5)
        if r.status_code != 404:
            omni_detail += "\n✅ /api/generate mavjud"
        else:
            omni_detail += "\n❌ /api/generate 404"
    except:
        omni_detail += "\n❌ /api/generate ulanmadi"
    try:
        r = requests.post(base_url + "/v1/chat/completions", json={"model":"test"}, timeout=5)
        if r.status_code != 404:
            omni_detail += "\n✅ /v1/chat/completions mavjud"
        else:
            omni_detail += "\n❌ /v1/chat/completions 404"
    except:
        omni_detail += "\n❌ /v1/chat/completions ulanmadi"

    await update.message.reply_text(
        f"📊 <b>VPS Status</b>\n"
        f"🌐 <code>77.42.77.60</code>\n"
        f"⚡ Load: {ls}\n"
        f"💾 Disk: {ds}\n"
        f"📝 Xotira:\n<pre>{mem}</pre>\n\n"
        f"🔗 <b>OmniRoute:</b> {omni_status}\n"
        f"🤖 Model: <code>{OMNI_MODEL}</code>\n"
        f"📡 Endpointlar:{omni_detail}",
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
        await safe_reply(update, ans[:4000], parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik:\n<pre>{str(e)[:800]}</pre>", parse_mode="HTML")

# ============================================================
# Xatoliklarni ushlash
# ============================================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xatolik: {context.error}", exc_info=context.error)
    if isinstance(context.error, Conflict):
        logger.error("❌ Conflict: boshqa bot instansi ishlayapti! Bot to'xtatilmoqda...")
        sys.exit(1)
    elif isinstance(context.error, NetworkError):
        logger.warning(f"Tarmoq xatosi: {context.error}")
    elif update and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("❌ Ichki xatolik yuz berdi.")
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
