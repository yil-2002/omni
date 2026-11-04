/**
 * LOKAL UNIT TEST — deploy talab qilmaydi, tarmoqqa chiqmaydi.
 *
 * ⚠️ Bu INTEGRATSION TEST EMAS. Mock qilinadi:
 *   - `env.AI.run`  (haqiqiy Workers AI chaqirilmaydi)
 *   - global `fetch` (haqiqiy Director API chaqirilmaydi)
 * Haqiqiy Workers AI, haqiqiy Director API, KV va deploy — tekshirilMAYDI.
 *
 * Ishga tushirish:  node selftest.mjs
 */
import worker, { __test } from "./worker.js";

// Ataylab SOXTA qiymatlar — hech qanday haqiqiy kalit emas.
const DUMMY_INBOUND = ["dummy", "inbound", String(4242)].join("-");
const DUMMY_AGENT_KEY = ["dummy", "agent", String(9191)].join("-");

let results = [];
const check = (name, cond, extra = "") => {
  results.push({ name, ok: !!cond, extra });
  console.log(`${cond ? "✅" : "❌"} ${name}${extra ? " — " + extra : ""}`);
};

// ─────────────────── mock qatlami ───────────────────
let lastPrompt = null;
let lastModelArgs = null;
let ackRequests = [];
let aiCalls = 0;

function makeEnv(overrides = {}) {
  return {
    AGENT_ID: "agent-02-reviewer",
    INBOUND_SECRET: DUMMY_INBOUND,
    AGENT_KEY: DUMMY_AGENT_KEY,
    AI: {
      run: async (model, args) => {
        aiCalls++;
        lastModelArgs = args;
        lastPrompt = args.messages.find((m) => m.role === "user").content;
        return {
          response:
            "XULOSA: Tekshiruv bajarildi, dalil sifatida PROJECT_STATE va artifact ko'rildi.\n" +
            "VERDICT: OK\nRUXSAT: kerak emas",
        };
      },
    },
    ...overrides,
  };
}

// body === null  =>  "muvaffaqiyatli" javob, task_id so'rovdan aks ettiriladi (echo)
let fetchReply = { status: 200, body: null, dynamic: null };
globalThis.fetch = async (url, opts) => {
  const sent = JSON.parse(opts.body);
  ackRequests.push({ url: String(url), headers: opts.headers, body: sent });
  if (fetchReply.dynamic) return fetchReply.dynamic(url, sent);
  const text = fetchReply.body === null
    ? JSON.stringify({ ok: true, task_id: sent.task_id, status: "ACK" })
    : fetchReply.body;
  return new Response(text, { status: fetchReply.status, headers: { "Content-Type": "application/json" } });
};

// ─────────────────── yordamchilar ───────────────────
const AUTH = { "X-Relay-Secret": DUMMY_INBOUND };

function wire({ taskId = "T-ONE", state = "[PROJECT_STATE] AGENT-SYSTEM | faza: hybrid_policy_active | versiya: v1", artifactBlock = "" } = {}) {
  return [
    "[TYPE: TASK]",
    "[PROJECT_ID: AGENT-SYSTEM]",
    `[TASK_ID: ${taskId}]`,
    "[FROM: director]",
    "[TO: agent-02-reviewer]",
    "[ROLE: reviewer]",
    "[ACCEPTANCE_CRITERIA: mustaqil tekshiruv, dalilli xulosa]",
    "[ARTIFACT_REF: not_provided]",
    "[STATUS: ASSIGNED]",
    state,
    ...(artifactBlock ? [artifactBlock] : []),
    "",
    "VAZIFA: webhook xatolarini tekshir",
  ].join("\n");
}

const postTask = (body, headers = AUTH, env = makeEnv()) =>
  worker.fetch(
    new Request("https://agent02.local/task", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: typeof body === "string" ? body : JSON.stringify(body),
    }),
    env,
  );

const uniqueId = (p) => `${p}-${Math.random().toString(36).slice(2, 7).toUpperCase()}`;

// ═══════════════════ 1. HEALTH ═══════════════════
{
  const r = await worker.fetch(new Request("https://agent02.local/health"), makeEnv());
  const j = await r.json();
  check("health: 200 + ready (secret bor)", r.status === 200 && j.ok && j.ready === true, `inbound_auth=${j.inbound_auth}`);
  check("health: runtime = cloudflare_workers_ai", j.runtime === "cloudflare_workers_ai");
  check("health: verdict_policy = fail_closed", j.verdict_policy === "fail_closed");
  check("health: dedupe rejimi ko'rsatilgan", j.dedupe === "memory_only", j.dedupe);
  check("health: secret yo'q -> ready=false", (await (async () => {
    const r2 = await worker.fetch(new Request("https://agent02.local/health"), makeEnv({ INBOUND_SECRET: undefined }));
    const j2 = await r2.json();
    return j2.ready === false && j2.inbound_auth === "MISSING" && j2.warnings.length === 1;
  })()));
}

