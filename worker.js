/**
 * Agent-02 — Mustaqil Reviewer Worker  ·  v1.3
 * =====================================================================
 * Bu — Cloudflare Workers AI ustida ishlaydigan MUSTAQIL reviewer.
 * Diqqat: u Arena sessiyasidagi Agent-02 emas. Arena sessiyasiga ulanish
 * bu paketda YO'Q va da'vo qilinmaydi (README §0 ga qarang).
 *
 * v1.3 da tuzatilgan nuqsonlar:
 *   #1 PROJECT_STATE parsing — `[PROJECT_STATE] ...` (kolonsiz) shakl ham o'qiladi
 *   #2 ARTIFACT — inline kod/diff/log qabul qilinadi; URL o'qilmaydi (cheklov README'da)
 *   #3 Verdict — fail-closed: whitelist'dan tashqari/yо'q verdict => NEEDS_APPROVAL
 *   #4 ACK — Director javobining sxemasi tekshiriladi (HTTP 200 + {ok:false} = failure)
 *   #5 INBOUND_SECRET — MAJBURIY; bo'lmasa /task fail-closed (503)
 *   #6 Selftest — 27 ta lokal unit test (mock qilingani README'da aniq yozilgan)
 *   #7 Dedupe — bir xil TASK_ID uchun ikki qatlamli himoya (xotira + ixtiyoriy KV)
 *
 * Bindings / secrets (faqat NOMLAR, qiymatlar kodga yozilmaydi):
 *   AI              — Workers AI binding (majburiy)
 *   AGENT_ID        — var, "agent-02-reviewer"
 *   DIRECTOR_URL    — var, Director ACK endpoint
 *   INBOUND_SECRET  — secret (MAJBURIY): Director yuboradigan `X-Relay-Secret`
 *   AGENT_KEY       — secret (MAJBURIY): Director'ga ACK yuborishda `X-Agent-Key`
 *   TASK_DEDUPE     — (ixtiyoriy) KV namespace; bo'lmasa faqat xotiradagi dedupe ishlaydi
 */

const DEFAULT_DIRECTOR = "https://diyor-agency-24-7.pages.dev/api/sync";
const DEFAULT_AGENT_ID = "agent-02-reviewer";

const REVIEW_SYSTEM = `Sen mustaqil texnik reviewersan (Agent-02). Vazifang — boshqa tizimning ishini
tekshirib, xato, bug va buzilishlarni topish. Qoidalaring:
- Faqat dalilga tayan (log, status, message_id, test natijasi, berilgan kod/diff).
- Dalil bo'lmasa "dalil yo'q" deb yoz; ishlamagan narsani "ishlayapti" dema.
- Kodni o'zgartirmaysan; faqat tahlil va aniq taklif berasan.
- Javobni o'zbek tilida, oddiy va tushunarli tilda yoz.
- Yakunda ANIQ formatda tugat (boshqa qator qo'shma):
  XULOSA: <2-6 jumla>
  VERDICT: OK | BUG_FOUND | NEEDS_APPROVAL
  RUXSAT: <biror amal uchun ruxsat kerak bo'lsa savol; aks holda "kerak emas">`;

const MODELS = ["@cf/meta/llama-3.1-8b-instruct", "@cf/meta/llama-3.2-3b-instruct"];

const MAX_PAYLOAD_BYTES = 20000;
const MAX_ARTIFACT_CHARS = 8000;
const ALLOWED_VERDICTS = ["OK", "BUG_FOUND", "NEEDS_APPROVAL"];
const DEDUPE_TTL_MS = 10 * 60 * 1000;
const DEDUPE_MAX = 200;

/** Xotiradagi dedupe (isolate darajasida). Ishonchliligi cheklangan — README §7. */
const seenTasks = new Map();

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

/**
 * Nuqson #1: `[KEY: value]` VA `[KEY] value` shakllarini qo'llab-quvvatlaydi.
 * Nuqson #2: `[ARTIFACT_INLINE_BEGIN] ... [ARTIFACT_INLINE_END]` blokini ajratadi.
 */
