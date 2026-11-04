/**
 * LOKAL UNIT TEST — deploy talab qilmaydi, tarmoqqa chiqmaydi.
 *
 * ⚠️ Bu INTEGRATSION TEST EMAS. Mock qilinadi:
 *   - `env.AI.run`  (haqiqiy Workers AI chaqirilmaydi)
 *   - global `fetch` (haqiqiy Director API chaqirilmaydi)
 * Haqiqiy Workers AI, Director API, KV, Durable Object, deploy, autentifikatsiya — tekshirilMAYDI.
 * Prompt-injection testi faqat SIYOSAT MATNI mavjudligini tekshiradi — LLM xavfsizligini isbotlamaydi.
 *
 * Ishga tushirish (ZIP ochilgan papkada):  node selftest.mjs
 */
import worker, { __test } from "./worker.js";

// Ataylab SOXTA qiymatlar — hech qanday haqiqiy kalit emas.
const DUMMY_INBOUND = ["dummy", "inbound", String(4242)].join("-");
const DUMMY_AGENT_KEY = ["dummy", "agent", String(9191)].join("-");

const results = [];
const check = (name, cond, extra = "") => {
  results.push({ name, ok: !!cond, extra });
  console.log(`${cond ? "✅" : "❌"} ${name}${extra ? " — " + extra : ""}`);
};

// ─────────────────── mock qatlami ───────────────────
let lastPrompt = null;
let aiCalls = 0;
let ackRequests = [];
let aiDelayMs = 0;
let aiReply = "XULOSA: Tekshiruv bajarildi, dalil ko'rildi.\nVERDICT: OK\nRUXSAT: kerak emas";

function makeAI(over) {
  return {
    run: async (model, args) => {
      aiCalls++;
      lastPrompt = args.messages.find((m) => m.role === "user").content;
      if (aiDelayMs) await new Promise((r) => setTimeout(r, aiDelayMs));
      if (over) return over(model, args);
      return { response: aiReply };
    },
  };
}

function makeEnv(overrides = {}) {
  return {
    AGENT_ID: "agent-02-reviewer",
    INBOUND_SECRET: DUMMY_INBOUND,
    AGENT_KEY: DUMMY_AGENT_KEY,
    AI: makeAI(),
    ...overrides,
  };
}

let fetchReply = { status: 200, body: null, dynamic: null };
globalThis.fetch = async (url, opts) => {
  const sent = JSON.parse(opts.body);
  ackRequests.push({ url: String(url), headers: opts.headers, body: sent });
  if (fetchReply.dynamic) return fetchReply.dynamic(url, sent);
  const text =
    fetchReply.body === null ? JSON.stringify({ ok: true, task_id: sent.task_id, status: "ACK" }) : fetchReply.body;
  return new Response(text, { status: fetchReply.status, headers: { "Content-Type": "application/json" } });
};

