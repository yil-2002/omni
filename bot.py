#!/usr/bin/env python3
"""VPS Buddy — OmniRoute (OpenAI-compatible) + Telegram Bot — v3 (shaxsiy)
Xususiyatlar: /auth kirish kodi, kategoriyalangan+ballangan model tanlash,
/code (cancel + qayta yozish), inline mini-menyu (/app), OmniRoute health-check,
avtomatik qayta urinish (retry), batafsil xato xabarlari.
"""
import os, sys, json, logging, subprocess, re, shutil, atexit, math, time, asyncio
from datetime import datetime
from dotenv import load_dotenv
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
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
OMNI_MODEL = os.getenv("OMNI_MODEL", "auto/best-coding")   # zaxira/standart model

CODE_MODEL = os.getenv("CODE_MODEL", "") or OMNI_MODEL     # /code buyrug'i ishlatadigan model

ACCESS_CODE = os.getenv("ACCESS_CODE", "yil-2002")

PROJECT_DIR = os.getenv("PROJECT_DIR", "/root/antigravity-project")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/root/antigravity-project/bot-output")
AUTH_FILE = os.path.join(PROJECT_DIR, "authorized_users.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

# Aniqlangan OmniRoute format ("ollama" / "openai") — bir marta aniqlab keshlanadi
_OMNI_FORMAT = {"mode": None}
# OmniRoute holati (health-check uchun, faqat o'zgarganda xabar beriladi)
_OMNI_HEALTH = {"up": None}
# Model kategoriyalari keshi
_MODEL_CACHE = {"ts": 0, "data": {}}
# Har bir user uchun faol /code vazifasi
ACTIVE_TASKS = {}
# Har bir user uchun oxirgi /code so'rovi ("Qayta yoz" tugmasi uchun)
LAST_PROMPT = {}

CATEGORY_ORDER = ["🚀 Auto", "💎 Premium", "⚡ Tez/Groq", "🆓 Bepul"]

HELP_TEXT = (
    "🤖 <b>VPS Buddy — Yordam</b>\n\n"
    "• <code>/code &lt;vazifa&gt;</code> — AI dan kod yozish\n"
    "• <code>/cancel</code> — Ketayotgan /code vazifasini bekor qilish\n"
    "• <code>/model</code> — Kod yozish uchun model tanlash (kategoriya bo'yicha)\n"
    "• <code>/app</code> — Tezkor menyu (status/model/kod/yordam)\n"
    "• <code>/run &lt;buyruq&gt;</code> — Shell buyruq (admin)\n"
    "• <code>/models</code> — Barcha mavjud modellar (admin)\n"
    "• <code>/status</code> — VPS va OmniRoute holati (admin)\n"
    "• <code>/myid</code> — Telegram ID ingiz\n"
    "• <code>/stop</code> — To'xtatish\n"
)

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

def _omni_base():
    return OMNI_URL.replace("/api/generate", "").replace("/v1/chat/completions", "").rstrip("/")

# ============================================================
# Modellarni aniqlash, kategoriyalash va ballash
# ============================================================
def categorize_entry(entry):
    mid = entry.get("id", "") or ""
    typ = entry.get("type")
    if typ in ("audio", "video"):
        return None
    if mid.startswith("felo/"):
        return None
    if mid.startswith("auto/"):
        return "🚀 Auto"
    if mid.startswith("aug/"):
        return "💎 Premium"
    if mid.startswith("groq/") or mid.startswith("g4fgroq/") or mid.startswith("g4f-groq/"):
        return "⚡ Tez/Groq"
    return "🆓 Bepul"   # tllm/, oc/, ddgw/, mcode/, pepper/ va h.k.

def score_entry(entry):
    caps = entry.get("capabilities", {}) or {}
    s = 0.0
    if caps.get("reasoning"):
        s += 2
    if caps.get("thinking"):
        s += 2
    if caps.get("tool_calling"):
        s += 1
    if caps.get("vision"):
        s += 1
    ctx = entry.get("context_length") or entry.get("max_input_tokens") or 0
    try:
        s += math.log10(max(int(ctx), 1))
    except Exception:
        pass
    return round(s, 1)

def fetch_categorized_models():
    base = _omni_base()
    try:
        r = requests.get(base + "/v1/models", timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
    except Exception as e:
        logger.warning(f"Modellar ro'yxati olinmadi: {e}")
        return {}
    cats = {}
    for entry in data:
        cat = categorize_entry(entry)
        if not cat:
            continue
        mid = entry.get("id")
        name = entry.get("name") or mid
        if not mid:
            continue
        cats.setdefault(cat, []).append((score_entry(entry), mid, name))
    for cat in cats:
        cats[cat].sort(key=lambda x: x[0], reverse=True)
    return cats

def get_categorized_models(force=False):
    now = time.time()
    if force or now - _MODEL_CACHE["ts"] > 600 or not _MODEL_CACHE["data"]:
        data = fetch_categorized_models()
        if data:
            _MODEL_CACHE["data"] = data
            _MODEL_CACHE["ts"] = now
    return _MODEL_CACHE["data"]

# ============================================================
# OmniRoute API — format aniqlash, keshlash, avtomatik qayta urinish
# ============================================================
def _omni_ollama(prompt, system, model):
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    payload = {"model": model, "prompt": full_prompt, "stream": False}
    headers = {"Content-Type": "application/json"}
    if OMNI_KEY and OMNI_KEY != "not-needed":
        headers["Authorization"] = f"Bearer {OMNI_KEY}"
    r = requests.post(_omni_base() + "/api/generate", json=payload, headers=headers, timeout=90)
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
    r = requests.post(_omni_base() + "/v1/chat/completions", json=payload, headers=headers, timeout=90)
    r.raise_for_status()
    data = r.json()
    if "choices" in data and len(data["choices"]) > 0:
        return data["choices"][0].get("message", {}).get("content", "")
    return ""

def omni_generate(prompt, system="", model=None):
    """Keshlangan formatdan boshlaydi, tarmoq xatosida avtomatik qayta urinadi."""
    model = model or CODE_MODEL
    order = ["ollama", "openai"]
    if _OMNI_FORMAT["mode"] == "openai":
        order = ["openai", "ollama"]

    max_retries = 2
    errors = []
    for fmt in order:
        for attempt in range(max_retries + 1):
            try:
                result = _omni_ollama(prompt, system, model) if fmt == "ollama" else _omni_openai(prompt, system, model)
                _OMNI_FORMAT["mode"] = fmt
                return result
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                errors.append(f"{fmt}: tarmoq xatosi ({e})")
                break
            except requests.exceptions.HTTPError as e:
                body = ""
                try:
                    body = e.response.text[:200]
                except Exception:
                    pass
                errors.append(f"{fmt} ({e.response.status_code}): {body}")
                break
            except Exception as e:
                errors.append(f"{fmt}: {e}")
                break

    raise Exception(
        "OmniRoute javob bermadi:\n" + "\n".join(f"• {x}" for x in errors) +
        f"\n\nModel: {model}\n"
        f"Tekshiring: curl -s {_omni_base()}/v1/models\n"
        f"Yoki /model buyrug'i bilan boshqa model tanlang."
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
# /code — asosiy AI kod yozish oqimi (cancel + qayta yozish bilan)
# ============================================================
async def run_code_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, uid: int):
    LAST_PROMPT[uid] = prompt
    await update.effective_chat.send_action(ChatAction.TYPING)
    status_msg = await update.effective_chat.send_message(
        f"⏰ Kod yozilmoqda... (model: {CODE_MODEL})\nBekor qilish: /cancel"
    )

    system = "You are an expert programmer. Write clean, well-commented code. Use markdown code blocks with language identifier."
    task = asyncio.create_task(asyncio.to_thread(omni_generate, f"Write code for: {prompt}", system, CODE_MODEL))
    ACTIVE_TASKS[uid] = task
    try:
        ans = await task
    except asyncio.CancelledError:
        try:
            await status_msg.edit_text("🛑 Bekor qilindi.")
        except Exception:
            pass
        return
    except Exception as e:
        try:
            await status_msg.delete()
        except Exception:
            pass
        await update.effective_chat.send_message(f"❌ Xatolik:\n<pre>{str(e)[:600]}</pre>", parse_mode="HTML")
        return
    finally:
        ACTIVE_TASKS.pop(uid, None)

    try:
        await status_msg.delete()
    except Exception:
        pass

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = detect_ext(ans)
    fn = f"code_{ts}.{ext}"
    fp = os.path.join(OUTPUT_DIR, fn)
    header = f"# Vazifa: {prompt}\n# Vaqt: {datetime.now().isoformat()}\n# User: {uid}\n\n"
    with open(fp, "w", encoding="utf-8") as f:
        f.write(header + ans)

    for i in range(0, len(ans), 3800):
        try:
            await update.effective_chat.send_message(ans[i:i + 3800], parse_mode="Markdown")
        except BadRequest:
            await update.effective_chat.send_message(ans[i:i + 3800])

    regen_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Qayta yoz", callback_data="regen")]])
    with open(fp, "rb") as f:
        await update.effective_chat.send_document(document=f, caption=f"📁 {fn}", reply_markup=regen_kb)

    await notify_admins(context, f"📝 <b>Kod</b>\nUser: <code>{uid}</code>\n{prompt[:100]}")

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
    if u.id in ACTIVE_TASKS and not ACTIVE_TASKS[u.id].done():
        await update.message.reply_text("⏳ Sizda allaqachon bajarilayotgan vazifa bor. Kuting yoki /cancel yuboring.")
        return
    prompt = " ".join(context.args)
    await run_code_generation(update, context, prompt, u.id)

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_authorized(u.id):
        return
    task = ACTIVE_TASKS.get(u.id)
    if task and not task.done():
        task.cancel()
        await update.message.reply_text("🛑 Bekor qilinmoqda...")
    else:
        await update.message.reply_text("Hozir faol vazifa yo'q.")

async def regen_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    if not is_authorized(uid):
        await q.answer()
        return
    prompt = LAST_PROMPT.get(uid)
    if not prompt:
        await q.answer("Eslab qolingan so'rov yo'q.", show_alert=True)
        return
    if uid in ACTIVE_TASKS and not ACTIVE_TASKS[uid].done():
        await q.answer("Sizda allaqachon bajarilayotgan vazifa bor.", show_alert=True)
        return
    await q.answer("🔁 Qayta yozilmoqda...")
    await run_code_generation(update, context, prompt, uid)

# ============================================================
# /model — kategoriya + ball asosida model tanlash
# ============================================================
async def show_category_menu(message_or_query, edit=False):
    cats = get_categorized_models()
    buttons = []
    for i, cname in enumerate(CATEGORY_ORDER):
        if cats.get(cname):
            buttons.append([InlineKeyboardButton(f"{cname} ({len(cats[cname])})", callback_data=f"cat:{i}")])
    buttons.append([InlineKeyboardButton("❌ Yopish", callback_data="cat:close")])
    text = f"🤖 Joriy kod modeli:\n<code>{CODE_MODEL}</code>\n\nKategoriya tanlang:"
    markup = InlineKeyboardMarkup(buttons)
    if edit:
        await message_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message_or_query.reply_text(text, parse_mode="HTML", reply_markup=markup)

async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await show_category_menu(update.message, edit=False)

async def model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_admin(q.from_user.id):
        await q.answer()
        return
    data = q.data
    cats = get_categorized_models()

    if data == "cat:close":
        await q.answer()
        await q.edit_message_text("Yopildi.")
        return

    if data == "cat:back":
        await q.answer()
        await show_category_menu(q, edit=True)
        return

    if data.startswith("cat:"):
        await q.answer()
        idx = int(data.split(":")[1])
        cname = CATEGORY_ORDER[idx]
        models = cats.get(cname, [])[:8]
        buttons = []
        for j, (score, mid, name) in enumerate(models):
            label = f"{name} · {score}"
            buttons.append([InlineKeyboardButton(label[:64], callback_data=f"mdl:{idx}:{j}")])
        buttons.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="cat:back")])
        await q.edit_message_text(
            f"{cname} — eng yuqori ballilar:\n<i>(ball = reasoning/thinking/tool_calling/vision + kontekst)</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data.startswith("mdl:"):
        global CODE_MODEL
        _, cidx, midx = data.split(":")
        cname = CATEGORY_ORDER[int(cidx)]
        models = cats.get(cname, [])
        try:
            score, mid, name = models[int(midx)]
        except IndexError:
            await q.answer("Model topilmadi, ro'yxat yangilangan bo'lishi mumkin.", show_alert=True)
            return
        CODE_MODEL = mid
        await q.answer("✅ Model o'zgartirildi")
        await q.edit_message_text(f"✅ Kod modeli o'zgartirildi:\n<b>{name}</b>\n<code>{mid}</code>", parse_mode="HTML")

# ============================================================
# /app — tezkor inline menyu
# ============================================================
async def app_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_authorized(u.id):
        return
    buttons = [[InlineKeyboardButton("🤖 Model tanlash", callback_data="cat:menu")]]
    if is_admin(u.id):
        buttons.insert(0, [InlineKeyboardButton("📊 Status", callback_data="app:status")])
    buttons.append([InlineKeyboardButton("💻 Kod yozish", callback_data="app:code")])
    buttons.append([InlineKeyboardButton("ℹ️ Yordam", callback_data="app:help")])
    await update.message.reply_text(
        "📱 <b>VPS Buddy — Menyu</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons)
    )

async def app_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    if not is_authorized(uid):
        await q.answer()
        return
    await q.answer()
    if q.data == "app:status":
        if not is_admin(uid):
            return
        text = build_status_text()
        await q.edit_message_text(text, parse_mode="HTML")
    elif q.data == "cat:menu":
        await show_category_menu(q, edit=True)
    elif q.data == "app:code":
        await q.edit_message_text(
            "💻 Kod yozish uchun:\n<code>/code vazifangiz</code>\n\nMisol: <code>/code flask rest api</code>",
            parse_mode="HTML"
        )
    elif q.data == "app:help":
        await q.edit_message_text(HELP_TEXT, parse_mode="HTML")

# ============================================================
# Callback marshrutizatori
# ============================================================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data or ""
    if data == "regen":
        await regen_callback(update, context)
    elif data.startswith("app:") or data == "cat:menu":
        await app_callback(update, context)
    elif data.startswith("cat:") or data.startswith("mdl:"):
        await model_callback(update, context)
    else:
        await update.callback_query.answer()

# ============================================================
# Buyruqlar
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_authorized(u.id):
        await update.message.reply_text(
            "🔒 <b>Bu bot yopiq.</b>\n\nKirish uchun kodni yuboring:\n<code>/auth kodingiz</code>",
            parse_mode="HTML"
        )
        await notify_admins(context, f"🔔 <b>Ruxsatsiz urinish</b>\nID: <code>{u.id}</code>\nIsm: {u.first_name}")
        return
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML")
    await update.message.reply_text(
        "📝 <b>Kod yozishni xohlaysizmi?</b>\nMisol: <code>/code python telegram bot</code>\n\n"
        "Yoki <code>/app</code> — tezkor menyu",
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
    cats = get_categorized_models(force=True)
    if not cats:
        await update.message.reply_text("❌ Model ro'yxati olinmadi.")
        return
    total = sum(len(v) for v in cats.values())
    t = f"🤖 <b>Modellar ({total} ta, {len(cats)} kategoriya):</b>\n\n"
    for cname in CATEGORY_ORDER:
        if cname in cats:
            top = cats[cname][:3]
            t += f"<b>{cname}</b> ({len(cats[cname])} ta)\n"
            for score, mid, name in top:
                t += f"  • {name} <code>{score}</code>\n"
            t += "\n"
    t += f"Joriy kod modeli: <code>{CODE_MODEL}</code>\nBatafsil tanlash uchun: /model"
    await update.message.reply_text(t, parse_mode="HTML")

def build_status_text():
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
    try:
        r = requests.get(base_url + "/v1/models", timeout=5)
        if r.status_code == 200:
            omni_status = "✅ OpenAI (/v1/models)"
    except Exception:
        pass
    health = _OMNI_HEALTH["up"]
    health_text = "✅ ishlayapti" if health else ("❌ javob bermayapti" if health is False else "⏳ hali tekshirilmadi")

    return (
        f"📊 <b>VPS Status</b>\n"
        f"⚡ Load: {ls}\n"
        f"💾 Disk: {ds}\n"
        f"📝 Xotira:\n<pre>{mem}</pre>\n\n"
        f"🔗 <b>OmniRoute:</b> {omni_status}\n"
        f"❤️ Health-check: {health_text}\n"
        f"💻 Kod modeli: <code>{CODE_MODEL}</code>\n"
        f"🔐 Format kesh: <code>{_OMNI_FORMAT['mode'] or 'aniqlanmagan'}</code>"
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(build_status_text(), parse_mode="HTML")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text("🛑 To'xtatildi.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML")

# ============================================================
# OmniRoute Health-check (fon vazifasi)
# ============================================================
async def health_check_job(context: ContextTypes.DEFAULT_TYPE):
    base = _omni_base()
    up = False
    try:
        r = requests.get(base + "/v1/models", timeout=8)
        up = (r.status_code == 200)
    except Exception:
        up = False
    prev = _OMNI_HEALTH["up"]
    if prev is not None and prev != up:
        if up:
            await notify_admins(context, "✅ <b>OmniRoute qayta ishga tushdi.</b>")
        else:
            await notify_admins(context, "🚨 <b>OmniRoute javob bermayapti!</b>")
    _OMNI_HEALTH["up"] = up

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

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("auth", auth_cmd))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("code", code_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("app", app_cmd))
    app.add_handler(CommandHandler("run", run_cmd))
    app.add_handler(CommandHandler("models", models_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_error_handler(error_handler)

    if app.job_queue is not None:
        app.job_queue.run_repeating(health_check_job, interval=300, first=30)
    else:
        logger.warning("JobQueue mavjud emas — health-check o'chirilgan. "
                        "O'rnatish: pip install \"python-telegram-bot[job-queue]\"")

    logger.info("Bot ishga tushdi... (PID: %s)", os.getpid())
    logger.info(f"CODE_MODEL={CODE_MODEL}")
    app.run_polling()

if __name__ == "__main__":
    main()
