#!/usr/bin/env python3
"""VPS Buddy — OmniRoute (Ollama/OpenAI) + Telegram Bot — v2
Yangiliklar: /auth kirish kodi, chat/code uchun alohida modellar,
/image /video generatsiya, format-keshlash, batafsil xato xabarlari.
"""
import os, sys, json, logging, subprocess, re, shutil, atexit, base64
from datetime import datetime
from dotenv import load_dotenv
import requests
from telegram import Update
from telegram.constants import ChatAction
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
OMNI_MODEL = os.getenv("OMNI_MODEL", "auto/best-coding")     # umumiy zaxira model

# Chat va kod yozish uchun alohida modellar (.env da bo'sh bo'lsa avtomatik tanlanadi)
CHAT_MODEL = os.getenv("CHAT_MODEL", "") or OMNI_MODEL
CODE_MODEL = os.getenv("CODE_MODEL", "") or OMNI_MODEL

# Rasm / video generatsiya — .env da bo'sh bo'lsa o'chirilgan hisoblanadi
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "")
VIDEO_MODEL = os.getenv("VIDEO_MODEL", "")

# Kirish kodi tizimi — ADMIN bo'lmagan userlar shu kodni yuborsa botdan foydalana oladi
ACCESS_CODE = os.getenv("ACCESS_CODE", "yil-2002")

PROJECT_DIR = os.getenv("PROJECT_DIR", "/root/antigravity-project")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/root/antigravity-project/bot-output")
CHAT_DIR = os.path.join(PROJECT_DIR, "chats")
AUTH_FILE = os.path.join(PROJECT_DIR, "authorized_users.json")
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

# Aniqlangan OmniRoute format ("ollama" / "openai") — bir marta aniqlab keshlanadi
_OMNI_FORMAT = {"mode": None}

