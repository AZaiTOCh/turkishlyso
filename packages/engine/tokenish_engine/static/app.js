const messagesEl = document.getElementById("messages");
const errorEl = document.getElementById("error");
const promptEl = document.getElementById("prompt");
const fileInput = document.getElementById("fileInput");
const attachmentsEl = document.getElementById("attachments");
const providersEl = document.getElementById("providers");
const modelSelect = document.getElementById("model");
const providerSelect = document.getElementById("provider");
const threadListEl = document.getElementById("threadList");

const STORE_KEY = "tokenish.threads.v2";
const MUMBLZ_REV = "lowercase-titles-v1";
const WELCOME = "Attach a pdf, docx, xlsx, csv, or image. tokenish optimizes every send automatically.";
const MAX_VISION_IMAGES = 16;
const MAX_ATTACH_FILES = 20;
const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "webp", "gif", "bmp"]);

const DEFAULT_MODELS = [
  "gemini-3.5-flash",
  "openrouter/free",
];

const MODELS_BY_PROVIDER = {
  auto: ["gemini-3.5-flash", "claude-sonnet-4-20250514", "gpt-4o", "openrouter/free", "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "grok-3", "sonar"],
  gemini: ["gemini-3.5-flash"],
  openrouter: ["openrouter/free"],
  groq: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
  grok: ["grok-3"],
  anthropic: ["claude-sonnet-4-20250514"],
  openai: ["gpt-4o"],
  perplexity: ["sonar"],
};

const PROVIDER_BY_MODEL = {};
for (const [p, models] of Object.entries(MODELS_BY_PROVIDER)) {
  if (p === "auto") continue;
  for (const m of models) PROVIDER_BY_MODEL[m] = p;
}

const PROVIDER_OPTION_LABELS = {
  auto: "auto (recommended)",
  gemini: "gemini",
  openrouter: "openrouter",
  grok: "grok",
  groq: "groq",
  anthropic: "claude",
  openai: "chatgpt",
  perplexity: "perplexity",
};

/** @type {Record<string, { usable: boolean, reason: string, hint: string, detail: string }>} */
let providerHealth = {};

const AUTH_KEY = "tokenish.auth.v1";
const GRETTA_INTRO_KEY = "tokenish.gretta.intro.v3";
const GRETTA_SEEN_KEY = "tokenish.gretta.seen.v3";
const GRETTA_PICK_KEY = "tokenish.gretta.pick.v1";
const GRETTA_FLOW = "tokenish.gretta.flow.v3"; // session step: intro|auth|api|keys|need|done
const SIDEBAR_KEY = "tokenish.sidebars.v1";
const SESSION_BOOT_KEY = "tokenish.session.boot.v1";


let files = [];
let threads = [];
let activeId = null;
/** Set when Gretta fidelity gate rejects current attachments/need. */
let materialBlocked = false;
/** Lifetime totals across ALL chats — never reset on new chat. */
let lifetime = emptyTokex();
let linkedKeysStatus = {
  gemini: false,
  openrouter: false,
  openai: false,
  anthropic: false,
  perplexity: false,
  groq: false,
  grok: false,
};

function uid() {
  return `t_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function emptyTokex() {
  return { before: 0, after: 0, saved: 0, last: null, sends: [] };
}

function normalizeTokex(raw) {
  const t = { ...emptyTokex(), ...(raw || {}) };
  if (!Array.isArray(t.sends)) t.sends = [];
  if (!t.sends.length && t.last && (t.before || t.after)) {
    const firstBefore = Math.max(0, t.before - (t.last.before || 0));
    const firstAfter = Math.max(0, t.after - (t.last.after || 0));
    const firstSaved = Math.max(0, t.saved - (t.last.saved || 0));
    if (firstBefore > 0) {
      t.sends.push({
        before: firstBefore,
        after: firstAfter,
        saved: firstSaved,
        pct: Math.round((firstSaved / firstBefore) * 10000) / 100,
      });
    }
    t.sends.push({ ...t.last });
  }
  return t;
}

function rebuildLifetimeFromThreads() {
  const agg = emptyTokex();
  for (const th of threads) {
    const t = normalizeTokex(th.tokex);
    th.tokex = t;
    for (const s of t.sends) {
      agg.before += Number(s.before || 0);
      agg.after += Number(s.after || 0);
      agg.saved += Number(s.saved || 0);
      agg.sends.push({ ...s, threadId: th.id, title: th.title });
      agg.last = s;
    }
  }
  return agg;
}

function newThread(title = "new chat") {
  return {
    id: uid(),
    title,
    updatedAt: Date.now(),
    messages: [{ role: "assistant", content: WELCOME }],
    tokex: emptyTokex(),
  };
}

function loadStore() {
  try {
    const raw = localStorage.getItem(STORE_KEY) || localStorage.getItem("tokenish.threads.v1");
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveStore() {
  localStorage.setItem(
    STORE_KEY,
    JSON.stringify({ activeId, threads, lifetime }),
  );
}

function activeThread() {
  return threads.find((t) => t.id === activeId) || null;
}

function showError(msg) {
  errorEl.hidden = !msg;
  errorEl.textContent = msg || "";
  errorEl.className = "error";
}

function showInfo(msg) {
  errorEl.hidden = !msg;
  errorEl.textContent = msg || "";
  errorEl.className = msg ? "error info-note" : "error";
}

function fileExt(name) {
  const m = String(name || "").toLowerCase().match(/\.([a-z0-9]+)$/);
  return m ? m[1] : "";
}

function isImageFile(f) {
  if (!f) return false;
  if (f.type && f.type.startsWith("image/")) return true;
  return IMAGE_EXTS.has(fileExt(f.name));
}

function fileKey(f) {
  return `${f.name}::${f.size}::${f.lastModified || 0}`;
}

function countImages(list) {
  return (list || []).filter(isImageFile).length;
}

function tknshHtml() {
  return `<div class="tknsh" aria-label="working"><span>t</span><span>k</span><span>n</span><span>s</span><span>h</span></div>`;
}

function renderAttachments({ staging = false, stagingCount = 0 } = {}) {
  const chips = files
    .map((f, i) => {
      const kind = isImageFile(f) ? "image" : "file";
      return (
        `<span class="chip ready" data-idx="${i}" title="${escapeHtml(f.name)}">` +
        `<span class="chip-kind">${kind}</span>` +
        `<span class="chip-name">${escapeHtml(f.name)}</span>` +
        `<button type="button" class="chip-x" aria-label="remove">×</button>` +
        `</span>`
      );
    })
    .join("");
  const status = staging
    ? `<span class="attach-status">${tknshHtml()}<span>reading ${stagingCount || ""} file${(stagingCount || 0) === 1 ? "" : "s"}…</span></span>`
    : files.length
      ? `<span class="attach-meta">${files.length} attached · ${countImages(files)} image${countImages(files) === 1 ? "" : "s"}</span>`
      : "";
  attachmentsEl.innerHTML = chips + status;
  attachmentsEl.querySelectorAll(".chip-x").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const idx = Number(btn.closest(".chip")?.dataset?.idx);
      if (!Number.isFinite(idx)) return;
      files.splice(idx, 1);
      renderAttachments();
      showError("");
    };
  });
}

async function stageIncomingFiles(incoming) {
  const list = Array.from(incoming || []);
  if (!list.length) return;
  showError("");
  renderAttachments({ staging: true, stagingCount: list.length });

  // Brief tknsh pulse while files are staged locally (same animation as chat).
  await new Promise((r) => setTimeout(r, 280));

  const seen = new Set(files.map(fileKey));
  const next = [...files];
  const skipped = [];
  for (const f of list) {
    const key = fileKey(f);
    if (seen.has(key)) {
      skipped.push(`${f.name} (already attached)`);
      continue;
    }
    if (next.length >= MAX_ATTACH_FILES) {
      skipped.push(`${f.name} (max ${MAX_ATTACH_FILES} files)`);
      continue;
    }
    if (isImageFile(f) && countImages(next) >= MAX_VISION_IMAGES) {
      skipped.push(`${f.name} (vision limit ${MAX_VISION_IMAGES} images)`);
      continue;
    }
    // Touch-read so the browser surfaces large-file / permission errors early.
    try {
      await f.slice(0, 16).arrayBuffer();
    } catch (err) {
      skipped.push(`${f.name} (could not read)`);
      continue;
    }
    seen.add(key);
    next.push(f);
  }
  files = next;
  renderAttachments();
  if (skipped.length) {
    showError(`could not attach all files: ${skipped.slice(0, 4).join("; ")}${skipped.length > 4 ? "…" : ""}`);
  }
  if (next.length) {
    const gate = assessMaterialSuitability(next, "");
    publishGrettaNote(gate.note, { blocked: !gate.ok });
  } else {
    materialBlocked = false;
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function formatReply(text) {
  let s = String(text || "");
  // Keep trailing reply-meta line intact for HTML styling.
  let meta = "";
  const metaMatch = s.match(/\n\n— (.+)$/);
  if (metaMatch) {
    meta = metaMatch[1];
    s = s.slice(0, -metaMatch[0].length);
  }
  s = s.replace(/^#{1,6}\s+/gm, "");
  s = s.replace(/\*\*([^*]+)\*\*/g, "$1");
  s = s.replace(/__([^_]+)__/g, "$1");
  s = s.replace(/\*([^*]+)\*/g, "$1");
  s = s.replace(/^---+$/gm, "");
  s = s.replace(/^>\s?/gm, "");
  let html = escapeHtml(s);
  if (meta) {
    html += `<div class="reply-meta">— ${escapeHtml(meta)}</div>`;
  }
  return html;
}

function formatReplyStamp(provider, model, tokex) {
  const when = new Date().toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
  const who = [provider, model].filter(Boolean).join(" / ") || "unknown model";
  let tokens = "";
  if (tokex) {
    const after = Number(
      tokex.after ?? tokex.tokex_this_run ?? tokex.optimized_tokens ?? 0,
    );
    const before = Number(
      tokex.before ?? tokex.total_tokex ?? tokex.original_tokens ?? after,
    );
    const saved = Number(
      tokex.saved ?? tokex.saved_tokex ?? tokex.saved_tokens ?? Math.max(0, before - after),
    );
    if (after > 0 || before > 0) {
      tokens = ` · ${after.toLocaleString()} tokens`;
      if (before > 0) {
        const pct = Math.round((saved / before) * 10000) / 100;
        tokens += ` (${before.toLocaleString()}→${after.toLocaleString()}, saved ${pct}%)`;
      }
    }
  }
  return `— ${who} · ${when}${tokens}`;
}

/** Auto: Gemini 3.5 Flash first, unless Claude or an updated GPT (not gpt-4o) is linked. */
function isUpdatedGptModel(model) {
  const s = String(model || "").toLowerCase();
  if (!s || s.includes("gpt-4o")) return false; // gpt-4o / 4o-mini = old for auto priority
  return /gpt-4\.1|gpt-5|\bo3\b|\bo4\b|\bo1\b/.test(s);
}

function pickAutoPreferredModel() {
  // 1) Claude if linked + usable
  if (linkedKeysStatus.anthropic && healthForProvider("anthropic").usable) {
    return "claude-sonnet-4-20250514";
  }
  // 2) Updated GPT only (gpt-4o does NOT beat Gemini)
  if (linkedKeysStatus.openai && healthForProvider("openai").usable) {
    const openaiModel = (MODELS_BY_PROVIDER.openai || [])[0] || "gpt-4o";
    if (isUpdatedGptModel(openaiModel)) return openaiModel;
  }
  // 3) Gemini everyday default
  if (linkedKeysStatus.gemini) return "gemini-3.5-flash";

  const rest = [
    ["openrouter", "openrouter/free"],
    ["groq", "llama-3.3-70b-versatile"],
    ["grok", "grok-3"],
    ["perplexity", "sonar"],
  ];
  for (const [prov, mdl] of rest) {
    if (linkedKeysStatus[prov] && healthForProvider(prov).usable) return mdl;
  }
  for (const [prov, mdl] of rest) {
    if (linkedKeysStatus[prov]) return mdl;
  }
  return "gemini-3.5-flash";
}

const FIDELITY_RISK_RE =
  /\b(contract|agreement|nda|msa|sow\b|legal|deposition|affidavit|subpoena|court.?filing|litigation|patent|trademark|hipaa|phi\b|medical.?record|clinical.?trial|tax.?return|10-?k|10-?q|sec.?filing|prospectus|scientific|arxiv|theorem|lemma|proof\b|equation|mission.?critical|regulated.?record)\b/i;

function fidelityBlockReason(blob) {
  const t = String(blob || "").toLowerCase();
  if (/\b(contract|agreement|nda|msa|sow\b)\b/.test(t)) {
    return "nah — that reads like a contract/agreement. every clause matters, so Tokenish sits this one out.";
  }
  if (/\b(legal|deposition|affidavit|subpoena|court|litigation)\b/.test(t)) {
    return "nah — legal stuff. we’d risk fidelity, so not clear for Tokenish.";
  }
  if (/\b(scientific|arxiv|theorem|lemma|proof\b|equation)\b/.test(t)) {
    return "nah — science/math papers. one dropped line can wreck the answer.";
  }
  if (/\b(hipaa|phi\b|medical|clinical|tax.?return|10-?k|10-?q|sec.?filing|prospectus|patent|regulated|mission.?critical)\b/.test(t)) {
    return "nah — regulated / mission-critical. Tokenish won’t touch it.";
  }
  return "nah — that material isn’t clear for Tokenish (fidelity risk).";
}

/** Rough pre-send TOKEX band from file kinds (not a measured Agatha number). */
function estimateTokexBand(files) {
  const list = Array.from(files || []);
  if (!list.length) return null;
  let lo = 4;
  let hi = 10;
  for (const f of list) {
    const n = String(f.name || "").toLowerCase();
    const t = String(f.type || "").toLowerCase();
    if (/\.(csv|tsv)$/.test(n)) {
      lo = Math.max(lo, 12);
      hi = Math.max(hi, 28);
    } else if (/\.(json|jsonl)$/.test(n)) {
      lo = Math.max(lo, 10);
      hi = Math.max(hi, 25);
    } else if (/\.(pdf|docx?|md|txt)$/.test(n)) {
      lo = Math.max(lo, 6);
      hi = Math.max(hi, 18);
    } else if (/^image\//.test(t) || /\.(png|jpe?g|webp|gif|bmp)$/.test(n)) {
      lo = Math.max(lo, 3);
      hi = Math.max(hi, 12);
    } else if (/^video\//.test(t) || /\.(mp4|webm|mov)$/.test(n)) {
      lo = Math.max(lo, 8);
      hi = Math.max(hi, 35);
    }
  }
  return { lo, hi };
}

function assessMaterialSuitability(fileList, needText) {
  const files = Array.from(fileList || []);
  const blob = [
    needText || "",
    ...files.map((f) => `${f.name || ""} ${f.type || ""}`),
  ].join(" ");
  if (FIDELITY_RISK_RE.test(blob)) {
    return {
      ok: false,
      note: fidelityBlockReason(blob),
    };
  }
  if (!files.length && !String(needText || "").trim()) {
    return { ok: true, note: "" };
  }
  if (!files.length) {
    return {
      ok: true,
      note: "clear for Tokenish. bare chat usually saves ~0% TOKEX — attach material if you want real savings.",
    };
  }
  const band = estimateTokexBand(files);
  const est = band
    ? ` est ~${band.lo}–${band.hi}% TOKEX if cylinders fire (rough, pre-measure).`
    : "";
  return {
    ok: true,
    note: `clear for Tokenish.${est}`,
  };
}

function publishGrettaNote(note, { blocked = false } = {}) {
  if (!note) return;
  materialBlocked = !!blocked;
  const th = activeThread();
  const status = document.getElementById("grettaSlotStatus");
  if (status) status.textContent = note;
  if (th) {
    addBubble("assistant", note);
    th.messages.push({ role: "assistant", content: note });
    saveStore();
  }
}

function fillTokexBox(prefix, t, scopeLabel) {
  t = normalizeTokex(t);
  const before = t.before || 0;
  const after = t.after || 0;
  const saved = Math.max(0, t.saved || before - after);
  const grandPct = before > 0 ? Math.round((saved / before) * 10000) / 100 : 0;

  document.getElementById(`${prefix}Saved`).textContent = before
    ? `saved tokens ${grandPct}%`
    : "saved tokens 0%";
  document.getElementById(`${prefix}Scope`).textContent = scopeLabel;
  document.getElementById(`${prefix}Total`).textContent = Number(before).toLocaleString();
  document.getElementById(`${prefix}Run`).textContent = Number(after).toLocaleString();
  document.getElementById(`${prefix}Pct`).textContent = `${Number(saved).toLocaleString()} (${grandPct}%)`;

  const metaEl = document.getElementById(`${prefix}Meta`);
  const sendsEl = document.getElementById(`${prefix}Sends`);
  if (!t.sends.length) {
    metaEl.innerHTML = `<div class="tokex-details-empty">no send details yet</div>`;
    sendsEl.innerHTML = "";
    return;
  }
  const parts = t.sends.map((s) => Number(s.saved || 0).toLocaleString()).join(" + ");
  metaEl.textContent =
    `saved ${parts} = ${Number(saved).toLocaleString()} ÷ before ${Number(before).toLocaleString()} = ${grandPct}%`;
  sendsEl.innerHTML = t.sends
    .map(
      (s, i) =>
        `<div>send ${i + 1}: saved ${Number(s.saved).toLocaleString()} ` +
        `(${Number(s.before).toLocaleString()} → ${Number(s.after).toLocaleString()}) · ${s.pct}%</div>`,
    )
    .join("");
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

function localZoneAbbrev(date) {
  try {
    const parts = new Intl.DateTimeFormat(undefined, { timeZoneName: "short" }).formatToParts(date);
    const z = parts.find((p) => p.type === "timeZoneName")?.value;
    if (z) return z;
  } catch { /* ignore */ }
  try {
    const off = -date.getTimezoneOffset();
    const sign = off >= 0 ? "+" : "-";
    const abs = Math.abs(off);
    return `UTC${sign}${pad2(Math.floor(abs / 60))}:${pad2(abs % 60)}`;
  } catch {
    return "";
  }
}

function tickLiveWorldClock() {
  const el = document.getElementById("liveWorldClock");
  if (!el) return;
  const d = new Date();
  const zone = localZoneAbbrev(d);
  el.textContent = zone
    ? `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())} ${zone}`
    : `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