function parsePacket(raw) {
  const out = {};
  const artifactLines = [];
  const rest = [];
  let inArtifact = false;
  let artifactTruncated = false;
  let artifactChars = 0;

  for (const line of String(raw || "").split(/\r?\n/)) {
    if (/^\[ARTIFACT_INLINE_BEGIN\]/i.test(line)) {
      inArtifact = true;
      continue;
    }
    if (/^\[ARTIFACT_INLINE_END\]/i.test(line)) {
      inArtifact = false;
      continue;
    }
    if (inArtifact) {
      const room = MAX_ARTIFACT_CHARS - artifactChars;
      if (line.length > room) {
        // Bitta uzun qator bo'lsa ham butunlay tashlab yubormaymiz — sig'gancha olamiz.
        if (room > 0) {
          artifactLines.push(line.slice(0, room));
          artifactChars += room;
        }
        artifactTruncated = true;
        continue;
      }
      artifactLines.push(line);
      artifactChars += line.length + 1;
      continue;
    }
    rest.push(line);
    const withColon = line.match(/^\[([A-Z_]+):\s*(.*)\]$/);
    const bare = line.match(/^\[([A-Z_]+)\]\s*(.*)$/);
    if (withColon) out[withColon[1]] = withColon[2].trim();
    else if (bare) out[bare[1]] = bare[2].trim();
  }

  const joined = rest.join("\n");
  const idx = joined.search(/\bVAZIFA:\s*/i);
  out.TASK_BODY = idx >= 0 ? joined.slice(idx).replace(/^\s*VAZIFA:\s*/i, "").trim() : "";
  out.ARTIFACT_INLINE = artifactLines.join("\n").trim();
  out.ARTIFACT_TRUNCATED = artifactTruncated;
  return out;
}

async function reviewTask(env, packet) {
  const task = packet.TASK_BODY || "";
  const criteria = packet.ACCEPTANCE_CRITERIA || "Mustaqil tekshiruv va dalilli xulosa.";
  const artifactRef = packet.ARTIFACT_REF || "not_provided";
  const projectState = packet.PROJECT_STATE || "";
  const inline = packet.ARTIFACT_INLINE || "";

  const artifactBlock = inline
    ? `ARTIFACT (inline, ${inline.length} belgi${packet.ARTIFACT_TRUNCATED ? ", QISQARTIRILGAN" : ""}):\n<<<\n${inline}\n>>>`
    : artifactRef !== "not_provided"
      ? `ARTIFACT_REF: ${artifactRef}\nDIQQAT: bu Worker tashqi URL/repo'ni O'QIMAYDI. Faqat havola berilgan — mazmun ko'rinmaydi, shuning uchun dalil sifatida faqat havolaning o'zini qayd et va "artifact mazmuni ko'rsatilmagan" deb yoz.`
      : `ARTIFACT_REF: not_provided\nDIQQAT: artifact berilmagan — taxmin qilma, "dalil yo'q" deb yoz.`;

  const prompt = [
    `TOPSHIRIQ: ${task}`,
    `QABUL MEZONLARI: ${criteria}`,
    projectState
      ? `PROJECT_STATE: ${projectState}`
      : `PROJECT_STATE: berilmagan (paketda yo'q — buni kamchilik sifatida qayd et)`,
    artifactBlock,
    "",
    "Eslatma: bu paket Director (Agent-01) tomonidan HTTPS orqali yuborilgan; sening tiziming uning KV'siga kira olmaydi.",
  ].join("\n");

  const errors = [];
  for (const model of MODELS) {
    try {
      const r = await env.AI.run(model, {
        messages: [
          { role: "system", content: REVIEW_SYSTEM },
          { role: "user", content: prompt },
        ],
        max_tokens: 700,
      });
      const text = String((r && (r.response || r.result || "")) || "").trim();
      if (text) return { text, model, errors, prompt };
      errors.push(`${model}: empty`);
    } catch (e) {
      errors.push(`${model}: ${String((e && e.message) || e).slice(0, 90)}`);
    }
  }
  return {
    text: "XULOSA: Tekshiruvni bajara olmadim — model javob bermadi.\nVERDICT: BUG_FOUND\nRUXSAT: kerak emas",
    model: null,
    errors,
    prompt,
  };
}

/**
 * Nuqson #3: FAIL-CLOSED.
 * - verdict yo'q / ruxsat etilmagan qiymat / bo'sh javob  => NEEDS_APPROVAL
 * - faqat whitelist: OK | BUG_FOUND | NEEDS_APPROVAL
 */
