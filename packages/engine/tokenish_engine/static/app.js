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
const WELCOME = "Attach a pdf, docx, xlsx, csv, or image. tokenish optimizes every send automatically.";

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

function newThread(title = "New chat") {
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

function renderAttachments() {
  attachmentsEl.innerHTML = files.map((f) => `<span class="chip">${escapeHtml(f.name)}</span>`).join("");
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

function renderTokexPanel() {
  const t = normalizeTokex(lifetime);
  lifetime = t;
  const before = t.before || 0;
  const after = t.after || 0;
  const saved = Math.max(0, t.saved || before - after);
  // Grand total = total tokens saved / total tokens before (across all sends).
  const grandPct = before > 0 ? Math.round((saved / before) * 10000) / 100 : 0;

  document.getElementById("tokexSaved").textContent = before
    ? `Saved Tokens ${grandPct}%`
    : "Saved Tokens 0%";
  document.getElementById("tokexScope").textContent = t.sends.length
    ? `lifetime grand total · ${t.sends.length} send${t.sends.length === 1 ? "" : "s"} · all chats`
    : "lifetime grand total · all chats";
  document.getElementById("tokexTotal").textContent = Number(before).toLocaleString();
  document.getElementById("tokexRun").textContent = Number(after).toLocaleString();
  document.getElementById("tokexPct").textContent = `${Number(saved).toLocaleString()} (${grandPct}%)`;

  const weightedEl = document.getElementById("tokexWeighted");
  if (t.sends.length > 1) {
    weightedEl.hidden = false;
    const parts = t.sends.map((s) => Number(s.saved || 0).toLocaleString()).join(" + ");
    weightedEl.textContent =
      `saved ${parts} = ${Number(saved).toLocaleString()} ÷ before ${Number(before).toLocaleString()} = ${grandPct}%`;
  } else {
    weightedEl.hidden = true;
    weightedEl.textContent = "";
  }

  const sendsEl = document.getElementById("tokexSends");
  if (t.sends.length) {
    sendsEl.hidden = false;
    const recent = t.sends.slice(-8);
    const offset = t.sends.length - recent.length;
    sendsEl.innerHTML = recent
      .map(
        (s, i) =>
          `<div>send ${offset + i + 1}: saved ${Number(s.saved).toLocaleString()} ` +
          `(${Number(s.before).toLocaleString()} → ${Number(s.after).toLocaleString()}) · ${s.pct}%</div>`,
      )
      .join("");
  } else {
    sendsEl.hidden = true;
    sendsEl.innerHTML = "";
  }
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

function addBubble(role, content) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  if (role === "user") {
    div.innerHTML = `<div class="body">${escapeHtml(content)}</div>`;
  } else {
    div.innerHTML = `<div class="body">${formatReply(content)}</div>`;
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
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
  const t = (prompt || "").trim().replace(/\s+/g, " ");
  if (!t) return "New chat";
  return t.length > 42 ? `${t.slice(0, 42)}…` : t;
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
    addBubble(m.role, m.content);
  }
  renderTokexPanel();
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
      if (["openai", "anthropic"].includes(p.name)) continue;
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

  addBubble("user", prompt);
  thread.messages.push({ role: "user", content: prompt });
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
  const pageRange = document.getElementById("pageRange").value.trim();
  if (pageRange) fd.append("page_range", pageRange);
  for (const f of files) fd.append("files", f);

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
          renderTokexPanel();
          saveStore();
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
    files = [];
    fileInput.value = "";
    renderAttachments();
    renderThreadList();
    saveStore();
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
fileInput.onchange = () => {
  files = Array.from(fileInput.files || []);
  renderAttachments();
};
document.getElementById("sendBtn").onclick = () => send();
document.getElementById("newChat").onclick = () => createChat();
document.addEventListener("click", () => closeAllThreadMenus());
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
    if (data.gemini || data.openrouter) return;
    modal.hidden = false;
  } catch {
    modal.hidden = false;
  }
}

async function handleKeySave(fromModal) {
  const gemini = (fromModal
    ? document.getElementById("keyGemini")
    : document.getElementById("sideKeyGemini")
  ).value.trim();
  const openrouter = (fromModal
    ? document.getElementById("keyOpenRouter")
    : document.getElementById("sideKeyOpenRouter")
  ).value.trim();
  const msg = document.getElementById("keyModalMsg");
  if (!gemini && !openrouter) {
    showError("paste a Gemini or OpenRouter key");
    if (msg) { msg.hidden = false; msg.textContent = "paste a Gemini or OpenRouter key"; }
    return;
  }
  try {
    const data = await saveKeys({
      GEMINI_API_KEY: gemini,
      OPENROUTER_API_KEY: openrouter,
    });
    if (fromModal) document.getElementById("keyModal").hidden = true;
    if (msg) msg.hidden = true;
    showError("");
    const th = activeThread();
    if (th) {
      const note = `Keys saved (${(data.saved || []).join(", ") || "ok"}). Try sending again.`;
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
})();