function formatSavedPct(pct) {
  const n = Number(pct);
  if (!Number.isFinite(n)) return "0.00";
  return n.toFixed(2);
}

function renderGlobalClock(data) {
  const savedEl = document.getElementById("globalSaved");
  const noteEl = document.getElementById("globalNote");
  const usersEl = document.getElementById("globalUsers");
  if (!savedEl || !noteEl) return;
  const before = Number(data?.total_tokex || 0);
  const saved = Number(data?.saved_tokex || 0);
  const pct =
    data?.saved_pct != null
      ? Number(data.saved_pct)
      : before > 0
        ? Math.round((saved / before) * 10000) / 100
        : 0;
  savedEl.textContent = `${formatSavedPct(pct)}%`;
  noteEl.textContent = "Live World Counter";
  noteEl.title = data?.note || "";
  if (usersEl) {
    const connected = !!data?.hive_opt_in;
    const users = Number(data?.users_online ?? 0);
    usersEl.textContent = connected
      ? `connected users online: ${users}`
      : `users online: ${users}`;
  }
}

async function syncLifetimeToHive() {
  lifetime = normalizeTokex(lifetime);
  try {
    await fetch("/tokex-clock/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        saved_tokex: Math.max(0, Math.round(lifetime.saved || 0)),
        total_tokex: Math.max(0, Math.round(lifetime.before || 0)),
      }),
    });
  } catch { /* hive optional */ }
}