function splitVerdict(text) {
  const src = String(text || "").trim();
  const rawVerdict = (src.match(/VERDICT:\s*([A-Za-z_]+)/) || [])[1] || null;
  const verdict = rawVerdict ? rawVerdict.toUpperCase() : null;
  const approvalRaw = (src.match(/RUXSAT:\s*(.+)/i) || [])[1] || "";

  const reasons = [];
  if (!src) reasons.push("model javobi bo'sh");
  else if (!rawVerdict) reasons.push("VERDICT qatori yo'q");
  else if (!ALLOWED_VERDICTS.includes(verdict)) reasons.push(`ruxsat etilmagan VERDICT: ${rawVerdict}`);

  const failClosed = reasons.length > 0;
  const finalVerdict = failClosed ? "NEEDS_APPROVAL" : verdict;

  let summary = src.replace(/VERDICT:[\s\S]*$/i, "").replace(/^\s*XULOSA:\s*/i, "").trim();
  if (!summary) summary = "Model mazmunli xulosa bermadi.";
  if (failClosed) {
    summary = `Tekshirib bo'lmadi (${reasons.join("; ")}). ${summary}`.slice(0, 900);
  } else {
    summary = summary.slice(0, 900);
  }

  const approvalAsked = approvalRaw && !/kerak\s*emas/i.test(approvalRaw);
  const needsApproval = failClosed || finalVerdict === "NEEDS_APPROVAL" || !!approvalAsked;

  return {
    summary,
    verdict: finalVerdict,
    verdict_raw: rawVerdict,
    fail_closed: failClosed,
    fail_reasons: reasons,
    needs_approval: needsApproval,
    approval_question: needsApproval
      ? String(approvalAsked ? approvalRaw : failClosed
          ? "Model javobi formati noto'g'ri — tekshiruvni qo'lda tasdiqlash kerakmi?"
          : "Davom etishga ruxsat berasizmi?").slice(0, 300)
      : "",
  };
}

/**
 * Nuqson #4: ACK sxemasi tekshiriladi.
 * Muvaffaqiyat = HTTP 2xx + JSON obyekt + `ok === true` (+ task_id mos, agar berilgan bo'lsa).
 */
function validateAckResponse(httpStatus, bodyText, expectedTaskId) {
  if (!(httpStatus >= 200 && httpStatus < 300)) {
    return { ok: false, error: `director_http_${httpStatus}` };
  }
  let parsed;
  try {
    parsed = JSON.parse(bodyText);
  } catch (_) {
    return { ok: false, error: "director_invalid_json" };
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { ok: false, error: "director_invalid_schema" };
  }
  if (parsed.ok !== true) {
    return { ok: false, error: `director_rejected: ${String(parsed.error || "ok!=true").slice(0, 80)}` };
  }
  if (parsed.task_id && expectedTaskId && String(parsed.task_id) !== String(expectedTaskId)) {
    return { ok: false, error: "director_task_id_mismatch" };
  }
  return { ok: true, director_status: parsed.status || null };
}

async function sendAck(env, payload) {
  const url = env.DIRECTOR_URL || DEFAULT_DIRECTOR;
  const agentId = env.AGENT_ID || DEFAULT_AGENT_ID;
  if (!env.AGENT_KEY) return { ok: false, status: 0, error: "agent_key_missing" };

  let res;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Agent-Id": agentId,
        "X-Agent-Key": env.AGENT_KEY,
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(20000),
    });
  } catch (e) {
    return { ok: false, status: 0, error: `director_unreachable: ${String((e && e.message) || e).slice(0, 90)}` };
  }

  let bodyText = "";
  try {
    bodyText = await res.text();
  } catch (_) {}

  const verdict = validateAckResponse(res.status, bodyText, payload.task_id);
  return { status: res.status, body_text: bodyText.slice(0, 200), ...verdict };
}

/** Nuqson #7: dedupe — xotira + (ixtiyoriy) KV. */
async function dedupeCheck(env, taskId) {
  const now = Date.now();
  for (const [k, ts] of seenTasks) {
    if (now - ts > DEDUPE_TTL_MS) seenTasks.delete(k);
  }
  if (seenTasks.has(taskId)) return { duplicate: true, layer: "memory" };

  if (env.TASK_DEDUPE && typeof env.TASK_DEDUPE.get === "function") {
    try {
      if (await env.TASK_DEDUPE.get(`task:${taskId}`)) return { duplicate: true, layer: "kv" };
    } catch (_) {}
  }
  return { duplicate: false };
}

