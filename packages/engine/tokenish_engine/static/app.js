const messagesEl = document.getElementById("messages");
const errorEl = document.getElementById("error");
const promptEl = document.getElementById("prompt");
const fileInput = document.getElementById("fileInput");
const attachmentsEl = document.getElementById("attachments");
const providersEl = document.getElementById("providers");
const modelSelect = document.getElementById("model");
const providerSelect = document.getElementById("provider");

let history = [];
let files = [];

const DEFAULT_MODELS = [
  "gemini-3.5-flash",
  "openrouter/free",
];

function showError(msg) {
  errorEl.hidden = !msg;
  errorEl.textContent = msg || "";
}

function renderAttachments() {
  attachmentsEl.innerHTML = files.map((f) => `<span class="chip">${f.name}</span>`).join("");
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

/** Soft-clean model markdown into readable plain-looking HTML (no report chrome). */
function formatReply(text) {
  let s = String(text || "");
  // Strip common markdown report decoration while keeping readable structure.
  s = s.replace(/^#{1,6}\s+/gm, "");
  s = s.replace(/\*\*([^*]+)\*\*/g, "$1");
  s = s.replace(/__([^_]+)__/g, "$1");
  s = s.replace(/\*([^*]+)\*/g, "$1");
  s = s.replace(/^---+$/gm, "");
  s = s.replace(/^>\s?/gm, "");
  return escapeHtml(s);
}

function renderTokex(t) {
  const saved = t ? (t.saved_tokex ?? t.saved_tokens ?? 0) : 0;
  const total = t ? (t.total_tokex ?? t.original_tokens ?? 0) : 0;
  const run = t ? (t.tokex_this_run ?? t.optimized_tokens ?? 0) : 0;
  const pct = t ? (t.saved_pct ?? 0) : 0;
  const minimal = total > 0 && total < 32 && saved === 0;
  const overhead = total > 0 && run > total;
  document.getElementById("tokexSaved").textContent = minimal
    ? "Saved Tokens —"
    : overhead
      ? "Saved Tokens 0%"
      : `Saved Tokens ${pct}%`;
  document.getElementById("tokexTotal").textContent = Number(total).toLocaleString();
  document.getElementById("tokexRun").textContent = Number(run).toLocaleString();
  document.getElementById("tokexPct").textContent = minimal
    ? "short prompt"
    : overhead
      ? `+${Number(run - total).toLocaleString()} overhead`
      : `${Number(saved).toLocaleString()} (${pct}%)`;
}

function addBubble(role, content, meta = {}) {
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
  const prompt = promptEl.value.trim() || (files.length ? "(attachment only)" : "");
  if (!prompt && !files.length) return;
  showError("");
  addBubble("user", prompt);
  history.push({ role: "user", content: prompt });
  promptEl.value = "";

  const fd = new FormData();
  fd.append("prompt", prompt);
  const model = modelSelect.value;
  const provider = providerSelect.value;
  fd.append("target_engine", model);
  fd.append("model", model);
  fd.append("provider", provider);
  fd.append("history", JSON.stringify(history.slice(0, -1)));
  fd.append("stream", "true");
  const pageRange = document.getElementById("pageRange").value.trim();
  if (pageRange) fd.append("page_range", pageRange);
  for (const f of files) fd.append("files", f);

  const loader = makeTknshLoader();
  let bubble = null;
  let assistant = "";
  let meta = {};

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
          meta = evt;
          renderTokex(evt.tokex || evt.meter);
        } else if (evt.type === "routing") {
          meta.provider = evt.provider;
          meta.model = evt.model;
          meta.fallback_used = evt.fallback_used;
          meta.fallback_reason = evt.fallback_reason;
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
    history.push({ role: "assistant", content: assistant });
    files = [];
    fileInput.value = "";
    renderAttachments();
  } catch (e) {
    loader.remove();
    showError(e.message || String(e));
    if (!bubble) bubble = addBubble("assistant", "");
    bubble.querySelector(".body").innerHTML = formatReply("error: " + (e.message || e));
  }
}

document.getElementById("attachBtn").onclick = () => fileInput.click();
fileInput.onchange = () => {
  files = Array.from(fileInput.files || []);
  renderAttachments();
};
document.getElementById("sendBtn").onclick = () => send();
document.getElementById("newChat").onclick = () => {
  history = [];
  messagesEl.innerHTML = "";
  addBubble("assistant", "Attach a pdf, docx, xlsx, csv, or image. tokenish optimizes every send automatically.");
};
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
    addBubble("assistant", `Keys saved (${(data.saved || []).join(", ") || "ok"}). Try sending again.`);
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

addBubble("assistant", "Attach a pdf, docx, xlsx, csv, or image. tokenish optimizes every send automatically.");
fillModels(DEFAULT_MODELS);
loadProviders();
maybeShowKeyWizard();