async function refreshTokexClock() {
  try {
    await syncLifetimeToHive();
    const res = await fetch("/tokex-clock", { cache: "no-store" });
    const data = await res.json();
    renderGlobalClock(data);
    return data;
  } catch {
    renderGlobalClock({ saved_tokex: 0, total_tokex: 0, hive_opt_in: false, users_online: 0, source: "offline" });
    return null;
  }
}

async function maybeShowHiveConnect(force) {
  const modal = document.getElementById("hiveModal");
  if (!modal) return;
  try {
    const res = await fetch("/tokex-clock/status", { cache: "no-store" });
    const data = await res.json();
    const opt = document.getElementById("hiveOptIn");
    const url = document.getElementById("hiveUrlInput");
    if (opt) opt.checked = !!data.hive_opt_in;
    if (url) url.value = data.hive_url || "";
    renderGlobalClock(data.clock || data);
    if (force || data.hive_opt_in == null) {
      /* show only when forced via ⋮ or first invitation */
    }
    if (force) modal.hidden = false;
    else if (!data.hive_opt_in && !localStorage.getItem("tokenish.hive.prompted")) {
      modal.hidden = false;
      localStorage.setItem("tokenish.hive.prompted", "1");
    }
  } catch {
    if (force) modal.hidden = false;
  }
}

function closeAllTokexDetailMenus() {
  document.querySelectorAll(".tokex-details-menu.open").forEach((el) => el.classList.remove("open"));
}

function renderTokexPanel(thread) {
  lifetime = normalizeTokex(lifetime);
  fillTokexBox(
    "life",
    lifetime,
    lifetime.sends.length
      ? `grand total (all chats) · ${lifetime.sends.length} send${lifetime.sends.length === 1 ? "" : "s"}`
      : "grand total (all chats)",
  );

  const th = thread || activeThread();
  const chat = normalizeTokex(th?.tokex);
  if (th) th.tokex = chat;
  fillTokexBox(
    "chat",
    chat,
    chat.sends.length
      ? `current chat (${chat.sends.length} send${chat.sends.length === 1 ? "" : "s"})`
      : "current chat (0 sends)",
  );
  refreshTokexClock();
}

function accumulateTokex(thread, report) {
  if (!thread || !report) return;
  thread.tokex = normalizeTokex(thread.tokex);
  lifetime = normalizeTokex(lifetime);
  const before = Number(report.total_tokex ?? report.original_tokens ?? 0);
  const after = Number(report.tokex_this_run ?? report.optimized_tokens ?? 0);
  const saved = Number(report.saved_tokex ?? report.saved_tokens ?? Math.max(0, before - after));
  const pct =
    Math.round(Number(report.saved_pct ?? (before > 0 ? (saved / before) * 100 : 0)) * 100) / 100;
  const send = { before, after, saved, pct, threadId: thread.id, title: thread.title };
  thread.tokex.before += before;
  thread.tokex.after += after;
  thread.tokex.saved += saved;
  thread.tokex.last = send;
  thread.tokex.sends.push(send);
  lifetime.before += before;
  lifetime.after += after;
  lifetime.saved += saved;
  lifetime.last = send;
  lifetime.sends.push(send);
  // Neoborg / Live World Counter Clock refreshes after each measured send.
  refreshTokexClock();
}

function addBubble(role, content, attachments) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  if (role === "user") {
    const attachHtml = renderMessageAttachments(attachments);
    div.innerHTML =
      `<div class="body">${escapeHtml(content)}</div>` +
      attachHtml;
  } else {
    div.innerHTML = `<div class="body">${formatReply(content)}</div>`;
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function renderMessageAttachments(attachments) {
  const list = Array.isArray(attachments) ? attachments.filter(Boolean) : [];
  if (!list.length) return "";
  const imgs = list.filter((a) => a.kind === "image").length;
  const filesN = list.length - imgs;
  const summaryParts = [];
  if (imgs) summaryParts.push(`${imgs} image${imgs === 1 ? "" : "s"}`);
  if (filesN) summaryParts.push(`${filesN} file${filesN === 1 ? "" : "s"}`);
  const summary = summaryParts.join(" · ") || `${list.length} attached`;
  const cards = list
    .map((a) => {
      const name = escapeHtml(a.name || "attachment");
      if (a.kind === "image" && a.thumb) {
        return (
          `<div class="msg-attach image" title="${name}">` +
          `<img src="${a.thumb}" alt="${name}" />` +
          `<span class="msg-attach-name">${name}</span>` +
          `</div>`
        );
      }
      const kind = escapeHtml(a.kind || "file");
      return (
        `<div class="msg-attach file" title="${name}">` +
        `<span class="msg-attach-badge">${kind}</span>` +
        `<span class="msg-attach-name">${name}</span>` +
        `</div>`
      );
    })
    .join("");
  return (
    `<div class="msg-attachments" aria-label="uploaded attachments">` +
    `<div class="msg-attach-summary">${escapeHtml(summary)} uploaded</div>` +
    `<div class="msg-attach-grid">${cards}</div>` +
    `</div>`
  );
}

async function makeThumbDataUrl(file, maxEdge = 96) {
  if (!file || !isImageFile(file)) return null;
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      try {
        const scale = Math.min(1, maxEdge / Math.max(img.width, img.height));
        const w = Math.max(1, Math.round(img.width * scale));
        const h = Math.max(1, Math.round(img.height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL("image/jpeg", 0.72));
      } catch {
        resolve(null);
      } finally {
        URL.revokeObjectURL(url);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(null);
    };
    img.src = url;
  });
}

async function snapshotAttachments(fileList) {
  const out = [];
  for (const f of fileList || []) {
    const kind = isImageFile(f) ? "image" : "file";
    const item = {
      name: f.name,
      kind,
      size: f.size || 0,
    };
    if (kind === "image") {
      item.thumb = await makeThumbDataUrl(f);
    }
    out.push(item);
  }
  return out;
}

function makeTknshLoader() {
  const wrap = document.createElement("div");
  wrap.className = "bubble assistant thinking";
  wrap.innerHTML = `<div class="tknsh" aria-label="working"><span>t</span><span>k</span><span>n</span><span>s</span><span>h</span></div>`;
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrap;
}

function titleFromPrompt(prompt) {
  const t = (prompt || "").trim().replace(/\s+/g, " ").toLowerCase();
  if (!t) return "new chat";
  return t.length > 42 ? `${t.slice(0, 42)}…` : t;
}

function titleWord(w) {
  if (!w) return w;
  return String(w).toLowerCase();
}