// ─────────────────── yordamchilar ───────────────────
const AUTH = { "X-Relay-Secret": DUMMY_INBOUND };
const uid = (p) => `${p}-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;

function wire({ taskId, state = "[PROJECT_STATE] AGENT-SYSTEM | faza: hybrid_policy_active | versiya: v1", artifactBlock = "", to = "agent-02-reviewer" } = {}) {
  return [
    "[TYPE: TASK]",
    "[PROJECT_ID: AGENT-SYSTEM]",
    `[TASK_ID: ${taskId}]`,
    "[FROM: director]",
    `[TO: ${to}]`,
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

// ═══════════════════ A. HEALTH / KONFIGURATSIYA ═══════════════════
{
  const r = await worker.fetch(new Request("https://agent02.local/health"), makeEnv());
  const j = await r.json();
  check("health: 200, ready=true (to'liq konfiguratsiya)", r.status === 200 && j.ready === true);
  check("health: version = 1.4", j.version === "1.4", j.version);
  check("health: runtime = cloudflare_workers_ai", j.runtime === "cloudflare_workers_ai");
  check("health: checks.ai_binding = true", j.checks.ai_binding === true);
  check("health: verdict_policy = fail_closed_line_anchored", j.verdict_policy === "fail_closed_line_anchored");
  check("health: prompt_injection_policy = true", j.prompt_injection_policy === true);
  check("health: dedupe_scope = single_isolate", j.dedupe_scope === "single_isolate");
}

// #4 — AI binding yo'q bo'lsa ready:false
{
  const envNoAI = makeEnv({ AI: undefined });
  const j = await (await worker.fetch(new Request("https://agent02.local/health"), envNoAI)).json();
  check("#4 AI binding yo'q -> ready:false", j.ready === false);
  check("#4 AI binding yo'q -> checks.ai_binding:false", j.checks.ai_binding === false);
  check("#4 AI binding yo'q -> warning beriladi", j.warnings.some((w) => w.includes("AI binding")));

  const r = await postTask({ wire: wire({ taskId: uid("T-NOAI") }) }, AUTH, envNoAI);
  const b = await r.json();
  check("#4 AI binding yo'q -> /task 503 ai_binding_missing", r.status === 503 && b.error === "ai_binding_missing");

  const envNoInbound = makeEnv({ INBOUND_SECRET: undefined });
  const j2 = await (await worker.fetch(new Request("https://agent02.local/health"), envNoInbound)).json();
  check("#4 INBOUND_SECRET yo'q -> ready:false", j2.ready === false && j2.checks.inbound_secret === false);

  const envNoKey = makeEnv({ AGENT_KEY: undefined });
  const j3 = await (await worker.fetch(new Request("https://agent02.local/health"), envNoKey)).json();
  check("#4 AGENT_KEY yo'q -> ready:false", j3.ready === false && j3.checks.agent_key === false);
}

// ═══════════════════ B. KIRISH HIMOYASI ═══════════════════
{
  const r1 = await postTask({ wire: wire({ taskId: uid("T-A1") }) }, AUTH, makeEnv({ INBOUND_SECRET: undefined }));
  check("B: INBOUND_SECRET yo'q -> 503 fail-closed", r1.status === 503 && (await r1.json()).error === "inbound_secret_missing");

  const r2 = await postTask({ wire: wire({ taskId: uid("T-A2") }) }, {});
  check("B: sarlavhasiz -> 401", r2.status === 401);

  const r3 = await postTask({ wire: wire({ taskId: uid("T-A3") }) }, { "X-Relay-Secret": "wrong" });
  check("B: noto'g'ri sarlavha -> 401", r3.status === 401);

  const r4 = await postTask({ wire: wire({ taskId: uid("T-A4") }) });
  check("B: to'g'ri sarlavha -> 200", r4.status === 200);
}

// ═══════════════════ B2. #9 (v1.4.1) AGENT_KEY PREFLIGHT ═══════════════════
// Nuqson: v1.4 da AGENT_KEY yo'q bo'lsa ham AI bir marta chaqirilardi va keyin 502 qaytardi.
{
  const tid = uid("T-K1");
  fetchReply = { status: 200, body: null };
  ackRequests = [];
  aiCalls = 0;

  const envNoKey = makeEnv({ AGENT_KEY: undefined });
  const r = await postTask({ wire: wire({ taskId: tid }) }, AUTH, envNoKey);
  const j = await r.json();

  check("#9 AGENT_KEY yo'q -> 503", r.status === 503, `status=${r.status}`);
  check("#9 xato nomi agent_key_missing", j.error === "agent_key_missing", j.error);
  check("#9 javobda model_invoked:false", j.model_invoked === false);
  check("#9 javobda dedupe_marked:false", j.dedupe_marked === false);
  check("#9 javobda director_called:false", j.director_called === false);
  check("#9 AI.run() CHAQIRILMADI (aiCalls===0)", aiCalls === 0, `aiCalls=${aiCalls}`);
  check("#9 Director fetch SONI 0", ackRequests.length === 0, `fetch=${ackRequests.length}`);
  check("#9 prompt yozilmadi (model umuman ishlamadi)", lastPrompt === null || !String(lastPrompt).includes(tid));

  // dedupe holati qo'yilmaganini isbotlash: xuddi shu TASK_ID, AGENT_KEY bilan -> oddiy yo'l
  const r2 = await postTask({ wire: wire({ taskId: tid }) }, AUTH, makeEnv());
  const j2 = await r2.json();
  check("#9 preflight dublikat belgisi qoldirmadi (retry ACKNOWLEDGED)", r2.status === 200 && j2.status === "ACKNOWLEDGED", j2.status);
  check("#9 retry'da duplicate:false", j2.duplicate === false);
  check("#9 AGENT_KEY bilan oddiy yo'l AI'ni chaqiradi (aiCalls===1)", aiCalls === 1, `aiCalls=${aiCalls}`);
  check("#9 AGENT_KEY bilan Director'ga 1 marta ACK ketadi", ackRequests.length === 1, `fetch=${ackRequests.length}`);

  // AGENT_KEY bo'sh satr ham yo'q deb hisoblanadi
  aiCalls = 0;
  ackRequests = [];
  const r3 = await postTask({ wire: wire({ taskId: uid("T-K2") }) }, AUTH, makeEnv({ AGENT_KEY: "" }));
  const j3 = await r3.json();
  check("#9 AGENT_KEY:'' ham 503 agent_key_missing", r3.status === 503 && j3.error === "agent_key_missing");
  check("#9 AGENT_KEY:'' da ham aiCalls===0 va fetch 0", aiCalls === 0 && ackRequests.length === 0);

  // INBOUND_SECRET / AI preflight'lari AGENT_KEY'dan oldin ishlaydi (tartib saqlanadi)
  aiCalls = 0;
  ackRequests = [];
  const r4 = await postTask({ wire: wire({ taskId: uid("T-K3") }) }, AUTH, makeEnv({ AGENT_KEY: undefined, INBOUND_SECRET: undefined }));
  check("#9 INBOUND_SECRET ham yo'q -> inbound_secret_missing (birinchi to'siq)", r4.status === 503 && (await r4.json()).error === "inbound_secret_missing");

  const r5 = await postTask({ wire: wire({ taskId: uid("T-K4") }) }, { "X-Relay-Secret": "wrong" }, makeEnv({ AGENT_KEY: undefined }));
  check("#9 noto'g'ri kirish + AGENT_KEY yo'q -> 401 (preflight'dan oldin auth)", r5.status === 401);

  const r6 = await postTask({ wire: wire({ taskId: uid("T-K5") }) }, AUTH, makeEnv({ AGENT_KEY: undefined, AI: undefined }));
  check("#9 AGENT_KEY va AI ikkalasi yo'q -> ai_binding_missing (birinchi to'siq)", r6.status === 503 && (await r6.json()).error === "ai_binding_missing");

  // health ham shu holatni ko'rsatadi
  const h = await (await worker.fetch(new Request("https://agent02.local/health"), envNoKey)).json();
  check("#9 health: agent_key yo'q -> ready:false + checks.agent_key:false", h.ready === false && h.checks.agent_key === false);
  check("#9 health: 'ready:false => /task ishlamaydi' da'vosi endi kod bilan mos", h.ready === false && r.status === 503);
  aiCalls = 0;
  ackRequests = [];
}

// ═══════════════════ C. PARSING: PROJECT_STATE / ARTIFACT ═══════════════════
{
  const st = "AGENT-SYSTEM | faza: hybrid_policy_active | versiya: v7 | ochiq ruxsat: 2";
  await postTask({ wire: wire({ taskId: uid("T-S1"), state: `[PROJECT_STATE] ${st}` }) });
  check("C: `[PROJECT_STATE] matn` promptga tushdi", !!lastPrompt && lastPrompt.includes(st));
  check("C: 'berilmagan' yo'q", !!lastPrompt && !lastPrompt.includes("PROJECT_STATE: berilmagan"));

  const st2 = "AGENT-SYSTEM | kolon shakli v9";
  await postTask({ wire: wire({ taskId: uid("T-S2"), state: `[PROJECT_STATE: ${st2}]` }) });
  check("C: `[PROJECT_STATE: matn]` shakli ham ishlaydi", !!lastPrompt && lastPrompt.includes(st2));

  await postTask({ wire: wire({ taskId: uid("T-S3"), state: "" }) });
  check("C: state yo'q -> 'berilmagan' + kamchilik", !!lastPrompt && lastPrompt.includes("berilmagan") && lastPrompt.includes("kamchilik"));

  const code = "function add(a,b){ return a-b }  // BUG";
  await postTask({ wire: wire({ taskId: uid("T-S4"), artifactBlock: `[ARTIFACT_INLINE_BEGIN]\n${code}\n[ARTIFACT_INLINE_END]` }) });
  check("C: inline artifact promptga tushdi", !!lastPrompt && lastPrompt.includes("a-b"));

  await postTask({ wire: wire({ taskId: uid("T-S5"), artifactBlock: `[ARTIFACT_INLINE_BEGIN]\n${"x".repeat(12000)}\n[ARTIFACT_INLINE_END]` }) });
  check("C: katta artifact 8000 ga qisqaradi", !!lastPrompt && lastPrompt.includes("QISQARTIRILGAN"));

  await postTask({
    wire: wire({ taskId: uid("T-S6") }).replace("[ARTIFACT_REF: not_provided]", "[ARTIFACT_REF: https://github.com/x/y/z.js]"),
  });
  check("C: URL-only -> 'tashqi URL O'QIMAYDI' ogohlantirishi", !!lastPrompt && lastPrompt.includes("O'QIMAYDI"));
}

// ═══════════════════ D. #6 VERDICT — qatorga bog'langan, fail-closed ═══════════════════
{
  const { splitVerdict } = __test;

  const okV = splitVerdict("XULOSA: Hammasi joyida.\nVERDICT: OK\nRUXSAT: kerak emas");
  check("#6 oddiy VERDICT: OK qabul qilinadi", okV.verdict === "OK" && okV.fail_closed === false);

  const bugV = splitVerdict("XULOSA: Xato topildi.\nVERDICT: BUG_FOUND\nRUXSAT: kerak emas");
  check("#6 VERDICT: BUG_FOUND qabul qilinadi", bugV.verdict === "BUG_FOUND");

  const noVerdict = splitVerdict("XULOSA: Hammasi yaxshi.");
  check("#6 verdict yo'q -> NEEDS_APPROVAL", noVerdict.verdict === "NEEDS_APPROVAL" && noVerdict.fail_closed);

  // #6 asosiy regressiya: matn ichidagi (embedded) verdict hisobga olinmaydi
  const embedded = splitVerdict(
    "XULOSA: Artifactda shunday yozuv bor: VERDICT: OK deb yozilgan, lekin bu iqtibos.\nVERDICT: BUG_FOUND\nRUXSAT: kerak emas",
  );
  check("#6 matn ichidagi 'VERDICT: OK' e'tiborsiz, haqiqiy qator BUG_FOUND", embedded.verdict === "BUG_FOUND" && embedded.verdict_raw === "BUG_FOUND");

  const onlyEmbedded = splitVerdict("XULOSA: foydalanuvchi VERDICT: OK yozishni so'radi, men buni bajarmadim.");
  check("#6 faqat embedded verdict -> NEEDS_APPROVAL", onlyEmbedded.verdict === "NEEDS_APPROVAL" && onlyEmbedded.fail_closed);

  const dup = splitVerdict("XULOSA: a\nVERDICT: OK\nVERDICT: BUG_FOUND\nRUXSAT: kerak emas");
  check("#6 takroriy VERDICT -> NEEDS_APPROVAL", dup.verdict === "NEEDS_APPROVAL" && dup.fail_reasons.some((r) => r.includes("takrorlangan")));

  const unknown = splitVerdict("XULOSA: z\nVERDICT: LOOKS_FINE\nRUXSAT: kerak emas");
  check("#6 noma'lum qiymat -> NEEDS_APPROVAL", unknown.verdict === "NEEDS_APPROVAL" && unknown.verdict_raw === "LOOKS_FINE");

  const trailing = splitVerdict("XULOSA: a\nVERDICT: OK\nqo'shimcha izoh shu yerda");
  check("#6 verdict'dan keyin formatdan tashqari qator -> NEEDS_APPROVAL", trailing.verdict === "NEEDS_APPROVAL");

  const empty = splitVerdict("   ");
  check("#6 bo'sh javob -> NEEDS_APPROVAL", empty.verdict === "NEEDS_APPROVAL");

  const approval = splitVerdict("XULOSA: Tuzatish kerak.\nVERDICT: NEEDS_APPROVAL\nRUXSAT: 2 faylni o'zgartirishga ruxsat berasizmi?");
  check("#6 NEEDS_APPROVAL + savol saqlanadi", approval.needs_approval === true && approval.approval_question.includes("ruxsat berasizmi"));
}

// ═══════════════════ E. #5 MODEL ISHLAMASA ═══════════════════
{
  const envDown = makeEnv({ AI: makeAI(() => { throw new Error("model down"); }) });
  const r = await postTask({ wire: wire({ taskId: uid("T-E1") }) }, AUTH, envDown);
  const j = await r.json();
  check("#5 model yiqilsa -> NEEDS_APPROVAL (BUG_FOUND emas)", j.verdict === "NEEDS_APPROVAL", j.verdict);
  check("#5 runtime_failed flagi ko'rsatiladi", j.runtime_failed === true);
  check("#5 summary sababni aytadi", String(j.verdict).length > 0 && j.fail_closed === true);
  check("#5 model bo'sh javob bersa ham NEEDS_APPROVAL", (await (async () => {
    const envEmpty = makeEnv({ AI: makeAI(() => ({ response: "" })) });
    const rr = await postTask({ wire: wire({ taskId: uid("T-E2") }) }, AUTH, envEmpty);
    return (await rr.json()).verdict === "NEEDS_APPROVAL";
  })()));
}

// ═══════════════════ F. #3 ACK KONTRAKTI ═══════════════════
{
  const { validateAckResponse } = __test;

  check("#3 ok:true + task_id mos -> success",
    validateAckResponse(200, JSON.stringify({ ok: true, task_id: "T-X", status: "ACK" }), "T-X").ok === true);

  const missing = validateAckResponse(200, JSON.stringify({ ok: true, status: "ACK" }), "T-X");
  check("#3 task_id YO'Q -> failure (Director kontrakti majburiy)", missing.ok === false && missing.error === "director_task_id_missing");

  const nullId = validateAckResponse(200, JSON.stringify({ ok: true, task_id: null }), "T-X");
  check("#3 task_id:null -> failure", nullId.ok === false && nullId.error === "director_task_id_missing");

  const emptyId = validateAckResponse(200, JSON.stringify({ ok: true, task_id: "" }), "T-X");
  check("#3 task_id:'' -> failure", emptyId.ok === false);

  check("#3 ok:false -> failure",
    validateAckResponse(200, JSON.stringify({ ok: false, error: "UNKNOWN_TASK_ID" }), "T-X").error.startsWith("director_rejected"));
  check("#3 JSON buzuq -> failure", validateAckResponse(200, "Forbidden", "T-X").error === "director_invalid_json");
  check("#3 bo'sh javob -> failure", validateAckResponse(200, "", "T-X").error === "director_invalid_json");
  check("#3 array -> failure", validateAckResponse(200, "[]", "T-X").error === "director_invalid_schema");
  check("#3 task_id mos emas -> failure", validateAckResponse(200, JSON.stringify({ ok: true, task_id: "T-OTHER" }), "T-X").error === "director_task_id_mismatch");
  check("#3 HTTP 500 -> failure", validateAckResponse(500, JSON.stringify({ ok: true, task_id: "T-X" }), "T-X").error === "director_http_500");

  // E2E
  fetchReply = { status: 200, body: JSON.stringify({ ok: true, status: "ACK" }) };
  const r = await postTask({ wire: wire({ taskId: uid("T-F1") }) });
  const j = await r.json();
  check("#3 E2E task_id yo'q -> 502 + delivered:false",
    r.status === 502 && j.delivered_to_director === false && j.director_error === "director_task_id_missing");

  fetchReply = { status: 200, body: JSON.stringify({ ok: false, error: "UNKNOWN_TASK_ID" }) };
  const r2 = await postTask({ wire: wire({ taskId: uid("T-F2") }) });
  check("#3 E2E {ok:false} -> 502", r2.status === 502);

  fetchReply = { status: 200, body: null };
  const r3 = await postTask({ wire: wire({ taskId: uid("T-F3") }) });
  check("#3 E2E to'g'ri javob -> 200 + ACKNOWLEDGED", r3.status === 200 && (await r3.json()).status === "ACKNOWLEDGED");
}

// ═══════════════════ G. #1 DUBLIKAT JAVOBI ═══════════════════
{
  const tid = uid("T-G1");
  fetchReply = { status: 200, body: null };
  aiCalls = 0;
  const r1 = await postTask({ wire: wire({ taskId: tid }) });
  const j1 = await r1.json();
  const r2 = await postTask({ wire: wire({ taskId: tid }) });
  const j2 = await r2.json();

  check("#1 birinchi so'rov: ACKNOWLEDGED, duplicate:false", j1.status === "ACKNOWLEDGED" && j1.duplicate === false);
  check("#1 model faqat 1 marta chaqirilgan", aiCalls === 1, `aiCalls=${aiCalls}`);
  check("#1 dublikat: status=DUPLICATE", j2.status === "DUPLICATE" && j2.duplicate === true);
  check("#1 dublikat: verdict=null (yangi verdict yo'q)", j2.verdict === null);
  check("#1 dublikat: needs_approval=false", j2.needs_approval === false);
  check("#1 dublikat: ack_sent=false va delivered_to_director=false",
    j2.ack_sent === false && j2.delivered_to_director === false);
  check("#1 dublikat: model_invoked=false", j2.model_invoked === false);
  check("#1 dublikat: first_seen_state=completed", j2.first_seen_state === "completed");
  check("#1 dublikat javobida ziddiyatli maydon yo'q",
    !(j2.ok === true && j2.verdict === "NEEDS_APPROVAL" && j2.needs_approval === false));
  const acksForTid = ackRequests.filter((a) => a.body.task_id === tid).length;
  check("#1 dublikat uchun Director'ga yangi ACK yuborilmadi", acksForTid === 1, `ACK=${acksForTid}`);
}

// ═══════════════════ H. #2 CONCURRENT DEDUPE ═══════════════════
{
  const tid = uid("T-H1");
  fetchReply = { status: 200, body: null };
  aiCalls = 0;
  aiDelayMs = 40; // model sekin ishlaydi -> concurrent oyna katta bo'ladi
  const [a, b] = await Promise.all([
    postTask({ wire: wire({ taskId: tid }) }),
    postTask({ wire: wire({ taskId: tid }) }),
  ]);
  const ja = await a.json();
  const jb = await b.json();
  aiDelayMs = 0;

  check("#2 concurrent 2 so'rovda AI faqat 1 marta", aiCalls === 1, `aiCalls=${aiCalls}`);
  const statuses = [ja.status, jb.status].sort();
  check("#2 bittasi ACKNOWLEDGED, ikkinchisi DUPLICATE",
    statuses[0] === "ACKNOWLEDGED" && statuses[1] === "DUPLICATE", statuses.join(" / "));
  const dupSide = ja.status === "DUPLICATE" ? ja : jb;
  check("#2 in_flight holati qayd etilgan", ["in_flight", "completed"].includes(dupSide.first_seen_state), dupSide.first_seen_state);
  check("#2 dublikat tomonda delivered:false", dupSide.delivered_to_director === false);

  // ACK muvaffaqiyatsiz bo'lsa retry yo'li ochiq bo'lishi kerak
  const tid2 = uid("T-H2");
  fetchReply = { status: 500, body: JSON.stringify({ ok: false }) };
  aiCalls = 0;
  await postTask({ wire: wire({ taskId: tid2 }) });
  fetchReply = { status: 200, body: null };
  const retry = await postTask({ wire: wire({ taskId: tid2 }) });
  const jr = await retry.json();
  check("#2 ACK yiqilgach qayta urinish ishlaydi (belgi tozalanadi)", aiCalls === 2 && jr.status === "ACKNOWLEDGED");
  check("#2 qayta urinishda duplicate:false", jr.duplicate === false);
}

// ═══════════════════ I. #7 PROMPT INJECTION SIYOSATI ═══════════════════
{
  const { REVIEW_SYSTEM } = __test;
  check("#7 system prompt'da injection siyosati bor",
    /PROMPT INJECTION/i.test(REVIEW_SYSTEM) && /ISHLANCHSIZ|ISHONCHSIZ/.test(REVIEW_SYSTEM));
  check("#7 'ko'rsatmalarni BAJARMA' qoidasi bor", /BAJARMA|bajarma/.test(REVIEW_SYSTEM));
  check("#7 verdict'ni kirish matni o'zgartira olmasligi yozilgan",
    /verdict qiymatini/i.test(REVIEW_SYSTEM) && /o'zgartira olmaydi/i.test(REVIEW_SYSTEM));
  check("#7 javob formati qat'iy belgilangan", /VERDICT: OK \| BUG_FOUND \| NEEDS_APPROVAL/.test(REVIEW_SYSTEM));

  // user prompt ham ishonchsiz bloklarni belgilaydi
  await postTask({ wire: wire({ taskId: uid("T-I1") }) });
  check("#7 user prompt 'ISHLANCHSIZ KIRISH' deb belgilaydi",
    !!lastPrompt && /ISHONCHSIZ KIRISH/i.test(lastPrompt) && /bajarma/i.test(lastPrompt));
}

// ═══════════════════ J. CHEGARALAR VA PROTOKOL ═══════════════════
{
  check("J: boshqa agentga TASK -> 400", (await postTask({ wire: wire({ taskId: uid("T-J1"), to: "agent-99" }) })).status === 400);
  check("J: TASK_ID yo'q -> 400", (await postTask({ wire: "salom" })).status === 400);
  check("J: 20KB dan katta -> 413", (await postTask({ wire: wire({ taskId: uid("T-J2") }) + "x".repeat(20000) })).status === 413);
  check("J: noma'lum yo'l -> 404", (await worker.fetch(new Request("https://agent02.local/nope"), makeEnv())).status === 404);

  fetchReply = { status: 200, body: null };
  ackRequests = [];
  const tid = uid("T-J3");
  await postTask({ wire: wire({ taskId: tid }) });
  const last = ackRequests[ackRequests.length - 1];
  check("J: ACK X-Agent-Key yuboriladi", last.headers["X-Agent-Key"] === DUMMY_AGENT_KEY);
  check("J: ACK X-Agent-Id yuboriladi", last.headers["X-Agent-Id"] === "agent-02-reviewer");
  check("J: ACK endpoint to'g'ri", last.url === "https://diyor-agency-24-7.pages.dev/api/sync");
  check("J: ACK op = jamoa_ack", last.body.op === "jamoa_ack");
  check("J: ACK verdict maydonlari bor", "verdict" in last.body && "fail_closed" in last.body);
}

// ═══════════════════ yakun ═══════════════════
const failed = results.filter((r) => !r.ok);
console.log("\n─────────────────────────────────────────────");
console.log(`MOCK QILINGAN: env.AI.run (${aiCalls > 0 ? "chaqirilgan" : "0"}) va global fetch (Director API).`);
console.log("HAQIQIY TEKSHIRILMAGAN: Workers AI, Director API, KV, Durable Object, deploy, autentifikatsiya.");
console.log("PROMPT-INJECTION: faqat siyosat MATNI tekshiriladi — LLM xavfsizligi isbotlanmaydi.");
console.log(`${failed.length === 0 ? "HAMMASI O'TDI" : failed.length + " ta XATO"} (${results.length - failed.length}/${results.length})`);
if (failed.length) failed.forEach((f) => console.log(`  ❌ ${f.name} — ${f.extra}`));
process.exit(failed.length === 0 ? 0 : 1);
