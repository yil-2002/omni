# Agent-02 — Mustaqil Reviewer Worker · **v1.3**

> **Bu paketda hech qanday secret yo'q.** Login, deploy va secret kiritishni **loyiha egasi** bajaradi.

## 0. ⚠️ Arxitektura chegarasi (ochiq qayd etiladi)

Bu Worker — **Cloudflare Workers AI** ustida ishlaydigan **mustaqil reviewer** (`env.AI.run`).
U **Arena sessiyasidagi Agent-02 bilan bir xil tizim EMAS**. Arena sessiyasiga ulanish bu paketda
**yo'q** va **hech qayerda da'vo qilinmaydi**. Agar talab aynan Arena Agent-02 sessiyasiga ulanish
bo'lsa — bu **arxitektura nomutanosibligi**: bunday integratsiya soxta qo'shilmaydi, u alohida
ish sifatida hal qilinishi kerak.

| Savol | Javob |
|---|---|
| `/task` haqiqiy modelni chaqiradimi? | **Ha** — Workers AI: `@cf/meta/llama-3.1-8b-instruct`, fallback `@cf/meta/llama-3.2-3b-instruct` |
| Arena Agent-02 ga ulanganmi? | **Yo'q** |
| Director'ning KV'siga kira oladimi? | **Yo'q** — alohida Cloudflare akkaunt |

## 1. Fayllar

| Fayl | Vazifasi |
|---|---|
| `worker.js` | Kirish nuqtasi: `GET /health`, `POST /task` (v1.3) |
| `wrangler.toml` | Worker nomi, `[ai] AI` binding, `AGENT_ID`, `DIRECTOR_URL` — **secretsiz** |
| `package.json` | `wrangler` devDep, `npm run selftest` |
| `selftest.mjs` | **49 ta lokal unit test** (mock'li, deploy talab qilmaydi) |
| `README.md` | Shu qo'llanma |
| `.gitignore` | `.env*`, `.dev.vars`, `node_modules/`, `*.zip` |

## 2. Binding va secret — faqat NOMLAR

| Nomi | Turi | Majburiy | Nima uchun |
|---|---|---|---|
| `AI` | Workers AI binding | ✅ | `/task` modeli |
| `AGENT_ID` | var | ✅ | `agent-02-reviewer` |
| `DIRECTOR_URL` | var | ✅ | `https://diyor-agency-24-7.pages.dev/api/sync` |
| `INBOUND_SECRET` | **secret** | ✅ **MAJBURIY** | Director → Agent-02 kirishini yopadi. **Yo'q bo'lsa `/task` = `503` (fail-closed)** |
| `AGENT_KEY` | **secret** | ✅ | Agent → Director ACK imzosi (`X-Agent-Key`) |
| `TASK_DEDUPE` | KV namespace | ⬜ ixtiyoriy | Takroriy `TASK_ID` himoyasini doimiy qiladi (yo'q bo'lsa faqat xotirada) |

### `INBOUND_SECRET` bo'yicha Director tomoni (majburiy tartib)

1. **Agent-02 akkauntida:** `npx wrangler secret put INBOUND_SECRET`
2. **Director akkauntida:** xuddi shu **qiymat** bilan alohida secret yaratiladi (nomi, masalan `TOKEN_AGENT02`).
3. Director allowlist'idagi route'ga `secret_binding` shu nom bilan yoziladi:
   `{"kind":"http","url":"…/task","secret_binding":"TOKEN_AGENT02"}`

Sabab: `sendAgentTask()` Director→Agent so'roviga `X-Relay-Secret` sarlavhasini **faqat**
`route.secret_binding` ko'rsatilganda qo'shadi. Bu qadam bajarilmasa Director'ning TASK'lari `401` oladi.
**Qiymatlar hech qayerda (kod, README, ZIP, log) yozilmaydi.**

## 3. API

**`GET /health`** → `200`
```json
{ "ok": true, "agent": "agent-02-reviewer", "version": "1.3",
  "runtime": "cloudflare_workers_ai", "models": ["@cf/meta/llama-3.1-8b-instruct", "…"],
  "ready": true, "inbound_auth": "shared_secret", "ack_configured": true,
  "dedupe": "memory_only", "verdict_policy": "fail_closed", "warnings": [] }
```

**`POST /task`** — sarlavha `X-Relay-Secret: <INBOUND_SECRET>` **majburiy**.

| Holat | HTTP |
|---|---|
| `INBOUND_SECRET` o'rnatilmagan | **503** `inbound_secret_missing` (fail-closed) |
| sarlavha yo'q / noto'g'ri | **401** `unauthorized` |
| `TASK_ID` yo'q | **400** |
| `TO:` boshqa agent | **400** |
| payload > 20 000 belgi | **413** |
| model + ACK muvaffaqiyatli | **200**, `delivered_to_director: true` |
| Director ACK rad etdi / JSON buzuq / `ok:false` | **502**, `delivered_to_director: false` + `director_error` |
| takroriy `TASK_ID` | **200**, `dedupe: "hit:memory"` (model **qayta chaqirilmaydi**) |

Kirish paketi (Director yuboradi):
```
[TYPE: TASK]
[PROJECT_ID: AGENT-SYSTEM]
[TASK_ID: T-20261104-XXXX]
[FROM: director]
[TO: agent-02-reviewer]
[ROLE: reviewer]
[ACCEPTANCE_CRITERIA: ...]
[ARTIFACT_REF: not_provided]
[STATUS: ASSIGNED]
[PROJECT_STATE] AGENT-SYSTEM | faza: ... | versiya: vN | ochiq ruxsat: N | oxirgi qaror: ...
[ARTIFACT_INLINE_BEGIN]
<kod / diff / log>
[ARTIFACT_INLINE_END]

VAZIFA:
...
```

Parser ikkala shaklni ham o'qiydi: `[KEY: value]` **va** `[KEY] value` (v1.3 tuzatishi).

## 4. Cheklovlar (yashirmasdan)

| Cheklov | Tafsilot |
|---|---|
| **Artefakt mazmuni** | Worker tashqi URL/repo/faylni **o'qimaydi** (GitHub token, keng fetch yo'q). Kod/diff/log bo'lsa `[ARTIFACT_INLINE_BEGIN]…[ARTIFACT_INLINE_END]` ichida yuboring (8000 belgigacha, ortig'i qisqartiriladi). Faqat URL berilsa model mazmunni ko'rmaydi — prompt ham buni modelga aytadi |
| **Verdict siyosati** | `VERDICT` yo'q, ruxsat etilmagan qiymat yoki bo'sh javob → **`NEEDS_APPROVAL`** (fail-closed). Faqat `OK`, `BUG_FOUND`, `NEEDS_APPROVAL` qabul qilinadi |
| **Dedupe** | `TASK_DEDUPE` KV bog'lanmasa — faqat **xotirada** (isolate darajasida, TTL 10 daqiqa, 200 yozuv). Ko'p instansiyada **kafolat emas** → productionda KV ulash tavsiya etiladi |
| **Header himoyasi** | `X-Relay-Secret` — oddiy shared secret. `INBOUND_SECRET` uzun va tasodifiy bo'lishi shart |
| **Selftest** | **Lokal unit test**, integratsion emas: `env.AI.run` va global `fetch` **mock** qilinadi |
| **Arena** | Arena Agent-02 sessiyasiga ulanish yo'q (§0) |