/** Mumblz: normalize to two lowercase words (no vowel stripping). */
function mumblzTitle(title) {
  const parts = String(title || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "fresh thread";
  return parts.slice(0, 2).map(titleWord).join(" ");
}

/** True if title looks vowel-stripped (old Mumblz mumble). Never keep these. */
function isVowellessTitle(title) {
  const letters = String(title || "").replace(/[^A-Za-z]/g, "");
  if (letters.length < 2) return false;
  return !/[aeiouAEIOU]/.test(letters);
}

/** Mumblz local title: two most suitable words from the dialog. */
function interpretTitleLocal(messages) {
  const stop = new Set([
    "the","a","an","and","or","to","of","in","on","for","with","as","by","at","from",
    "is","are","was","be","this","that","it","i","you","we","my","your","please","want",
    "need","deeply","attached","attachment","document","file","pdf","image","images",
    "then","generate","check","online","sources","everything","page","one","two","three",
    "color","colour",
  ]);
  const blob = (messages || [])
    .filter((m) => m && (m.role === "user" || m.role === "assistant"))
    .map((m) => String(m.content || ""))
    .join("\n")
    .slice(0, 5000);
  if (!blob.trim()) return mumblzTitle("fresh thread");

  const rules = [
    [/unicombinator|freefactorial|freesar|g[- ]?triangle/i, "combinatorics", 12],
    [/gveb|waldo|raphael|bosch|visual exhaustion/i, "benchmark", 12],
    [/palette|color|colour|painterly|brushstroke|chromatic/i, "chromatic", 10],
    [/peer review|adversar|critique/i, "critique", 9],
    [/fact[- ]?check|vetting|validity/i, "vetting", 8],
    [/exec(utive)?\s*summary|brief/i, "digest", 8],
    [/animation|cel[- ]?shad|cartoon/i, "animation", 8],
    [/urban|street|parking|cityscape/i, "cityscape", 8],
    [/quantum|cryptograph/i, "quantum", 9],
    [/assess|analy/i, "assessment", 5],
  ];
  const tasks = [
    [/adversar|peer review|critique/i, "critique", 10],
    [/fact[- ]?check|vet|valid/i, "audit", 9],
    [/summar|brief|exec/i, "digest", 8],
    [/color|style|ratio|break\s*down/i, "breakdown", 8],
    [/synthes/i, "synthesis", 7],
    [/assess|analy/i, "scrutiny", 6],
  ];
  const friendly = [
    "scrutiny", "digest", "breakdown", "synthesis", "contrast",
    "framework", "signalcraft", "threadmark", "spotlight", "blueprint",
  ];

  const pool = new Map();
  const add = (word, sem) => {
    const t = titleWord(String(word || "").replace(/[^A-Za-z0-9-]/g, ""));
    if (!t || t.length < 3 || stop.has(t.toLowerCase())) return;
    if (isVowellessTitle(t)) return;
    pool.set(t, Math.max(pool.get(t) || 0, sem));
  };

  for (const [re, label, sem] of rules) {
    if (re.test(blob)) add(label, sem + 8);
  }
  for (const [re, label, sem] of tasks) {
    if (re.test(blob)) add(label, sem + 7);
  }
  const counts = {};
  for (const w of blob.toLowerCase().match(/[a-z][a-z0-9'-]{3,}/g) || []) {
    if (stop.has(w)) continue;
    counts[w] = (counts[w] || 0) + 1;
  }
  for (const [w, n] of Object.entries(counts)) add(w, n + 2);
  friendly.forEach((w, i) => add(w, 3.5 - i * 0.15));

  const ranked = [...pool.entries()].sort((a, b) => b[1] - a[1]);

  const picked = [];
  for (const [word] of ranked) {
    if (picked.some((p) => p.toLowerCase() === word.toLowerCase())) continue;
    if (picked.some((p) => p.toLowerCase().slice(0, 5) === word.toLowerCase().slice(0, 5))) continue;
    picked.push(word);
    if (picked.length >= 2) break;
  }
  while (picked.length < 2) {
    const fb = friendly.find((w) => !picked.some((p) => p.toLowerCase() === w.toLowerCase()));
    picked.push(fb || ["signalcraft", "blueprint"][picked.length]);
  }
  return mumblzTitle(picked.slice(0, 2).join(" "));
}

function looksProvisionalTitle(title) {
  const t = String(title || "").trim();
  if (!t || t === "new chat" || t === "New chat" || t === "Fresh Token Thread" || t === "Fresh Thread" || t === "fresh thread" || t === "Frsh Tkn Thrd") return true;
  if (t.includes("…") || t.includes("...")) return true;
  if (t.length > 36) return true;
  const parts = t.split(/\s+/).filter(Boolean);
  if (parts.length !== 2) return true;
  if (isVowellessTitle(t)) return true;
  // Old Title Case titles should be lowercased
  if (/[A-Z]/.test(t)) return true;
  return false;
}

function applyThreadTitle(thread, next) {
  let title = mumblzTitle(String(next || "").trim());
  // Never keep old vowel-stripped labels.
  if (isVowellessTitle(title)) return false;
  if (!thread || !title) return false;
  if (title === thread.title) return false;
  thread.title = title;
  thread.updatedAt = Date.now();
  renderThreadList();
  if (thread.id === activeId) renderTokexPanel(thread);
  saveStore();
  return true;
}

async function refreshThreadTitle(thread, { useLlm = false } = {}) {
  if (!thread) return;
  const messages = (thread.messages || [])
    .filter((m) => m.role === "user" || m.role === "assistant")
    .filter((m) => m.content && m.content !== WELCOME)
    .map((m) => ({ role: m.role, content: String(m.content || "").slice(0, 2000) }));
  if (messages.length < 2) return;

  // Always set a clear local 2-word title first (never vowelless).
  applyThreadTitle(thread, interpretTitleLocal(messages));

  // Optional LLM polish only — reject vowelless server responses (stale daemon).
  if (!useLlm) return;

  try {
    const res = await fetch("/mumblz", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, use_llm: true }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.title && !isVowellessTitle(data.title)) {
      applyThreadTitle(thread, data.title);
    }
  } catch {
    // local title already applied
  }
}

async function retitleAllThreads({ force = false } = {}) {
  const rev = localStorage.getItem("tokenish.mumblz.rev");
  const mustForce = force || rev !== MUMBLZ_REV;
  for (const th of threads) {
    const msgs = (th.messages || []).filter(
      (m) => (m.role === "user" || m.role === "assistant") && m.content && m.content !== WELCOME,
    );
    if (msgs.length < 2) continue;
    if (!mustForce && !looksProvisionalTitle(th.title)) continue;
    // Wipe vowelless / provisional title so apply always writes the new one.
    if (isVowellessTitle(th.title) || looksProvisionalTitle(th.title)) {
      th.title = "new chat";
    }
    await refreshThreadTitle(th, { useLlm: false });
  }
  localStorage.setItem("tokenish.mumblz.rev", MUMBLZ_REV);
  saveStore();
  renderThreadList();
}

function formatThreadWhen(ts) {
  try {
    return new Date(ts || Date.now()).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function closeAllThreadMenus() {
  document.querySelectorAll(".thread-menu.open").forEach((el) => el.classList.remove("open"));
}

function setHistoryOpen(open) {
  const list = threadListEl;
  const btn = document.getElementById("historyToggle");
  if (!list || !btn) return;
  list.classList.toggle("open", open);
  list.hidden = !open;
  btn.setAttribute("aria-expanded", open ? "true" : "false");
}

function renderThreadList() {
  closeAllThreadMenus();
  const sorted = [...threads].sort((a, b) => b.updatedAt - a.updatedAt);
  threadListEl.innerHTML = "";
  for (const th of sorted) {
    const row = document.createElement("div");
    row.className = `thread-item${th.id === activeId ? " active" : ""}`;
    row.innerHTML =
      `<span class="title">${escapeHtml(th.title)}</span>` +
      `<div class="thread-actions">` +
      `<button class="menu-btn" type="button" title="more" aria-label="more">⋮</button>` +
      `<div class="thread-menu">` +
      `<div class="thread-when">${escapeHtml(formatThreadWhen(th.updatedAt))}</div>` +
      `<button class="thread-del" type="button">Delete</button>` +
      `</div></div>`;
    row.querySelector(".title").onclick = () => selectThread(th.id);
    const menuBtn = row.querySelector(".menu-btn");
    const menu = row.querySelector(".thread-menu");
    menuBtn.onclick = (e) => {
      e.stopPropagation();
      const wasOpen = menu.classList.contains("open");
      closeAllThreadMenus();
      closeAllTokexDetailMenus();
      if (!wasOpen) menu.classList.add("open");
    };
    row.querySelector(".thread-del").onclick = (e) => {
      e.stopPropagation();
      closeAllThreadMenus();
      deleteThread(th.id);
    };
    threadListEl.appendChild(row);
  }
}

function renderMessages(thread) {
  messagesEl.innerHTML = "";
  for (const m of thread.messages || []) {
    if (m.content === WELCOME) continue; // PDF empty-state uses centered hero, not this bubble
    addBubble(m.role, m.content, m.attachments);
  }
  renderTokexPanel(thread);
  syncChatEmptyState(thread);
}

function isChatEmpty(thread) {
  const msgs = (thread && thread.messages) || [];
  if (!msgs.length) return true;
  return msgs.every((m) => m.content === WELCOME);
}

function syncChatEmptyState(thread) {
  const empty = isChatEmpty(thread);
  const shell = document.getElementById("appShell");
  const hero = document.getElementById("welcomeHero");
  const chips = document.getElementById("uploadChips");
  shell?.classList.toggle("chat-empty", empty);
  if (hero) hero.hidden = !empty;
  if (messagesEl) messagesEl.hidden = empty;
  if (chips) chips.hidden = !empty;
}

function selectThread(id) {
  const th = threads.find((t) => t.id === id);
  if (!th) return;
  activeId = id;
  files = [];
  renderAttachments();
  renderMessages(th);
  renderThreadList();
  saveStore();
}

function createChat() {
  const th = newThread();
  threads.unshift(th);
  activeId = th.id;
  files = [];
  renderAttachments();
  renderMessages(th); // keeps lifetime TOKEX panel — does not reset
  renderThreadList();
  saveStore();
  promptEl.focus();
}

function deleteThread(id) {
  threads = threads.filter((t) => t.id !== id);
  // Keep lifetime totals even if a chat is deleted (history of savings stays).
  if (!threads.length) {
    const th = newThread();
    threads = [th];
    activeId = th.id;
    renderMessages(th);
    renderThreadList();
    saveStore();
    return;
  }
  if (activeId === id) {
    selectThread(threads[0].id);
  } else {
    renderThreadList();
    saveStore();
  }
}

function apiHistory(thread) {
  return (thread.messages || [])
    .filter((m) => m.role === "user" || m.role === "assistant")
    .filter((m) => m.content !== WELCOME)
    .map((m) => ({ role: m.role, content: m.content }));
}

function healthForProvider(name) {
  if (!name || name === "auto") return { usable: true, reason: "ok", hint: "", detail: "" };
  return providerHealth[name] || { usable: true, reason: "ok", hint: "", detail: "" };
}

function healthForModel(model) {
  const p = PROVIDER_BY_MODEL[model];
  return healthForProvider(p);
}

function reasonSuffix(reason) {
  if (reason === "quota") return " · check back soon";
  if (reason === "missing_key") return " · link a key";
  if (reason === "no_credits") return " · add credits";
  if (reason === "error") return " · check back soon";
  return "";
}

function setSlotStatus(el, hint, reason) {
  if (!el) return;
  if (!hint) {
    el.hidden = true;
    el.textContent = "";
    el.classList.remove("warn");
    return;
  }
  el.hidden = false;
  el.textContent = hint;
  el.classList.toggle("warn", reason !== "ok" && reason !== "missing_key");
}

function paintProviderOptions() {
  if (!providerSelect) return;
  const current = providerSelect.value;
  for (const opt of providerSelect.options) {
    const key = opt.value;
    const base = PROVIDER_OPTION_LABELS[key] || key;
    if (key === "auto") {
      opt.textContent = base;
      opt.classList.remove("degraded");
      continue;
    }
    const h = healthForProvider(key);
    opt.textContent = base + reasonSuffix(h.reason);
    opt.classList.toggle("degraded", h.reason !== "ok");
  }
  if ([...providerSelect.options].some((o) => o.value === current)) {
    providerSelect.value = current;
  }
}

function applyAvailabilityUI() {
  paintProviderOptions();
  const conn = providerSelect?.value || "auto";
  const model = modelSelect?.value || "";
  const connHealth = healthForProvider(conn);
  const modelOwner = conn === "auto" ? (PROVIDER_BY_MODEL[model] || "") : conn;
  const modelHealth = healthForProvider(modelOwner);

  providerSelect?.classList.toggle("degraded", conn !== "auto" && connHealth.reason !== "ok");
  modelSelect?.classList.toggle("degraded", modelHealth.reason !== "ok");

  if (conn !== "auto") {
    setSlotStatus(
      document.getElementById("connectionStatus"),
      connHealth.reason !== "ok" ? (connHealth.hint || "check back soon") : "",
      connHealth.reason
    );
    setSlotStatus(document.getElementById("modelStatus"), "", "ok");
  } else {
    setSlotStatus(document.getElementById("connectionStatus"), "", "ok");
    setSlotStatus(
      document.getElementById("modelStatus"),
      modelHealth.reason !== "ok" ? (modelHealth.hint || "check back soon") : "",
      modelHealth.reason
    );
  }
  updateSlotDots();
}

function fillModels(models, preferred, { forcePreferred = false } = {}) {
  const provider = providerSelect?.value || "auto";
  const fromProvider = MODELS_BY_PROVIDER[provider] || DEFAULT_MODELS;
  const current = modelSelect.value;
  const filtered = (models || []).filter(
    (m) => m === "gemini-3.5-flash" || m.startsWith("openrouter") || !String(m).startsWith("gemini")
  );
  const pool = provider === "auto"
    ? [...fromProvider, ...(filtered || [])]
    : fromProvider;
  const uniq = [...new Set(pool.filter(Boolean))];

  let pick;
  if (provider === "auto") {
    // Prefer live route override; otherwise always the auto-stack head among linked keys.
    pick = forcePreferred && preferred ? preferred : pickAutoPreferredModel();
  } else if (forcePreferred) {
    pick = preferred || uniq[0];
  } else {
    pick = preferred || current || uniq[0] || "gemini-3.5-flash";
  }
  if (provider === "gemini" || (String(pick).startsWith("gemini") && pick !== "gemini-3.5-flash")) {
    if (provider === "gemini") pick = "gemini-3.5-flash";
    else if (String(pick).startsWith("gemini") && pick !== "gemini-3.5-flash") pick = "gemini-3.5-flash";
  }

  if (provider === "auto") {
    // Lock: only show the chosen model; dropdown disabled so user can't override.
    const owner = PROVIDER_BY_MODEL[pick] || "";
    const h = healthForProvider(owner);
    const label = `${pick}${reasonSuffix(h.reason)} · auto`;
    modelSelect.innerHTML = `<option value="${escapeHtml(pick)}">${escapeHtml(label)}</option>`;
    modelSelect.value = pick;
    modelSelect.disabled = true;
    modelSelect.classList.add("auto-locked");
    modelSelect.title = "auto chooses the model — switch connection off auto to pick your own";
  } else {
    modelSelect.disabled = false;
    modelSelect.classList.remove("auto-locked");
    modelSelect.title = "";
    modelSelect.innerHTML = uniq.map((m) => {
      const h = healthForProvider(provider);
      const label = escapeHtml(m) + escapeHtml(reasonSuffix(h.reason));
      const deg = h.reason !== "ok" ? " degraded" : "";
      return `<option class="${deg.trim()}" value="${escapeHtml(m)}">${label}</option>`;
    }).join("");
    if ([...modelSelect.options].some((o) => o.value === pick)) {
      modelSelect.value = pick;
    } else if (modelSelect.options.length) {
      modelSelect.selectedIndex = 0;
    }
  }

  const hint = document.getElementById("autoModelHint");
  if (hint) {
    hint.hidden = provider !== "auto";
    if (provider === "auto") {
      const owner = PROVIDER_BY_MODEL[modelSelect.value] || "?";
      hint.textContent = `auto locked · ${owner} / ${modelSelect.value}`;
    }
  }
  applyAvailabilityUI();
}

function updateSlotDots() {
  const connDot = document.getElementById("connectionDot");
  const modelDot = document.getElementById("modelDot");
  const hasAny = Object.values(linkedKeysStatus).some(Boolean);
  const connectionOn = hasAny && !!providerSelect?.value;
  const modelOn = connectionOn && !!modelSelect?.value;
  const conn = providerSelect?.value || "auto";
  const connOk = conn === "auto" || healthForProvider(conn).usable;
  const modelOk = healthForModel(modelSelect?.value).usable || (conn !== "auto" && connOk);
  connDot?.classList.toggle("active", connectionOn && connOk);
  modelDot?.classList.toggle("active", modelOn && (conn === "auto" ? modelOk : connOk));
}

async function saveKeys(payload) {
  const res = await fetch("/settings/keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || (await res.text()) || "save failed");
  return data;
}

async function loadProviders(force = false) {
  try {
    const res = await fetch(force ? "/providers?force=1" : "/providers", { cache: "no-store" });
    const data = await res.json();
    providersEl.innerHTML = "";
    const modelSet = [];
    const nextHealth = {};
    for (const p of data.providers || []) {
      let reason = p.reason || "";
      let hint = p.hint || "";
      const detailL = String(p.detail || "").toLowerCase();
      if (!reason) {
        if (p.usable === false || p.available === false) {
          if (/quota|429|rate/.test(detailL)) reason = "quota";
          else if (/credit|license/.test(detailL)) reason = "no_credits";
          else if (/no key|missing/.test(detailL)) reason = "missing_key";
          else reason = "error";
        } else if (/quota|429|out of calls/.test(detailL)) {
          reason = "quota";
        } else {
          reason = "ok";
        }
      }
      if (!hint) {
        if (reason === "quota") hint = "out of calls — check back soon";
        else if (reason === "missing_key") hint = "link a key in manage connections";
        else if (reason === "no_credits") hint = "add credits on the provider site";
        else if (reason === "error") hint = "check back soon";
      }
      nextHealth[p.name] = {
        usable: reason === "ok",
        reason,
        hint,
        detail: p.detail || "",
      };
      const row = document.createElement("div");
      row.className = "provider" + (reason === "ok" ? "" : " degraded");
      const hasKey = reason !== "missing_key";
      const linkedNote = hasKey ? " · linked" : "";
      const right = escapeHtml(hint || p.detail || "");
      row.innerHTML = `<span><span class="dot ${reason === "ok" ? "ok" : "bad"}"></span>${p.name}${linkedNote}</span><span style="color:var(--muted);font-size:0.75rem">${right}</span>`;
      providersEl.appendChild(row);
      (p.models || []).forEach((m) => modelSet.push(m));
    }
    providerHealth = nextHealth;
    // Secondary sync: Argus inventory keeps popup greying current even if keys endpoint lagged.
    if (data.linked_keys?.has) {
      fillKeyWizard({ has: data.linked_keys.has, prefs: {} });
    }
    const pref = data.preferred;
    fillModels(modelSet, pref?.model);
    // Do NOT force connection back to auto — that silently ignored the user's pick.
    applyAvailabilityUI();
  } catch {
    showError("engine offline — restart tokenish");
    fillModels(DEFAULT_MODELS);
  }
}

async function send() {
  const thread = activeThread();
  if (!thread) return;
  const prompt = promptEl.value.trim() || (files.length ? "(attachment only)" : "");
  if (!prompt && !files.length) return;
  showError("");

  const preGate = assessMaterialSuitability(files, prompt);
  if (!preGate.ok) {
    publishGrettaNote(preGate.note, { blocked: true });
    showError("send blocked — material not suitable for Tokenish (fidelity risk)");
    return;
  }
  materialBlocked = false;

  if (thread.messages.length === 1 && thread.messages[0].content === WELCOME) {
    thread.title = titleFromPrompt(prompt);
  }

  const uploaded = await snapshotAttachments(files);
  addBubble("user", prompt, uploaded);
  thread.messages.push({ role: "user", content: prompt, attachments: uploaded });
  thread.updatedAt = Date.now();
  promptEl.value = "";
  renderThreadList();
  saveStore();

  const fd = new FormData();
  fd.append("prompt", prompt);
  const model = modelSelect.value;
  const provider = providerSelect.value;
  fd.append("target_engine", model);
  fd.append("model", model);
  fd.append("provider", provider);
  fd.append("history", JSON.stringify(apiHistory(thread).slice(0, -1)));
  fd.append("stream", "true");
  fd.append("enable_its", document.getElementById("allowIts")?.checked ? "true" : "false");
  const pageRange = document.getElementById("pageRange").value.trim();
  if (pageRange) fd.append("page_range", pageRange);
  for (const f of files) fd.append("files", f);

  // Clear composer chips once they've been stamped into the chat turn.
  files = [];
  fileInput.value = "";
  renderAttachments();

  const loader = makeTknshLoader();
  let bubble = null;
  let assistant = "";
  let usedProv = provider;
  let usedMdl = model;
  let tokexSnap = null;

  try {
    const res = await fetch("/chat", { method: "POST", body: fd });
    if (!res.ok || !res.body) throw new Error(await res.text());
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        let evt;
        try { evt = JSON.parse(line); } catch { continue; }
        if (evt.type === "meta") {
          accumulateTokex(thread, evt.tokex || evt.meter);
          tokexSnap = evt.tokex || evt.meter || tokexSnap;
          renderTokexPanel(thread);
          saveStore();
          if (evt.attachment_warning) showError(evt.attachment_warning);
          if (evt.provider) usedProv = evt.provider;
          if (evt.model) usedMdl = evt.model;
          if (evt.provider || evt.model) {
            const who = `${evt.provider || "?"} / ${evt.model || "?"}`;
            showError(`answering with ${who}`);
            // Reflect live auto pick in the Models dropdown immediately.
            if (providerSelect?.value === "auto" && evt.model) {
              fillModels(MODELS_BY_PROVIDER.auto, evt.model, { forcePreferred: true });
            }
          }
        } else if (evt.type === "routing") {
          if (evt.provider) usedProv = evt.provider;
          if (evt.model) usedMdl = evt.model;
          const who = `${evt.provider || "?"} / ${evt.model || "?"}`;
          const why = evt.fallback_reason ? ` — ${evt.fallback_reason}` : "";
          showError(`switched to ${who}${why}`);
          if (providerSelect?.value === "auto" && evt.model) {
            fillModels(MODELS_BY_PROVIDER.auto, evt.model, { forcePreferred: true });
          }
        } else if (evt.type === "delta") {
          if (!bubble) {
            loader.remove();
            bubble = addBubble("assistant", "");
          }
          assistant += evt.text || "";
          bubble.querySelector(".body").innerHTML = formatReply(assistant);
          messagesEl.scrollTop = messagesEl.scrollHeight;
        } else if (evt.type === "error") {
          throw new Error(evt.error || "chat failed");
        }
      }
    }
    if (!assistant) throw new Error("empty reply — try another model or OpenRouter key");
    const stamp = formatReplyStamp(usedProv, usedMdl, tokexSnap || thread.tokex?.last);
    const stamped = `${assistant}\n\n${stamp}`;
    if (bubble) bubble.querySelector(".body").innerHTML = formatReply(stamped);
    thread.messages.push({ role: "assistant", content: stamped });
    thread.updatedAt = Date.now();
    renderThreadList();
    saveStore();
    // Mumblz: instant local 2-word title, then optional LLM polish.
    await refreshThreadTitle(thread, { useLlm: false });
    refreshThreadTitle(thread, { useLlm: true });
  } catch (e) {
    loader.remove();
    showError(e.message || String(e));
    if (!bubble) bubble = addBubble("assistant", "");
    const errText = "error: " + (e.message || e);
    const stamp = formatReplyStamp(usedProv, usedMdl, tokexSnap);
    const stamped = `${errText}\n\n${stamp}`;
    bubble.querySelector(".body").innerHTML = formatReply(stamped);
    thread.messages.push({ role: "assistant", content: stamped });
    saveStore();
    loadProviders(true).catch(() => {});
  }
}

document.getElementById("attachBtn").onclick = () => fileInput.click();
document.getElementById("uploadImagesChip")?.addEventListener("click", () => {
  document.getElementById("imageInput")?.click();
});
document.getElementById("uploadVideosChip")?.addEventListener("click", () => {
  document.getElementById("videoInput")?.click();
});
async function onPickedFiles(inputEl) {
  const incoming = Array.from(inputEl?.files || []);
  if (inputEl) inputEl.value = "";
  await stageIncomingFiles(incoming);
}
fileInput.onchange = () => onPickedFiles(fileInput);
document.getElementById("imageInput")?.addEventListener("change", (e) => onPickedFiles(e.target));
document.getElementById("videoInput")?.addEventListener("change", (e) => onPickedFiles(e.target));
document.getElementById("sendBtn").onclick = () => send();
document.getElementById("newChat").onclick = () => createChat();
document.getElementById("historyToggle")?.addEventListener("click", () => {
  const open = document.getElementById("historyToggle")?.getAttribute("aria-expanded") !== "true";
  setHistoryOpen(open);
});

function readSidebarPrefs() {
  try {
    return JSON.parse(localStorage.getItem(SIDEBAR_KEY) || "{}") || {};
  } catch {
    return {};
  }
}
function writeSidebarPrefs(next) {
  localStorage.setItem(SIDEBAR_KEY, JSON.stringify(next));
}
function isNarrowChrome() {
  return window.matchMedia("(max-width: 1100px)").matches;
}
function syncSidebarScrim() {
  const shell = document.getElementById("appShell");
  const scrim = document.getElementById("sidebarScrim");
  if (!shell || !scrim) return;
  const show = isNarrowChrome() && (shell.classList.contains("left-open") || shell.classList.contains("right-open"));
  scrim.hidden = !show;
}
function setSidebarOpen(side, open) {
  const shell = document.getElementById("appShell");
  if (!shell) return;
  const cls = side === "left" ? "left-open" : "right-open";
  shell.classList.toggle(cls, !!open);
  const btn = document.getElementById(side === "left" ? "toggleLeftSidebar" : "toggleRightSidebar");
  if (btn) {
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    const label = side === "left" ? "history" : "models";
    btn.title = open ? `Hide ${label} sidebar` : `Show ${label} sidebar`;
  }
  const prefs = readSidebarPrefs();
  prefs[side] = !!open;
  writeSidebarPrefs(prefs);
  syncSidebarScrim();
}
function initSidebars() {
  const prefs = readSidebarPrefs();
  const narrow = isNarrowChrome();
  // PDF: left open like ChatGPT; models drawer closed until needed.
  const left = typeof prefs.left === "boolean" ? prefs.left : !narrow;
  const right = typeof prefs.right === "boolean" ? prefs.right : false;
  setSidebarOpen("left", left);
  setSidebarOpen("right", right);
  setHistoryOpen(true);
}
document.getElementById("toggleLeftSidebar")?.addEventListener("click", () => {
  const shell = document.getElementById("appShell");
  const open = !shell?.classList.contains("left-open");
  if (open && isNarrowChrome()) setSidebarOpen("right", false);
  setSidebarOpen("left", open);
});
document.getElementById("toggleRightSidebar")?.addEventListener("click", () => {
  const shell = document.getElementById("appShell");
  const open = !shell?.classList.contains("right-open");
  if (open && isNarrowChrome()) setSidebarOpen("left", false);
  setSidebarOpen("right", open);
});
document.getElementById("sidebarScrim")?.addEventListener("click", () => {
  setSidebarOpen("left", false);
  setSidebarOpen("right", false);
});
window.addEventListener("resize", () => syncSidebarScrim());
document.getElementById("engineToggle")?.addEventListener("click", () => {
  const btn = document.getElementById("engineToggle");
  const menu = document.getElementById("engineMenu");
  if (!btn || !menu) return;
  const open = btn.getAttribute("aria-expanded") !== "true";
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  menu.hidden = !open;
  menu.classList.toggle("open", open);
});
document.getElementById("cylindersToggle")?.addEventListener("click", (e) => {
  e.stopPropagation();
  const btn = document.getElementById("cylindersToggle");
  const menu = document.getElementById("cylindersMenu");
  if (!btn || !menu) return;
  const open = btn.getAttribute("aria-expanded") !== "true";
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  menu.hidden = !open;
  menu.classList.toggle("open", open);
});
document.querySelectorAll(".engine-sublink[data-cylinder]").forEach((btn) => {
  btn.addEventListener("click", () => {
    /* Name list only for now — detail panels in a future session. */
  });
});
document.getElementById("openResgents")?.addEventListener("click", () => {
  /* Label only — details via ⋮ */
});
document.getElementById("openMiddleware")?.addEventListener("click", () => {
  /* Label only — details via ⋮ */
});
document.querySelectorAll(".engine-help-btn").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const key = btn.getAttribute("data-help");
    const menu = document.getElementById(`help-${key}`);
    const wasOpen = menu?.classList.contains("open");
    document.querySelectorAll(".engine-help-menu.open").forEach((el) => el.classList.remove("open"));
    closeAllTokexDetailMenus();
    closeAllThreadMenus();
    document.querySelectorAll(".slot-help-menu.open").forEach((el) => el.classList.remove("open"));
    if (menu && !wasOpen) menu.classList.add("open");
  });
});
document.querySelectorAll(".engine-help-menu").forEach((menu) => {
  menu.addEventListener("click", (e) => e.stopPropagation());
});
document.getElementById("upgradeTokish")?.addEventListener("click", () => {
  showInfo("TOKISH = free tokenish + Nemean Privacy Middleware (local default · Azure-direct optional · zero prompt proxy). License chooser lands next.");
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (isNarrowChrome()) {
      setSidebarOpen("left", false);
      setSidebarOpen("right", false);
    }
  }
  if (e.ctrlKey && e.shiftKey && (e.key === "O" || e.key === "o")) {
    e.preventDefault();
    createChat();
  }
});
initSidebars();
document.querySelectorAll(".tokex-details-btn").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const menu = btn.parentElement.querySelector(".tokex-details-menu");
    const wasOpen = menu.classList.contains("open");
    closeAllThreadMenus();
    closeAllTokexDetailMenus();
    if (!wasOpen) menu.classList.add("open");
  });
});
document.querySelectorAll(".tokex-details-menu").forEach((menu) => {
  menu.addEventListener("click", (e) => e.stopPropagation());
});
document.addEventListener("click", () => {
  closeAllThreadMenus();
  closeAllTokexDetailMenus();
  document.querySelectorAll(".engine-help-menu.open").forEach((el) => el.classList.remove("open"));
});
promptEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