# ============================================================
# Ruxsat (access code) tizimi
# ============================================================
def load_authorized():
    try:
        with open(AUTH_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_authorized(ids):
    try:
        with open(AUTH_FILE, "w") as f:
            json.dump(list(ids), f)
    except Exception as e:
        logger.error(f"authorized_users.json yozilmadi: {e}")

AUTHORIZED_USERS = load_authorized()

def is_admin(uid):
    return (not ADMIN_IDS or ADMIN_IDS == [0]) or uid in ADMIN_IDS

def is_authorized(uid):
    """Admin yoki to'g'ri kirish kodini yuborgan foydalanuvchi"""
    return is_admin(uid) or uid in AUTHORIZED_USERS

# ============================================================
# Yordamchi funksiyalar
# ============================================================
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

async def send_long(update, text, parse_mode="Markdown", chunk=3800):
    """Uzun matnlarni bo'lib yuborish (kesmasdan, ma'lumot yo'qolmasligi uchun)"""
    if not text:
        text = "(bo'sh javob)"
    for i in range(0, len(text), chunk):
        part = text[i:i + chunk]
        try:
            await update.message.reply_text(part, parse_mode=parse_mode)
        except BadRequest:
            await update.message.reply_text(part)

def _omni_base():
    return OMNI_URL.replace("/api/generate", "").replace("/v1/chat/completions", "").rstrip("/")

# ============================================================
# Modellarni aniqlash
# ============================================================
def fetch_models():
    """OmniRoute'dan mavjud model nomlarini olish (Ollama yoki OpenAI formatida)"""
    base = _omni_base()
    names = []
    try:
        r = requests.get(base + "/api/tags", timeout=8)
        if r.status_code == 200:
            for m in r.json().get("models", []):
                n = m.get("name") or m.get("model")
                if n:
                    names.append(n)
    except Exception:
        pass
    if not names:
        try:
            r = requests.get(base + "/v1/models", timeout=8)
            if r.status_code == 200:
                for m in r.json().get("data", []):
                    n = m.get("id")
                    if n:
                        names.append(n)
        except Exception:
            pass
    return names

def auto_pick_models():
    """.env da CHAT_MODEL/CODE_MODEL berilmagan bo'lsa, mavjud modellardan avtomatik tanlaydi"""
    global CHAT_MODEL, CODE_MODEL
    names = fetch_models()
    if not names:
        logger.warning("OmniRoute'dan modellar ro'yxati olinmadi — .env dagi qiymatlar ishlatiladi.")
        return
    logger.info(f"OmniRoute'dagi modellar: {names}")
    if not os.getenv("CODE_MODEL"):
        coder = next((n for n in names if "code" in n.lower() or "coder" in n.lower()), None)
        CODE_MODEL = coder or names[0]
    if not os.getenv("CHAT_MODEL"):
        chat = next((n for n in names if n != CODE_MODEL), names[0])
        CHAT_MODEL = chat
    logger.info(f"Tanlangan modellar → CHAT_MODEL={CHAT_MODEL}  CODE_MODEL={CODE_MODEL}")

# ============================================================
# OmniRoute API — avtomatik format aniqlash + keshlash
# ============================================================
def _omni_ollama(prompt, system, model):
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    payload = {"model": model, "prompt": full_prompt, "stream": False}
    headers = {"Content-Type": "application/json"}
    if OMNI_KEY and OMNI_KEY != "not-needed":
        headers["Authorization"] = f"Bearer {OMNI_KEY}"
    url = _omni_base() + "/api/generate"
    r = requests.post(url, json=payload, headers=headers, timeout=90)
    r.raise_for_status()
    return r.json().get("response", "")

def _omni_openai(prompt, system, model):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": model, "messages": messages, "stream": False}
    headers = {"Content-Type": "application/json"}
    if OMNI_KEY and OMNI_KEY != "not-needed":
        headers["Authorization"] = f"Bearer {OMNI_KEY}"
    url = _omni_base() + "/v1/chat/completions"
    r = requests.post(url, json=payload, headers=headers, timeout=90)
    r.raise_for_status()
    data = r.json()
    if "choices" in data and len(data["choices"]) > 0:
        return data["choices"][0].get("message", {}).get("content", "")
    return ""

def omni_generate(prompt, system="", model=None):
    """Avval keshlangan formatni sinaydi, muvaffaqiyatsiz bo'lsa ikkinchisiga o'tadi."""
    model = model or CHAT_MODEL
    order = ["ollama", "openai"]
    if _OMNI_FORMAT["mode"] == "openai":
        order = ["openai", "ollama"]

    errors = []
    for fmt in order:
        try:
            result = _omni_ollama(prompt, system, model) if fmt == "ollama" else _omni_openai(prompt, system, model)
            _OMNI_FORMAT["mode"] = fmt  # keyingi safar to'g'ridan-to'g'ri shu formatdan boshlaymiz
            return result
        except requests.exceptions.HTTPError as e:
            body = ""
            try:
                body = e.response.text[:200]
            except Exception:
                pass
            errors.append(f"{fmt} ({e.response.status_code}): {body}")
        except Exception as e:
            errors.append(f"{fmt}: {e}")

    raise Exception(
        "OmniRoute javob bermadi:\n" + "\n".join(f"• {x}" for x in errors) +
        f"\n\nModel: {model}\n"
        f"Tekshiring: curl -s {_omni_base()}/api/tags\n"
        f"Yoki: /model buyrug'i bilan model nomini tekshiring/almashtiring"
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
    except Exception:
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
    if not is_authorized(u.id):
        await update.message.reply_text(
            "🔒 <b>Bu bot yopiq.</b>\n\n"
            "Kirish uchun kodni yuboring:\n"
            "<code>/auth kodingiz</code>",
            parse_mode="HTML"
        )
        await notify_admins(context, f"🔔 <b>Ruxsatsiz urinish</b>\nID: <code>{u.id}</code>\nIsm: {u.first_name}")
        return

    cmds = (
        "• /code &lt;vazifa&gt; — AI dan kod yozish\n"
        "• /image &lt;tavsif&gt; — Rasm generatsiya\n"
        "• /video &lt;tavsif&gt; — Video generatsiya\n"
        "• /reset — Suhbat tarixini tozalash\n"
    )
    if is_admin(u.id):
        cmds += (
            "• /run &lt;buyruq&gt; — Shell buyruq\n"
            "• /models — Mavjud modellar\n"
            "• /model — Chat/code modelini ko'rish yoki almashtirish\n"
            "• /status — VPS va OmniRoute holati\n"
        )
    cmds += "• /myid — ID ingiz\n• /stop — To'xtatish"

    await update.message.reply_text(
        f"🤖 <b>VPS Buddy</b>\n\n📋 <b>Buyruqlar:</b>\n{cmds}\n\n💬 Shunchaki matn yuboring — AI suhbat",
        parse_mode="HTML"
    )
    await update.message.reply_text(
        "📝 <b>Kod yozishni xohlaysizmi?</b>\nMisol: <code>/code python telegram bot</code>",
        parse_mode="HTML"
    )
    await notify_admins(context, f"🔔 <b>Foydalanuvchi /start bosdi</b>\nID: <code>{u.id}</code>\nIsm: {u.first_name}")

async def auth_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if is_authorized(u.id):
        await update.message.reply_text("✅ Sizda allaqachon ruxsat bor.")
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: <code>/auth kodingiz</code>", parse_mode="HTML")
        return
    code = " ".join(context.args).strip()
    if ACCESS_CODE and code == ACCESS_CODE:
        AUTHORIZED_USERS.add(u.id)
        save_authorized(AUTHORIZED_USERS)
        await update.message.reply_text("✅ Ruxsat berildi! /start ni qayta yuboring.")
        await notify_admins(context, f"🔓 <b>Yangi ruxsat</b>\nID: <code>{u.id}</code>\nIsm: {u.first_name}")
    else:
        await update.message.reply_text("❌ Noto'g'ri kod.")
        await notify_admins(context, f"🚫 <b>Noto'g'ri kod urinishi</b>\nID: <code>{u.id}</code>")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    t = f"🆔 <b>ID:</b> <code>{u.id}</code>\nIsm: {u.first_name}"
    if u.username:
        t += f"\n@{u.username}"
    await update.message.reply_text(t, parse_mode="HTML")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_authorized(u.id):
        return
    f = os.path.join(CHAT_DIR, f"{u.id}.json")
    try:
        os.remove(f)
    except Exception:
        pass
    await update.message.reply_text("🔄 Suhbat tarixi tozalandi.")

async def code_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_authorized(u.id):
        return
    if not context.args:
        await update.message.reply_text(
            "❌ <b>Vazifa kiritilmadi!</b>\n\nFoydalanish:\n"
            "<code>/code python telegram bot yoza oladimi</code>\n"
            "<code>/code flask rest api</code>\n"
            "<code>/code javascript calculator</code>",
            parse_mode="HTML"
        )
        return
    prompt = " ".join(context.args)
    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text(f"⏰ Kod yozilmoqda... (model: {CODE_MODEL})")
    try:
        system = "You are an expert programmer. Write clean, well-commented code. Use markdown code blocks with language identifier."
        # /code buyrug'i har doim CODE_MODEL ga (kod yozishga ixtisoslashgan modelga) yo'naltiriladi
        ans = omni_generate(f"Write code for: {prompt}", system, model=CODE_MODEL)
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik:\n<pre>{str(e)[:600]}</pre>", parse_mode="HTML")
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = detect_ext(ans)
    fn = f"code_{ts}.{ext}"
    fp = os.path.join(OUTPUT_DIR, fn)
    header = f"# Vazifa: {prompt}\n# Vaqt: {datetime.now().isoformat()}\n# User: {u.id}\n\n"
    with open(fp, "w", encoding="utf-8") as f:
        f.write(header + ans)
    await send_long(update, f"✅ Kod tayyor!\n\n{ans}")
    with open(fp, "rb") as f:
        await update.message.reply_document(document=f, caption=f"📁 {fn}")
    await notify_admins(context, f"📝 <b>Kod</b>\nUser: <code>{u.id}</code>\n{prompt[:100]}")

async def image_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_authorized(u.id):
        return
    if not IMAGE_MODEL:
        await update.message.reply_text(
            "🖼 <b>Rasm generatsiya sozlanmagan.</b>\n\n"
            "1) OmniRoute'da rasm modeli borligini tekshiring:\n"
            f"<code>curl -s {_omni_base()}/v1/models</code>\n"
            "2) .env fayliga qo'shing: <code>IMAGE_MODEL=model_nomi</code>\n"
            "3) Botni qayta ishga tushiring.",
            parse_mode="HTML"
        )
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: <code>/image mushukning tasviri</code>", parse_mode="HTML")
        return
    prompt = " ".join(context.args)
    await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
    await update.message.reply_text("🎨 Chizyapman...")
    try:
        r = requests.post(
            _omni_base() + "/v1/images/generations",
            json={"model": IMAGE_MODEL, "prompt": prompt, "n": 1},
            timeout=120
        )
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            raise Exception("Bo'sh javob qaytdi")
        item = data[0]
        if "url" in item:
            await update.message.reply_photo(item["url"], caption=f"🖼 {prompt[:200]}")
        elif "b64_json" in item:
            img_bytes = base64.b64decode(item["b64_json"])
            await update.message.reply_photo(img_bytes, caption=f"🖼 {prompt[:200]}")
        else:
            raise Exception("Noma'lum javob formati")
    except Exception as e:
        await update.message.reply_text(
            f"❌ Rasm generatsiya xatosi:\n<pre>{str(e)[:400]}</pre>\n\n"
            f"OmniRoute'da <code>/v1/images/generations</code> endpointi va "
            f"<code>{IMAGE_MODEL}</code> modeli mavjudligini tekshiring.",
            parse_mode="HTML"
        )

async def video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_authorized(u.id):
        return
    if not VIDEO_MODEL:
        await update.message.reply_text(
            "🎬 <b>Video generatsiya sozlanmagan.</b>\n\n"
            "OmniRoute'ning ko'pchilik o'rnatishlarida video generatsiya yo'q — "
            "avval mavjudligini tekshiring:\n"
            f"<code>curl -s {_omni_base()}/v1/models</code>\n"
            "Bo'lsa, .env ga <code>VIDEO_MODEL=model_nomi</code> qo'shing.",
            parse_mode="HTML"
        )
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: <code>/video mushuk yugurayapti</code>", parse_mode="HTML")
        return
    prompt = " ".join(context.args)
    await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
    await update.message.reply_text("🎬 Video tayyorlanmoqda, bu biroz vaqt olishi mumkin...")
    try:
        r = requests.post(
            _omni_base() + "/v1/videos/generations",
            json={"model": VIDEO_MODEL, "prompt": prompt},
            timeout=300
        )
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            raise Exception("Bo'sh javob qaytdi")
        item = data[0]
        if "url" in item:
            await update.message.reply_video(item["url"], caption=f"🎬 {prompt[:200]}")
        elif "b64_json" in item:
            vid_bytes = base64.b64decode(item["b64_json"])
            await update.message.reply_video(vid_bytes, caption=f"🎬 {prompt[:200]}")
        else:
            raise Exception("Noma'lum javob formati")
    except Exception as e:
        await update.message.reply_text(
            f"❌ Video generatsiya xatosi:\n<pre>{str(e)[:400]}</pre>\n\n"
            f"OmniRoute bu funksiyani qo'llab-quvvatlamasligi mumkin.",
            parse_mode="HTML"
        )

async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id):
        return
    if not context.args:
        await update.message.reply_text(
            "❌ <b>Buyruq kiritilmadi!</b>\n\nFoydalanish:\n"
            "<code>/run ls -la</code>\n<code>/run df -h</code>\n<code>/run ps aux | grep python</code>",
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
    names = fetch_models()
    if names:
        t = f"🤖 <b>Modellar ({len(names)} ta):</b>\n\n"
        for n in names[:50]:
            t += f"• <code>{n}</code>\n"
        if len(names) > 50:
            t += f"\n... va yana {len(names) - 50} ta"
        t += f"\n\nJoriy: chat=<code>{CHAT_MODEL}</code>, code=<code>{CODE_MODEL}</code>"
    else:
        t = "❌ Model ro'yxati olinmadi (/api/tags va /v1/models ikkalasi ham ishlamadi)."
    await update.message.reply_text(t, parse_mode="HTML")

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chat/code uchun ishlatiladigan modelni ko'rish yoki almashtirish (admin)"""
    if not is_admin(update.effective_user.id):
        return
    global CHAT_MODEL, CODE_MODEL
    if not context.args:
        await update.message.reply_text(
            f"🤖 Chat model: <code>{CHAT_MODEL}</code>\n"
            f"💻 Code model: <code>{CODE_MODEL}</code>\n\n"
            f"Almashtirish: <code>/model chat nom</code> yoki <code>/model code nom</code>",
            parse_mode="HTML"
        )
        return
    if len(context.args) < 2:
        await update.message.reply_text("Foydalanish: <code>/model chat qwen2.5</code>", parse_mode="HTML")
        return
    kind, name = context.args[0].lower(), " ".join(context.args[1:])
    if kind == "chat":
        CHAT_MODEL = name
    elif kind == "code":
        CODE_MODEL = name
    else:
        await update.message.reply_text("Birinchi so'z 'chat' yoki 'code' bo'lishi kerak.")
        return
    await update.message.reply_text(f"✅ {kind} model o'zgartirildi: <code>{name}</code>", parse_mode="HTML")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        load = os.getloadavg()
        ls = f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}"
    except Exception:
        ls = "?"
    try:
        d = shutil.disk_usage("/")
        ds = f"{(d.used / d.total) * 100:.1f}% ({d.used // (1024**3)}GB / {d.total // (1024**3)}GB)"
    except Exception:
        ds = "?"
    mem = local_run("free -h", timeout=5)
    base_url = _omni_base()
    omni_status = "❌"
    omni_detail = ""
    try:
        r = requests.get(base_url + "/api/tags", timeout=5)
        if r.status_code == 200:
            omni_status = "✅ Ollama (/api/tags)"
    except Exception:
        pass
    try:
        r = requests.get(base_url + "/v1/models", timeout=5)
        if r.status_code == 200:
            omni_status = "✅ OpenAI (/v1/models)"
    except Exception:
        pass
    try:
        r = requests.post(base_url + "/api/generate", json={"model": "test"}, timeout=5)
        omni_detail += "\n✅ /api/generate mavjud" if r.status_code != 404 else "\n❌ /api/generate 404"
    except Exception:
        omni_detail += "\n❌ /api/generate ulanmadi"
    try:
        r = requests.post(base_url + "/v1/chat/completions", json={"model": "test"}, timeout=5)
        omni_detail += "\n✅ /v1/chat/completions mavjud" if r.status_code != 404 else "\n❌ /v1/chat/completions 404"
    except Exception:
        omni_detail += "\n❌ /v1/chat/completions ulanmadi"

    await update.message.reply_text(
        f"📊 <b>VPS Status</b>\n"
        f"⚡ Load: {ls}\n"
        f"💾 Disk: {ds}\n"
        f"📝 Xotira:\n<pre>{mem}</pre>\n\n"
        f"🔗 <b>OmniRoute:</b> {omni_status}\n"
        f"🤖 Chat model: <code>{CHAT_MODEL}</code>\n"
        f"💻 Code model: <code>{CODE_MODEL}</code>\n"
        f"🖼 Image model: <code>{IMAGE_MODEL or 'sozlanmagan'}</code>\n"
        f"🎬 Video model: <code>{VIDEO_MODEL or 'sozlanmagan'}</code>\n"
        f"📡 Endpointlar:{omni_detail}\n"
        f"🔐 Kesh: format=<code>{_OMNI_FORMAT['mode'] or 'aniqlanmagan'}</code>",
        parse_mode="HTML"
    )

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🛑 To'xtatildi.")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_authorized(u.id):
        return
    if not update.message or not update.message.text or update.message.text.startswith("/"):
        return
    msg = update.message.text
    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text("⏰ O'ylayapman...")
    conv = load_chat(u.id)
    conv.append({"role": "user", "content": msg})
    history = "\n".join([
        f"{'User' if c['role'] == 'user' else 'AI'}: {c['content']}"
        for c in conv[-MAX_HIST:]
    ])
    prompt = f"You are VPS Buddy, helpful AI on a VPS. Be concise.\n\n{history}\nAI:"
    try:
        # Oddiy suhbat har doim CHAT_MODEL ga (chatni yaxshi tushunadigan modelga) yo'naltiriladi
        ans = omni_generate(prompt, model=CHAT_MODEL)
        conv.append({"role": "assistant", "content": ans})
        save_chat(u.id, conv)
        await send_long(update, ans)
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
        except Exception:
            pass

# ============================================================
# Main
# ============================================================
def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.error("BOT_TOKEN sozlanmagan!")
        sys.exit(1)

    try:
        auto_pick_models()
    except Exception as e:
        logger.warning(f"Model avto-aniqlash muvaffaqiyatsiz: {e}")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("auth", auth_cmd))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("code", code_cmd))
    app.add_handler(CommandHandler("image", image_cmd))
    app.add_handler(CommandHandler("video", video_cmd))
    app.add_handler(CommandHandler("run", run_cmd))
    app.add_handler(CommandHandler("models", models_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    app.add_error_handler(error_handler)

    logger.info("Bot ishga tushdi... (PID: %s)", os.getpid())
    logger.info(f"CHAT_MODEL={CHAT_MODEL}  CODE_MODEL={CODE_MODEL}")
    app.run_polling()

if __name__ == "__main__":
    main()