async function dedupeMark(env, taskId) {
  seenTasks.set(taskId, Date.now());
  while (seenTasks.size > DEDUPE_MAX) {
    const oldest = seenTasks.keys().next().value;
    seenTasks.delete(oldest);
  }
  if (env.TASK_DEDUPE && typeof env.TASK_DEDUPE.put === "function") {
    try {
      await env.TASK_DEDUPE.put(`task:${taskId}`, "1", { expirationTtl: Math.ceil(DEDUPE_TTL_MS / 1000) });
    } catch (_) {}
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const hasInbound = !!env.INBOUND_SECRET;

    if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/health")) {
      return json({
        ok: true,
        agent: env.AGENT_ID || DEFAULT_AGENT_ID,
        role: "reviewer",
        version: "1.3",
        runtime: "cloudflare_workers_ai",
        models: MODELS,
        ready: hasInbound && !!env.AGENT_KEY,
        inbound_auth: hasInbound ? "shared_secret" : "MISSING",
        ack_configured: !!env.AGENT_KEY,
        dedupe: env.TASK_DEDUPE ? "kv+memory" : "memory_only",
        verdict_policy: "fail_closed",
        endpoints: ["GET /health", "POST /task"],
        warnings: !hasInbound ? ["INBOUND_SECRET yo'q — /task fail-closed (503)"] : [],
      });
    }

    if (request.method === "POST" && (url.pathname === "/task" || url.pathname === "/")) {
      // Nuqson #5: kirish himoyasi MAJBURIY (fail-closed)
      if (!hasInbound) {
        return json({ ok: false, error: "inbound_secret_missing", hint: "wrangler secret put INBOUND_SECRET" }, 503);
      }
      const got = request.headers.get("X-Relay-Secret") || "";
      if (!got || got !== env.INBOUND_SECRET) {
        return json({ ok: false, error: "unauthorized" }, 401);
      }

      let raw = "";
      try {
        const ct = request.headers.get("Content-Type") || "";
        if (ct.includes("application/json")) {
          const b = await request.json();
          raw = b.wire || b.task || JSON.stringify(b);
        } else {
          raw = await request.text();
        }
      } catch (_) {
        return json({ ok: false, error: "bad_payload" }, 400);
      }
      if (raw.length > MAX_PAYLOAD_BYTES) return json({ ok: false, error: "payload_too_large", limit: MAX_PAYLOAD_BYTES }, 413);

      const packet = parsePacket(raw);
      if (!packet.TASK_ID) return json({ ok: false, error: "TASK_ID yo'q" }, 400);
      const myId = env.AGENT_ID || DEFAULT_AGENT_ID;
      if (packet.TO && String(packet.TO).toLowerCase() !== myId) {
        return json({ ok: false, error: `Bu vazifa boshqa agentga: ${packet.TO}` }, 400);
      }

      // Nuqson #7
      const dup = await dedupeCheck(env, packet.TASK_ID);
      if (dup.duplicate) {
        return json({
          ok: true, task_id: packet.TASK_ID, dedupe: `hit:${dup.layer}`,
          verdict: "NEEDS_APPROVAL", needs_approval: false,
          delivered_to_director: false,
          note: "Bu TASK_ID ya ishlangan — model qayta chaqirilmadi.",
        }, 200);
      }

      const review = await reviewTask(env, packet);
      const v = splitVerdict(review.text);

      const ack = await sendAck(env, {
        op: "jamoa_ack",
        task_id: packet.TASK_ID,
        project_id: packet.PROJECT_ID || "AGENT-SYSTEM",
        from: myId,
        status: "ACK",
        summary: v.summary,
        verdict: v.verdict,
        verdict_raw: v.verdict_raw,
        fail_closed: v.fail_closed,
        needs_approval: v.needs_approval,
        approval_question: v.approval_question,
      });

      // Muvaffaqiyatli ishlov berilgandagina dedupe'ga yozamiz (retry yo'lini yopmaymiz).
      if (ack.ok) await dedupeMark(env, packet.TASK_ID);

      return json({
        ok: !!ack.ok,
        task_id: packet.TASK_ID,
        dedupe: "miss",
        model_used: review.model,
        model_errors: review.errors,
        verdict: v.verdict,
        verdict_raw: v.verdict_raw,
        fail_closed: v.fail_closed,
        needs_approval: v.needs_approval,
        delivered_to_director: !!ack.ok,
        director_status: ack.status || null,
        director_error: ack.error || null,
      }, ack.ok ? 200 : 502);
    }

    return json({ ok: false, error: "not_found", endpoints: ["GET /health", "POST /task"] }, 404);
  },
};

// Lokal selftest uchun ichki funksiyalar (production'da ishlatilmaydi).
export const __test = { parsePacket, splitVerdict, validateAckResponse };