async function refreshLinkedApiSlots() {
  /** Always re-read which APIs are already linked (launch / reopen / post-save). */
  try {
    const res = await fetch("/settings/keys", { cache: "no-store" });
    const data = await res.json();
    fillKeyWizard(data);
    return data;
  } catch {
    return null;
  }
}

async function maybeShowKeyWizard(force = false) {
  const modal = document.getElementById("keyModal");
  if (!modal) return;
  const data = await refreshLinkedApiSlots();
  if (!force && data?.prefs?.hide_key_wizard) return;
  modal.hidden = false;
}

function loadAuth() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY) || "null");
  } catch {
    return null;
  }
}

function saveAuth(user) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(user));
}

function showModal(id, on) {
  const el = document.getElementById(id);
  if (el) el.hidden = !on;
}

function hideAllLaunchModals() {
  ["grettaModal", "authModal", "grettaApiModal", "grettaNeedModal"].forEach((id) =>
    showModal(id, false),
  );
  const keyModal = document.getElementById("keyModal");
  if (keyModal) keyModal.hidden = true;
}

function setGrettaFlow(step) {
  sessionStorage.setItem(GRETTA_FLOW, step);
}

function getGrettaFlow() {
  return sessionStorage.getItem(GRETTA_FLOW) || "";
}