## 5. Selftest — 49 ta test

```bash
cd agent02_edge && node selftest.mjs
```
**Kutiladi:** `HAMMASI O'TDI (49/49)`.

Qamrov: health (2 holat) · `INBOUND_SECRET` yo'q/noto'g'ri/to'g'ri · `[PROJECT_STATE]` ikki shakl + yo'qligi ·
inline artifact + qisqartirish + URL-only cheklovi · verdict fail-closed (yo'q/noma'lum/buzilgan/bo'sh/`OK`/`BUG_FOUND`) ·
ACK sxemasi (6 holat) + E2E `{ok:false}`/JSON buzuq/`ok:true` · dedupe (xotira + KV) · chegara holatlari ·
ACK sarlavhalari.

**Mock:** `env.AI.run` (model javobi), global `fetch` (Director API), ixtiyoriy KV (Map).
**Haqiqiy tekshirilmaydi:** Workers AI, Director API, KV, deploy, autentifikatsiya.

## 6. Deploy qadamlari (har biri + kutilayotgan natija)

| # | Amal | Kutiladi |
|---|---|---|
| 0 | `node selftest.mjs` | `HAMMASI O'TDI (49/49)` |
| 1 | Yangi Cloudflare akkaunt (boshqa email) | Limitlar ajralgan |
| 2 | `npx wrangler login` | `whoami` — **yangi** email |
| 3 | `npx wrangler deploy` | `https://agent-02-reviewer.<SUB>.workers.dev` |
| 4 | `npx wrangler secret put INBOUND_SECRET` | `health` → `inbound_auth: "shared_secret"` |
| 5 | `jamoa_agent_link.py handshake --id agent-02-reviewer` | Kod → Telegram **shaxsiy chat** (kanalga emas) |
| 6 | `jamoa_agent_link.py hello --nonce … --endpoint …` | `agent_key` **bir marta** + `✅ Agent-02 ulandi` |
| 7 | `npx wrangler secret put AGENT_KEY` | `health` → `ready: true` |
| 8 | Director tomonida `secret_binding` sozlash (§2) | TASK → ACK ishlaydi; kanalda faqat natija |
| 9 | `curl /health` | `ready: true`, `verdict_policy: fail_closed` |

## 7. Xavfsizlik

- `AGENT_KEY` faqat Worker secret'ida; Director'da faqat **SHA-256 hash**.
- Agent kaliti bilan Director API'sida faqat `jamoa_hello` va `jamoa_ack` ishlaydi — boshqasi `403`.
- Paketda token/kalit/nonce yo'q; `.env`/`.dev.vars` `.gitignore` bilan bloklangan.
- Default rejim — **review-only**; kod o'zgartiradi faqat egasining aniq ruxsati bilan.
