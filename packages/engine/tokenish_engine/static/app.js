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

let files = [];
let threads = [];
let activeId = null;
/** Lifetime totals across ALL chats — never reset on new chat. */
let lifetime = emptyTokex();

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
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function formatReply(text) {
  let s = String(text || "");
  s = s.replace(/^#{1,6}\s+/gm, "");
  s = s.replace(/\*\*([^*]+)\*\*/g, "$1");
  s = s.replace(/__([^_]+)__/g, "$1");
  s = s.replace(/\*([^*]+)\*/g, "$1");
  s = s.replace(/^---+$/gm, "");
  s = s.replace(/^>\s?/gm, "");
  return escapeHtml(s);
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

function closeAllTokexDetailMenus() {
  document.querySelectorAll(".tokex-details-menu.open").forEach((el) => el.classList.remove("open"));
}

function renderTokexPanel(thread) {
  lifetime = normalizeTokex(lifetime);
  fillTokexBox(
    "life",
    lifetime,
    lifetime.sends.length
      ? `grand total · ${lifetime.sends.length} send${lifetime.sends.length === 1 ? "" : "s"} · all chats`
      : "grand total · all chats",
  );

  const th = thread || activeThread();
  const chat = normalizeTokex(th?.tokex);
  if (th) th.tokex = chat;
  const title = th?.title ? th.title.slice(0, 36) : "this chat";
  fillTokexBox(
    "chat",
    chat,
    chat.sends.length
      ? `${title} · ${chat.sends.length} send${chat.sends.length === 1 ? "" : "s"}`
      : `${title} · no sends yet`,
  );
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
    addBubble(m.role, m.content, m.attachments);
  }
  renderTokexPanel(thread);
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

function fillModels(models, preferred) {
  const current = modelSelect.value;
  const filtered = (models || []).filter(
    (m) => m === "gemini-3.5-flash" || m.startsWith("openrouter") || !String(m).startsWith("gemini")
  );
  const uniq = [...new Set([...(filtered || []), ...DEFAULT_MODELS].filter(Boolean))];
  modelSelect.innerHTML = uniq.map((m) => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join("");
  let pick = preferred || current || "gemini-3.5-flash";
  if (String(pick).startsWith("gemini") && pick !== "gemini-3.5-flash") {
    pick = "gemini-3.5-flash";
  }
  if ([...modelSelect.options].some((o) => o.value === pick)) {
    modelSelect.value = pick;
  } else if (modelSelect.options.length) {
    modelSelect.selectedIndex = 0;
  }
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

async function loadProviders() {
  try {
    const res = await fetch("/providers");
    const data = await res.json();
    providersEl.innerHTML = "";
    const modelSet = [];
    for (const p of data.providers || []) {
      // show all providers Argus returns
      const row = document.createElement("div");
      row.className = "provider";
      row.innerHTML = `<span><span class="dot ${p.available ? "ok" : "bad"}"></span>${p.name}</span><span style="color:var(--muted);font-size:0.75rem">${escapeHtml(p.detail || "")}</span>`;
      providersEl.appendChild(row);
      (p.models || []).forEach((m) => modelSet.push(m));
    }
    const pref = data.preferred;
    fillModels(modelSet, pref?.model);
    if (pref?.provider && [...providerSelect.options].some((o) => o.value === pref.provider)) {
      providerSelect.value = "auto";
    }
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
          renderTokexPanel(thread);
          saveStore();
          if (evt.attachment_warning) showError(evt.attachment_warning);
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
    thread.messages.push({ role: "assistant", content: assistant });
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
    bubble.querySelector(".body").innerHTML = formatReply(errText);
    thread.messages.push({ role: "assistant", content: errText });
    saveStore();
  }
}

document.getElementById("attachBtn").onclick = () => fileInput.click();
fileInput.onchange = async () => {
  const incoming = Array.from(fileInput.files || []);
  fileInput.value = "";
  await stageIncomingFiles(incoming);
};
document.getElementById("sendBtn").onclick = () => send();
document.getElementById("newChat").onclick = () => createChat();
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
});
promptEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

async function maybeShowKeyWizard() {
  const modal = document.getElementById("keyModal");
  if (!modal) return;
  try {
    const res = await fetch("/settings/keys");
    const data = await res.json();
    fillKeyWizard(data);
    if (data.prefs?.hide_key_wizard) return;
    modal.hidden = false;
  } catch {
    modal.hidden = false;
  }
}

function fillKeyWizard(data) {
  const map = {
    keyGemini: data.has?.gemini,
    keyOpenRouter: data.has?.openrouter,
    keyOpenAI: data.has?.openai,
    keyAnthropic: data.has?.anthropic,
    keyPerplexity: data.has?.perplexity,
    keyGroq: data.has?.groq,
  };
  for (const [id, present] of Object.entries(map)) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (present) {
      el.placeholder = "already saved — paste to replace";
    }
  }
  if (data.prefs?.fallback_preference) {
    const pref = document.getElementById("fallbackPref");
    if (pref) pref.value = data.prefs.fallback_preference;
  }
}

async function handleKeySave(fromModal) {
  const msg = document.getElementById("keyModalMsg");
  const payload = fromModal
    ? {
        GEMINI_API_KEY: document.getElementById("keyGemini")?.value.trim() || "",
        OPENROUTER_API_KEY: document.getElementById("keyOpenRouter")?.value.trim() || "",
        OPENAI_API_KEY: document.getElementById("keyOpenAI")?.value.trim() || "",
        ANTHROPIC_API_KEY: document.getElementById("keyAnthropic")?.value.trim() || "",
        PERPLEXITY_API_KEY: document.getElementById("keyPerplexity")?.value.trim() || "",
        GROQ_API_KEY: document.getElementById("keyGroq")?.value.trim() || "",
        fallback_preference: document.getElementById("fallbackPref")?.value.trim() || "",
        hide_key_wizard: !!document.getElementById("dontShowWizard")?.checked,
      }
    : {
        GEMINI_API_KEY: document.getElementById("sideKeyGemini")?.value.trim() || "",
        OPENROUTER_API_KEY: document.getElementById("sideKeyOpenRouter")?.value.trim() || "",
      };

  const hasAny = Object.entries(payload).some(
    ([k, v]) => k.endsWith("_KEY") || k === "OPENAI_API_KEY" || k === "ANTHROPIC_API_KEY" || k === "GROQ_API_KEY" || k === "PERPLEXITY_API_KEY" || k === "GEMINI_API_KEY" || k === "OPENROUTER_API_KEY"
      ? !!v
      : false,
  );
  // Allow save of prefs alone from modal if keys already exist.
  if (fromModal && !hasAny) {
    // still try — server accepts prefs-only when a key already saved
  } else if (!fromModal && !payload.GEMINI_API_KEY && !payload.OPENROUTER_API_KEY) {
    showError("paste at least one key");
    return;
  }

  try {
    const data = await saveKeys(payload);
    if (fromModal) document.getElementById("keyModal").hidden = true;
    if (msg) msg.hidden = true;
    showError("");
    const th = activeThread();
    if (th) {
      const note = `connections saved${data.saved?.length ? ` (${data.saved.join(", ")})` : ""}. you can keep chatting.`;
      addBubble("assistant", note);
      th.messages.push({ role: "assistant", content: note });
      saveStore();
    }
    await loadProviders();
  } catch (e) {
    showError(e.message || String(e));
    if (msg) { msg.hidden = false; msg.textContent = e.message || String(e); }
  }
}

document.getElementById("keySkip")?.addEventListener("click", () => {
  document.getElementById("keyModal").hidden = true;
});
document.getElementById("keySave")?.addEventListener("click", () => handleKeySave(true));
document.getElementById("sideKeySave")?.addEventListener("click", () => handleKeySave(false));
document.getElementById("openKeyWizard")?.addEventListener("click", async () => {
  const modal = document.getElementById("keyModal");
  try {
    const res = await fetch("/settings/keys");
    fillKeyWizard(await res.json());
  } catch { /* ignore */ }
  if (modal) modal.hidden = false;
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
});

(function init() {
  const stored = loadStore();
  if (stored?.threads?.length) {
    threads = stored.threads.map((t) => ({
      ...t,
      tokex: normalizeTokex(t.tokex),
      messages: t.messages || [{ role: "assistant", content: WELCOME }],
    }));
    activeId = stored.activeId && threads.some((t) => t.id === stored.activeId)
      ? stored.activeId
      : threads[0].id;
    lifetime = stored.lifetime
      ? normalizeTokex(stored.lifetime)
      : rebuildLifetimeFromThreads();
  } else {
    const th = newThread();
    threads = [th];
    activeId = th.id;
    lifetime = emptyTokex();
  }
  renderThreadList();
  selectThread(activeId);
  fillModels(DEFAULT_MODELS);
  loadProviders();
  maybeShowKeyWizard();
  retitleAllThreads({ force: true });
})();