async function startLaunchFlow() {
  // Session-only gate. New window/tab = empty sessionStorage → always Hi I'm Gretta first.
  // Never auto-open the key/API list just because localStorage has old "onboard done" flags.
  hideAllLaunchModals();

  const step = getGrettaFlow();
  if (!step || step === "intro") {
    setGrettaFlow("intro");
    showModal("grettaModal", true);
    return;
  }
  if (step === "auth") {
    showModal("authModal", true);
    return;
  }
  if (step === "api") {
    showModal("grettaApiModal", true);
    return;
  }
  if (step === "keys") {
    await maybeShowKeyWizard(true);
    return;
  }
  if (step === "need") {
    showGrettaNeedModal();
    return;
  }
  // step === "done" → no launch popups
}

document.getElementById("grettaStart")?.addEventListener("click", () => {
  sessionStorage.setItem(GRETTA_INTRO_KEY, "1");
  setGrettaFlow("auth");
  showModal("grettaModal", false);
  showModal("authModal", true);
});

document.getElementById("grettaSkipIntro")?.addEventListener("click", () => {
  sessionStorage.setItem(GRETTA_INTRO_KEY, "1");
  setGrettaFlow("auth");
  showModal("grettaModal", false);
  showModal("authModal", true);
});

function finishAuth(user) {
  saveAuth(user);
  setGrettaFlow("api");
  showModal("authModal", false);
  showModal("grettaApiModal", true);
}