// ═══════════════════ 2. NUQSON #5 — kirish himoyasi MAJBURIY ═══════════════════
{
  const r1 = await postTask({ wire: wire() }, AUTH, makeEnv({ INBOUND_SECRET: undefined }));
  const j1 = await r1.json();
  check("#5 INBOUND_SECRET yo'q -> 503 fail-closed", r1.status === 503 && j1.error === "inbound_secret_missing", j1.error);

  const r2 = await postTask({ wire: wire() }, {});
  check("#5 sarlavhasiz -> 401", r2.status === 401 && (await r2.json()).error === "unauthorized");

  const r3 = await postTask({ wire: wire() }, { "X-Relay-Secret": "wrong-value" });
  check("#5 noto'g'ri sarlavha -> 401", r3.status === 401);

  const r4 = await postTask({ wire: wire({ taskId: uniqueId("T-AUTH") }) });
  check("#5 to'g'ri sarlavha -> 200", r4.status === 200, `status=${r4.status}`);
}

// ═══════════════════ 3. NUQSON #1 — PROJECT_STATE parsing ═══════════════════
{
  const stateText = "AGENT-SYSTEM | faza: hybrid_policy_active | versiya: v7 | ochiq ruxsat: 2";
  const r = await postTask({ wire: wire({ taskId: uniqueId("T-STATE"), state: `[PROJECT_STATE] ${stateText}` }) });
  await r.json();
  check("#1 `[PROJECT_STATE] matn` shakli promptga tushdi", !!lastPrompt && lastPrompt.includes(stateText),
    lastPrompt ? (lastPrompt.includes(stateText) ? "topildi" : "TOPILMADI") : "prompt yo'q");
  check("#1 promptda 'berilmagan' yo'q", !!lastPrompt && !lastPrompt.includes("PROJECT_STATE: berilmagan"));

  const stateText2 = "AGENT-SYSTEM | versiya: v9 | kolon shakli";
  const r2 = await postTask({ wire: wire({ taskId: uniqueId("T-STATE2"), state: `[PROJECT_STATE: ${stateText2}]` }) });
  await r2.json();
  check("#1 `[PROJECT_STATE: matn]` kolon shakli ham ishlaydi", !!lastPrompt && lastPrompt.includes(stateText2));

  const r3 = await postTask({ wire: wire({ taskId: uniqueId("T-NOSTATE"), state: "" }) });
  await r3.json();
  check("#1 state yo'q bo'lsa 'berilmagan' + kamchilik qayd etiladi",
    !!lastPrompt && lastPrompt.includes("berilmagan") && lastPrompt.includes("kamchilik"));
}

// ═══════════════════ 4. NUQSON #2 — ARTIFACT ═══════════════════
{
  const code = "function add(a,b){ return a-b }  // BUG: ayirish";
  const block = `[ARTIFACT_INLINE_BEGIN]\n${code}\n[ARTIFACT_INLINE_END]`;
  const r = await postTask({ wire: wire({ taskId: uniqueId("T-ART"), artifactBlock: block }) });
  await r.json();
  check("#2 inline artifact promptga tushdi", !!lastPrompt && lastPrompt.includes("a-b"));

  const longCode = "x".repeat(12000);
  const r2 = await postTask({ wire: wire({ taskId: uniqueId("T-ART2"), artifactBlock: `[ARTIFACT_INLINE_BEGIN]\n${longCode}\n[ARTIFACT_INLINE_END]` }) });
  await r2.json();
  check("#2 katta artifact 8000 belgiga qisqartiriladi", !!lastPrompt && lastPrompt.includes("QISQARTIRILGAN"));

  const r3 = await postTask({
    wire: wire({ taskId: uniqueId("T-ART3") }).replace("[ARTIFACT_REF: not_provided]", "[ARTIFACT_REF: https://github.com/x/y/blob/main/z.js]"),
  });
  await r3.json();
  check("#2 URL-only: 'tashqi URL O'QIMAYDI' cheklovi promptda", !!lastPrompt && lastPrompt.includes("O'QIMAYDI"));
}