document.getElementById("authSkip")?.addEventListener("click", () => {
  sessionStorage.setItem(GRETTA_INTRO_KEY, "1");
  setGrettaFlow("api");
  showModal("authModal", false);
  showModal("grettaApiModal", true);
});

document.getElementById("authContinue")?.addEventListener("click", () => {
  const email = document.getElementById("authEmail")?.value.trim() || "";
  const password = document.getElementById("authPassword")?.value || "";
  const msg = document.getElementById("authModalMsg");
  if (!email || !email.includes("@") || password.length < 4) {
    if (msg) {
      msg.hidden = false;
      msg.textContent = "use a real email and a password (4+ characters).";
    }
    return;
  }
  if (msg) msg.hidden = true;
  finishAuth({ email, provider: "email", at: Date.now() });
});

document.getElementById("authGoogle")?.addEventListener("click", () => {
  // Local demo session until real OAuth client IDs are configured.
  finishAuth({ email: "google-user@local", provider: "google-local", at: Date.now() });
});
document.getElementById("authFacebook")?.addEventListener("click", () => {
  finishAuth({ email: "facebook-user@local", provider: "facebook-local", at: Date.now() });
});

document.getElementById("grettaNextKeys")?.addEventListener("click", async () => {
  sessionStorage.setItem(GRETTA_SEEN_KEY, "1");
  setGrettaFlow("keys");
  showModal("grettaApiModal", false);
  await maybeShowKeyWizard(true);
});

document.getElementById("grettaSkipApi")?.addEventListener("click", () => {
  sessionStorage.setItem(GRETTA_SEEN_KEY, "1");
  setGrettaFlow("need");
  showModal("grettaApiModal", false);
  showGrettaNeedModal();
});

function loadGrettaPick() {
  try {
    return JSON.parse(localStorage.getItem(GRETTA_PICK_KEY) || "null");
  } catch {
    return null;
  }
}

function saveGrettaPick(pick) {
  localStorage.setItem(GRETTA_PICK_KEY, JSON.stringify(pick));
  renderGrettaSlotStatus(pick);
}

function renderGrettaSlotStatus(pick) {
  const el = document.getElementById("grettaSlotStatus");
  if (!el) return;
  if (!pick?.note) {
    el.textContent = "tell Gretta what you want done, or upload material";
    return;
  }
  el.textContent = pick.note;
}

function grettaRecommendLocal(need) {
  const text = String(need || "").toLowerCase();
  const map = [
    { provider: "openai", model: "gpt-4o", keys: ["logo", "brand", "design", "creative", "image gen", "illustrat", "artwork", "company logo", "code", "plan", "brainstorm", "json"], blurb: "ChatGPT gpt-4o — strong for creative briefs and design work" },
    { provider: "anthropic", model: "claude-sonnet-4-20250514", keys: ["summar", "legal", "contract", "assess", "rewrite", "edit", "essay", "careful"], blurb: "Claude Sonnet — strong at careful writing and rewrites" },
    { provider: "gemini", model: "gemini-3.5-flash", keys: ["document", "pdf", "explain", "search", "general", "photo"], blurb: "gemini-3.5-flash — fast everyday helper with live-web access" },
    { provider: "perplexity", model: "sonar", keys: ["news", "current", "today", "market", "research"], blurb: "Perplexity sonar — strong at fresh web-backed answers" },
    { provider: "groq", model: "llama-3.3-70b-versatile", keys: ["fast", "quick", "speed"], blurb: "Groq llama-3.3-70b — very fast answers when speed matters" },
    { provider: "openrouter", model: "openrouter/free", keys: ["free", "try", "budget"], blurb: "OpenRouter free models — when you just want to try" },
    { provider: "grok", model: "grok-3", keys: ["twitter", "humor", "opinion"], blurb: "grok-3 — more conversational takes" },
  ];
  const scored = map
    .map((row) => ({
      ...row,
      score: row.keys.reduce((n, k) => n + (text.includes(k) ? 1 : 0), 0),
      isLinked: !!linkedKeysStatus[row.provider],
    }))
    .sort((a, b) => b.score - a.score);
  const ideal = scored[0];
  const linkedPool = scored.filter((r) => r.isLinked);
  let best = linkedPool[0] || scored.find((r) => r.provider === "gemini") || ideal;
  let note;
  if (ideal && ideal.provider !== best.provider && ideal.score > 0) {
    note = `Ok — ${ideal.provider} fits that need best. It’s not linked here, so we lined up ${best.provider} (${best.blurb}).`;
  } else {
    note = `Ok — ${best.provider} is lined up for you (${best.blurb}).`;
  }
  return {
    agent: "Gretta",
    note,
    selected: {
      provider: best.provider,
      model: best.model,
      blurb: best.blurb,
      linked: !!linkedKeysStatus[best.provider],
    },
  };
}

function applyGrettaSelection(data) {
  saveGrettaPick(data);
  const sel = data?.selected || {};
  if (sel.provider && [...(providerSelect?.options || [])].some((o) => o.value === sel.provider)) {
    providerSelect.value = sel.provider;
    fillModels(MODELS_BY_PROVIDER[sel.provider] || DEFAULT_MODELS, sel.model);
  }
  updateSlotDots();
}

async function resolveGrettaNeed(need) {
  let data = null;
  try {
    const res = await fetch("/gretta/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ need }),
    });
    const raw = await res.text();
    try {
      data = JSON.parse(raw);
    } catch {
      data = null;
    }
    if (!res.ok || !data?.note) data = grettaRecommendLocal(need);
  } catch {
    data = grettaRecommendLocal(need);
  }
  applyGrettaSelection(data);
  return data;
}

function showGrettaNeedModal() {
  const input = document.getElementById("grettaNeedInput");
  const msg = document.getElementById("grettaNeedMsg");
  if (input) input.value = "";
  if (msg) msg.hidden = true;
  showModal("grettaNeedModal", true);
}

async function askGretta() {
  const need = document.getElementById("grettaAsk")?.value.trim() || "";
  const status = document.getElementById("grettaSlotStatus");
  if (!need) {
    if (status) status.textContent = "tell Gretta what you want done, or upload material.";
    return;
  }
  if (status) status.textContent = "Gretta is checking suitability…";
  const gate = assessMaterialSuitability(files, need);
  if (!gate.ok) {
    publishGrettaNote(gate.note, { blocked: true });
    return;
  }
  if (status) status.textContent = "Gretta is lining up a fit…";
  const data = await resolveGrettaNeed(need);
  publishGrettaNote(gate.note || data?.note || "lined up.", { blocked: false });
}

document.getElementById("grettaAskBtn")?.addEventListener("click", askGretta);

document.getElementById("grettaNeedGo")?.addEventListener("click", async () => {
  const need = document.getElementById("grettaNeedInput")?.value.trim() || "";
  const msg = document.getElementById("grettaNeedMsg");
  if (!need) {
    if (msg) {
      msg.hidden = false;
      msg.className = "error";
      msg.textContent = "tell Gretta what you want done, or hit got it and upload material.";
    }
    return;
  }
  if (msg) {
    msg.hidden = false;
    msg.className = "modal-lead";
    msg.textContent = "checking suitability + lining up a linked AI…";
  }
  await refreshLinkedApiSlots();
  const gate = assessMaterialSuitability(files, need);
  if (!gate.ok) {
    showModal("grettaNeedModal", false);
    setGrettaFlow("done");
    publishGrettaNote(gate.note, { blocked: true });
    const slotAsk = document.getElementById("grettaAsk");
    if (slotAsk) slotAsk.value = need;
    return;
  }
  const data = await resolveGrettaNeed(need);
  showModal("grettaNeedModal", false);
  setGrettaFlow("done");
  publishGrettaNote(gate.note || data?.note || "lined up.", { blocked: false });
  const slotAsk = document.getElementById("grettaAsk");
  if (slotAsk) slotAsk.value = need;
});

document.getElementById("grettaNeedSkip")?.addEventListener("click", () => {
  showModal("grettaNeedModal", false);
  setGrettaFlow("done");
  publishGrettaNote("Thx for the API setup! Upload ur material so I can see if we can help.", { blocked: false });
});

function fitTextToWidth(el, targetPx) {
  if (!el || !(targetPx > 0)) return;
  el.style.letterSpacing = "0px";
  el.style.transform = "";
  el.style.width = "max-content";
  const natural = el.getBoundingClientRect().width;
  const text = (el.textContent || "").replace(/\s+/g, " ").trim();
  const gaps = Math.max(text.length - 1, 1);
  const delta = targetPx - natural;
  if (Math.abs(delta) < 0.5) return;
  if (delta > 0) {
    el.style.letterSpacing = `${delta / gaps}px`;
  } else {
    el.style.transformOrigin = "left center";
    el.style.transform = `scaleX(${targetPx / natural})`;
  }
}

function fitBrandLines() {
  const row = document.querySelector(".brand-title-row");
  const rule = document.querySelector(".brand-rule");
  if (!row || !rule) return;
  rule.style.width = `${row.getBoundingClientRect().width}px`;
}

function applyLinkedStatus(hasMap) {
  linkedKeysStatus = {
    gemini: !!hasMap?.gemini,
    openrouter: !!hasMap?.openrouter,
    openai: !!hasMap?.openai,
    anthropic: !!hasMap?.anthropic,
    perplexity: !!hasMap?.perplexity,
    groq: !!hasMap?.groq,
    grok: !!hasMap?.grok,
  };
}

function fillKeyWizard(data) {
  // Support nested `has`, Argus `linked_keys.has`, and top-level booleans.
  let src = null;
  if (data?.has && typeof data.has === "object") src = data.has;
  else if (data?.linked_keys?.has && typeof data.linked_keys.has === "object") src = data.linked_keys.has;
  else src = data || {};
  applyLinkedStatus(src);

  const defaults = {
    keyGemini: "paste gemini key here",
    keyOpenRouter: "paste openrouter key here",
    keyOpenAI: "paste chatgpt/openai key here",
    keyAnthropic: "paste claude key here",
    keyPerplexity: "paste perplexity key here",
    keyGroq: "paste groq key here",
    keyGrok: "paste grok / xAI key here",
  };
  const map = {
    keyGemini: "gemini",
    keyOpenRouter: "openrouter",
    keyOpenAI: "openai",
    keyAnthropic: "anthropic",
    keyPerplexity: "perplexity",
    keyGroq: "groq",
    keyGrok: "grok",
  };
  for (const [id, slot] of Object.entries(map)) {
    const present = !!linkedKeysStatus[slot];
    const el = document.getElementById(id);
    const wrap = document.querySelector(`.key-slot[data-slot="${slot}"]`);
    if (el) {
      el.value = "";
      el.placeholder = present
        ? "••••••••  already linked — click & paste to replace"
        : defaults[id];
      el.classList.toggle("key-linked-input", present);
      el.disabled = false;
      el.readOnly = !!present;
      el.onfocus = present
        ? () => { el.readOnly = false; el.placeholder = defaults[id]; }
        : null;
    }
    if (wrap) {
      wrap.classList.toggle("linked-slot", present);
      wrap.setAttribute("data-linked", present ? "true" : "false");
      const badge = wrap.querySelector(".key-badge.linked");
      if (badge) {
        badge.hidden = !present;
        badge.textContent = "already linked";
      }
      const link = wrap.querySelector(".key-link");
      if (link) {
        link.classList.toggle("needs-key", !present);
      }
    }
  }
  if (data.prefs?.fallback_preference) {
    const pref = document.getElementById("fallbackPref");
    if (pref) pref.value = data.prefs.fallback_preference;
  }
  updateSlotDots();
}

async function handleKeySave(fromModal) {
  const msg = document.getElementById("keyModalMsg");
  const payload = {
    GEMINI_API_KEY: document.getElementById("keyGemini")?.value.trim() || "",
    OPENROUTER_API_KEY: document.getElementById("keyOpenRouter")?.value.trim() || "",
    OPENAI_API_KEY: document.getElementById("keyOpenAI")?.value.trim() || "",
    ANTHROPIC_API_KEY: document.getElementById("keyAnthropic")?.value.trim() || "",
    PERPLEXITY_API_KEY: document.getElementById("keyPerplexity")?.value.trim() || "",
    GROQ_API_KEY: document.getElementById("keyGroq")?.value.trim() || "",
    XAI_API_KEY: document.getElementById("keyGrok")?.value.trim() || "",
    fallback_preference: document.getElementById("fallbackPref")?.value.trim() || "",
    hide_key_wizard: !!document.getElementById("dontShowWizard")?.checked,
  };

  const newKeys = Object.entries(payload).filter(
    ([k, v]) => k.endsWith("_KEY") && !!String(v || "").trim(),
  );
  const hasNew = newKeys.length > 0;
  const hasExisting = Object.values(linkedKeysStatus).some(Boolean);

  // Gemini / OpenRouter are never required. Any new key OR any already-linked provider is enough.
  if (!hasNew && !hasExisting) {
    if (msg) {
      msg.hidden = false;
      msg.textContent = "paste at least one AI key (any provider). Gemini and OpenRouter are optional.";
    }
    showError("paste at least one AI key (any provider)");
    return;
  }

  try {
    const data = await saveKeys(payload);
    // Re-read inventory from disk/env so greying is never based on optimistic merge only.
    await refreshLinkedApiSlots();
    if (fromModal) document.getElementById("keyModal").hidden = true;
    if (msg) msg.hidden = true;
    showError("");
    const th = activeThread();
    if (th) {
      const note = hasNew
        ? `connections saved${data.saved?.length ? ` (${data.saved.join(", ")})` : ""}. you can keep chatting.`
        : "connections kept. you can keep chatting.";
      addBubble("assistant", note);
      th.messages.push({ role: "assistant", content: note });
      saveStore();
    }
    await loadProviders();
    updateSlotDots();
    if (fromModal) {
      setGrettaFlow("need");
      showGrettaNeedModal();
    }
  } catch (e) {
    showError(e.message || String(e));
    if (msg) { msg.hidden = false; msg.textContent = e.message || String(e); }
  }
}

document.getElementById("keySkip")?.addEventListener("click", () => {
  document.getElementById("keyModal").hidden = true;
  setGrettaFlow("need");
  showGrettaNeedModal();
});
document.getElementById("keySave")?.addEventListener("click", () => handleKeySave(true));
document.getElementById("openKeyWizard")?.addEventListener("click", async () => {
  const modal = document.getElementById("keyModal");
  await refreshLinkedApiSlots();
  if (modal) modal.hidden = false;
});
providerSelect?.addEventListener("change", () => {
  const p = providerSelect.value;
  if (p === "auto") {
    fillModels(MODELS_BY_PROVIDER.auto, pickAutoPreferredModel(), { forcePreferred: true });
  } else {
    fillModels(MODELS_BY_PROVIDER[p] || DEFAULT_MODELS);
  }
  applyAvailabilityUI();
});
modelSelect?.addEventListener("change", () => {
  applyAvailabilityUI();
});
document.getElementById("openHiveConnect")?.addEventListener("click", (e) => {
  e.stopPropagation();
  maybeShowHiveConnect(true);
});
document.getElementById("hiveSkip")?.addEventListener("click", () => {
  document.getElementById("hiveModal").hidden = true;
});
document.getElementById("hiveSave")?.addEventListener("click", async () => {
  const msg = document.getElementById("hiveModalMsg");
  try {
    const res = await fetch("/tokex-clock/opt-in", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        hive_opt_in: !!document.getElementById("hiveOptIn")?.checked,
        hive_url: document.getElementById("hiveUrlInput")?.value.trim() || "",
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "could not save");
    document.getElementById("hiveModal").hidden = true;
    if (msg) msg.hidden = true;
    await refreshTokexClock();
  } catch (e) {
    if (msg) {
      msg.hidden = false;
      msg.textContent = e.message || String(e);
    }
  }
});

document.getElementById("addCustomKey")?.addEventListener("click", () => {
  const wrap = document.getElementById("customKeySlots");
  if (!wrap) return;
  const id = `customKey_${Date.now()}`;
  const slot = document.createElement("div");
  slot.className = "key-slot";
  slot.innerHTML =
    `<div class="key-slot-top"><strong>your AI</strong></div>` +
    `<p class="key-hint">Name the provider and paste its key. Advanced — optional.</p>` +
    `<input type="text" placeholder="provider name (e.g. my-llm)" class="custom-prov" />` +
    `<input type="password" id="${id}" placeholder="paste key" autocomplete="off" style="margin-top:6px" />`;
  wrap.appendChild(slot);
});

document.querySelectorAll(".slot-help-btn").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const id = btn.getAttribute("data-help");
    const menu = document.getElementById(`help-${id}`);
    document.querySelectorAll(".slot-help-menu.open").forEach((el) => {
      if (el !== menu) el.classList.remove("open");
    });
    menu?.classList.toggle("open");
  });
});
document.addEventListener("click", () => {
  document.querySelectorAll(".slot-help-menu.open").forEach((el) => el.classList.remove("open"));
  document.querySelectorAll(".engine-help-menu.open").forEach((el) => el.classList.remove("open"));
});

(function init() {
  const stored = loadStore();
  if (stored?.threads?.length) {
    threads = stored.threads.map((t) => ({
      ...t,
      tokex: normalizeTokex(t.tokex),
      messages: t.messages || [{ role: "assistant", content: WELCOME }],
    }));
    lifetime = stored.lifetime
      ? normalizeTokex(stored.lifetime)
      : rebuildLifetimeFromThreads();
  } else {
    threads = [];
    lifetime = emptyTokex();
  }
  // Hard start (new browser session): land on a fresh chat, keep history.
  // Same-tab refresh keeps the current active chat.
  let resumeId = stored?.activeId && threads.some((t) => t.id === stored.activeId)
    ? stored.activeId
    : (threads[0]?.id || null);
  try {
    if (!sessionStorage.getItem(SESSION_BOOT_KEY)) {
      sessionStorage.setItem(SESSION_BOOT_KEY, "1");
      const th = newThread();
      threads.unshift(th);
      resumeId = th.id;
    } else if (!resumeId) {
      const th = newThread();
      threads = [th];
      resumeId = th.id;
    }
  } catch (_) {
    if (!resumeId) {
      const th = newThread();
      threads.unshift(th);
      resumeId = th.id;
    }
  }
  activeId = resumeId;
  saveStore();
  renderThreadList();
  selectThread(activeId);
  fillModels(DEFAULT_MODELS);
  // Launch Gretta flow last so nothing else can steal the first modal.
  refreshLinkedApiSlots().then(() => loadProviders()).then(() => updateSlotDots());
  // Clear bad v2 flag that forced the API key wizard on every window.
  try { localStorage.removeItem("tokenish.gretta.onboard.v2"); } catch (_) {}
  startLaunchFlow();
  renderGrettaSlotStatus(loadGrettaPick());
  tickLiveWorldClock();
  setInterval(tickLiveWorldClock, 1000);
  refreshTokexClock();
  setInterval(refreshTokexClock, 15000);
  maybeShowHiveConnect(false);
  retitleAllThreads({ force: true });
  fitBrandLines();
  window.addEventListener("resize", fitBrandLines);
  if (document.fonts?.ready) document.fonts.ready.then(fitBrandLines);
  const mark = document.querySelector(".brand-wordmark");
  if (mark) mark.addEventListener("load", fitBrandLines);
})();