// ═══════════════════ 5. NUQSON #3 — verdict fail-closed ═══════════════════
{
  const { splitVerdict } = __test;

  const okV = splitVerdict("XULOSA: Hammasi joyida.\nVERDICT: OK\nRUXSAT: kerak emas");
  check("#3 VERDICT: OK qabul qilinadi", okV.verdict === "OK" && okV.fail_closed === false && okV.needs_approval === false);

  const bugV = splitVerdict("XULOSA: Xato topildi.\nVERDICT: BUG_FOUND\nRUXSAT: kerak emas");
  check("#3 VERDICT: BUG_FOUND qabul qilinadi", bugV.verdict === "BUG_FOUND" && bugV.fail_closed === false);

  const missing = splitVerdict("XULOSA: Hammasi yaxshi ko'rinadi.");
  check("#3 verdict YO'Q -> NEEDS_APPROVAL (fail-closed)",
    missing.verdict === "NEEDS_APPROVAL" && missing.fail_closed === true && missing.needs_approval === true,
    missing.fail_reasons.join("; "));
  check("#3 summary 'tekshirib bo'lmadi' bilan boshlanadi", missing.summary.startsWith("Tekshirib bo'lmadi"));

  const unknown = splitVerdict("XULOSA: Zo'r.\nVERDICT: LOOKS_FINE\nRUXSAT: kerak emas");
  check("#3 noma'lum VERDICT -> NEEDS_APPROVAL", unknown.verdict === "NEEDS_APPROVAL" && unknown.verdict_raw === "LOOKS_FINE");

  const broken = splitVerdict("VERDICT OK deb o'ylayman");
  check("#3 buzilgan javob -> NEEDS_APPROVAL", broken.verdict === "NEEDS_APPROVAL" && broken.fail_closed === true);

  const empty = splitVerdict("   ");
  check("#3 bo'sh javob -> NEEDS_APPROVAL", empty.verdict === "NEEDS_APPROVAL" && empty.summary.includes("bo'sh"));

  const wantsApproval = splitVerdict("XULOSA: Tuzatish kerak.\nVERDICT: NEEDS_APPROVAL\nRUXSAT: 2 faylni o'zgartirishga ruxsat berasizmi?");
  check("#3 NEEDS_APPROVAL + savol saqlanadi", wantsApproval.needs_approval === true && wantsApproval.approval_question.includes("ruxsat berasizmi"));
}

// ═══════════════════ 6. NUQSON #4 — Director ACK sxemasi ═══════════════════
{
  const { validateAckResponse } = __test;

  const okAck = validateAckResponse(200, JSON.stringify({ ok: true, task_id: "T-ONE", status: "ACK" }), "T-ONE");
  check("#4 ok:true + task_id mos -> success", okAck.ok === true, okAck.error || "");

  const falseAck = validateAckResponse(200, JSON.stringify({ ok: false, error: "UNKNOWN_TASK_ID" }), "T-ONE");
  check("#4 HTTP 200 + {ok:false} -> failure", falseAck.ok === false && falseAck.error.startsWith("director_rejected"), falseAck.error);

  const badJson = validateAckResponse(200, "Forbidden", "T-ONE");
  check("#4 200 + JSON emas -> failure", badJson.ok === false && badJson.error === "director_invalid_json");

  const emptyJson = validateAckResponse(200, "", "T-ONE");
  check("#4 200 + bo'sh javob -> failure", emptyJson.ok === false && emptyJson.error === "director_invalid_json");

  const arrayJson = validateAckResponse(200, "[]", "T-ONE");
  check("#4 200 + array -> failure", arrayJson.ok === false && arrayJson.error === "director_invalid_schema");

  const mismatch = validateAckResponse(200, JSON.stringify({ ok: true, task_id: "T-OTHER" }), "T-ONE");
  check("#4 task_id mos kelmasa -> failure", mismatch.ok === false && mismatch.error === "director_task_id_mismatch");

  const http500 = validateAckResponse(500, JSON.stringify({ ok: true }), "T-ONE");
  check("#4 HTTP 500 -> failure", http500.ok === false && http500.error === "director_http_500");

  // End-to-end: Director {ok:false} qaytarsa Worker buni delivered deb hisoblamaydi
  fetchReply = { status: 200, body: JSON.stringify({ ok: false, error: "UNKNOWN_TASK_ID" }) };
  const r = await postTask({ wire: wire({ taskId: uniqueId("T-ACKF") }) });
  const j = await r.json();
  check("#4 E2E: {ok:false} -> delivered_to_director:false + 502",
    r.status === 502 && j.delivered_to_director === false && String(j.director_error).includes("director_rejected"),
    `${r.status} / ${j.director_error}`);

  fetchReply = { status: 200, body: "<html>gateway</html>" };
  const r2 = await postTask({ wire: wire({ taskId: uniqueId("T-ACKJ") }) });
  const j2 = await r2.json();
  check("#4 E2E: JSON bo'lmagan javob -> failure", r2.status === 502 && j2.director_error === "director_invalid_json");

  fetchReply = { status: 200, body: null };
  const r3 = await postTask({ wire: wire({ taskId: uniqueId("T-ACKOK") }) });
  const j3 = await r3.json();
  check("#4 E2E: ok:true -> delivered_to_director:true + 200", r3.status === 200 && j3.delivered_to_director === true);
}

// ═══════════════════ 7. NUQSON #7 — dedupe ═══════════════════
{
  const tid = uniqueId("T-DUP");
  aiCalls = 0;
  fetchReply = { status: 200, body: null };
  const r1 = await postTask({ wire: wire({ taskId: tid }) });
  const j1 = await r1.json();
  const firstCalls = aiCalls;
  const r2 = await postTask({ wire: wire({ taskId: tid }) });
  const j2 = await r2.json();

  check("#7 birinchi TASK modelni chaqiradi", firstCalls === 1 && j1.dedupe === "miss");
  check("#7 takroriy TASK_ID modelni QAYTA chaqirmaydi", aiCalls === 1, `aiCalls=${aiCalls}`);
  check("#7 takroriy javobda dedupe hit qayd etiladi", j2.dedupe === "hit:memory", j2.dedupe);

  // KV qatlami bo'lsa ham ishlashi (dummy KV, real binding emas)
  const kvStore = new Map();
  const envKv = makeEnv({
    TASK_DEDUPE: {
      get: async (k) => kvStore.get(k) || null,
      put: async (k, v) => void kvStore.set(k, v),
    },
  });
  const tid2 = uniqueId("T-DUPKV");
  aiCalls = 0;
  fetchReply = { status: 200, body: null };
  await postTask({ wire: wire({ taskId: tid2 }) }, AUTH, envKv);
  await postTask({ wire: wire({ taskId: tid2 }) }, AUTH, envKv);
  check("#7 KV qatlami ham dedupe qiladi", aiCalls === 1 && kvStore.has(`task:${tid2}`), `aiCalls=${aiCalls}`);
}

// ═══════════════════ 8. boshqa himoya va chegaralar ═══════════════════
{
  const r1 = await postTask({ wire: wire({ taskId: "T-X" }).replace("[TO: agent-02-reviewer]", "[TO: agent-99]") });
  check("boshqa agentga TASK -> 400", r1.status === 400);

  const r2 = await postTask({ wire: "salom, TASK_ID yo'q" });
  check("TASK_ID yo'q -> 400", r2.status === 400);

  const r3 = await postTask({ wire: wire({ taskId: uniqueId("T-BIG") }) + "x".repeat(20000) });
  check("20 KB dan katta -> 413", r3.status === 413);

  const envDown = makeEnv({
    AI: { run: async () => { throw new Error("model down"); } },
  });
  const r4 = await postTask({ wire: wire({ taskId: uniqueId("T-DOWN") }) }, AUTH, envDown);
  const j4 = await r4.json();
  check("model ishlamasa -> BUG_FOUND + ACK yuboriladi", r4.status === 200 && j4.verdict === "BUG_FOUND");

  const envNoKey = makeEnv({ AGENT_KEY: undefined });
  const r5 = await postTask({ wire: wire({ taskId: uniqueId("T-NOKEY") }) }, AUTH, envNoKey);
  const j5 = await r5.json();
  check("AGENT_KEY yo'q -> ACK failure (502)", r5.status === 502 && j5.director_error === "agent_key_missing");

  const r6 = await worker.fetch(new Request("https://agent02.local/nope"), makeEnv());
  check("noma'lum yo'l -> 404", r6.status === 404);
}

// ═══════════════════ 9. ACK sarlavhalari ═══════════════════
{
  ackRequests = [];
  fetchReply = { status: 200, body: null };
  await postTask({ wire: wire({ taskId: "T-HDR" }) });
  const last = ackRequests[ackRequests.length - 1];
  check("ACK: X-Agent-Key yuboriladi", last && last.headers["X-Agent-Key"] === DUMMY_AGENT_KEY);
  check("ACK: X-Agent-Id yuboriladi", last && last.headers["X-Agent-Id"] === "agent-02-reviewer");
  check("ACK: to'g'ri endpoint", last && last.url === "https://diyor-agency-24-7.pages.dev/api/sync");
  check("ACK: op = jamoa_ack", last && last.body.op === "jamoa_ack");
  check("ACK: verdict maydonlari uzatiladi", last && "verdict" in last.body && "fail_closed" in last.body);
}

// ═══════════════════ yakun ═══════════════════
const failed = results.filter((r) => !r.ok);
console.log("\n─────────────────────────────────────────────");
console.log(`MOCK QILINGAN: env.AI.run (${aiCalls} chaqiruv) va global fetch (Director API).`);
console.log("HAQIQIY TEKSHIRILMAGAN: Workers AI, Director API, KV, deploy, autentifikatsiya.");
console.log(`${failed.length === 0 ? "HAMMASI O'TDI" : failed.length + " ta XATO"} (${results.length - failed.length}/${results.length})`);
if (failed.length) failed.forEach((f) => console.log(`  ❌ ${f.name} — ${f.extra}`));
process.exit(failed.length === 0 ? 0 : 1);
