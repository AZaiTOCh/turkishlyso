
const messagesEl = document.getElementById("messages");
const errorEl = document.getElementById("error");
const promptEl = document.getElementById("prompt");
const fileInput = document.getElementById("fileInput");
const attachmentsEl = document.getElementById("attachments");
const providersEl = document.getElementById("providers");
const modelsList = document.getElementById("models");

let history = [];
let files = [];

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

function renderTokex(t) {
  const saved = t ? (t.saved_tokex ?? t.saved_tokens ?? 0) : 0;
  const total = t ? (t.total_tokex ?? t.original_tokens ?? 0) : 0;
  const run = t ? (t.tokex_this_run ?? t.optimized_tokens ?? 0) : 0;
  const pct = t ? (t.saved_pct ?? 0) : 0;
  document.getElementById("tokexSaved").textContent = `Saved Tokens ${pct}%`;
  document.getElementById("tokexTotal").textContent = Number(total).toLocaleString();
  document.getElementById("tokexRun").textContent = Number(run).toLocaleString();
  document.getElementById("tokexPct").textContent = `${Number(saved).toLocaleString()} (${pct}%)`;
}

function addBubble(role, content, meta = {}) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  const bits = [role];
  if (meta.provider) bits.push(`${meta.provider}/${meta.model || ""}`);
  const t = meta.tokex || meta.meter;
  if (t) bits.push(`saved ${t.saved_tokex ?? t.saved_tokens} (${t.saved_pct}%)`);
  div.innerHTML = `<div class="meta">${bits.join(" · ")}</div>${escapeHtml(content)}`;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

async function loadProviders() {
  try {
    const res = await fetch("/providers");
    const data = await res.json();
    providersEl.innerHTML = "";
    const modelSet = new Set();
    for (const p of data.providers || []) {
      const row = document.createElement("div");
      row.className = "provider";
      row.innerHTML = `<span><span class="dot ${p.available ? "ok" : "bad"}"></span>${p.name}</span><span style="color:var(--muted);font-size:0.75rem">${p.detail}</span>`;
      providersEl.appendChild(row);
      (p.models || []).forEach((m) => modelSet.add(m));
    }
    modelsList.innerHTML = [...modelSet].map((m) => `<option value="${m}"></option>`).join("");
    const pref = data.preferred;
    if (pref?.provider && pref?.model) {
      document.getElementById("provider").value =
        pref.provider === "openai" || pref.provider === "groq" ? "auto" : pref.provider;
      document.getElementById("model").value = pref.model;
    }
  } catch {
    showError("engine offline");
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
  const model = document.getElementById("model").value;
  const provider = document.getElementById("provider").value;
  fd.append("target_engine", model);
  fd.append("model", model);
  fd.append("provider", provider);
  fd.append("history", JSON.stringify(history.slice(0, -1)));
  fd.append("stream", "true");
  fd.append("show_envelope", "false");
  const pageRange = document.getElementById("pageRange").value.trim();
  if (pageRange) fd.append("page_range", pageRange);
  for (const f of files) fd.append("files", f);

  const bubble = addBubble("assistant", "");
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
        } else if (evt.type === "delta") {
          assistant += evt.text || "";
          const t = meta.tokex || meta.meter;
          const route = meta.provider
            ? `${meta.provider}/${meta.model}${meta.fallback_used ? " (fallback)" : ""}`
            : "";
          bubble.innerHTML = `<div class="meta">assistant${route ? ` · ${route}` : ""}${
            t ? ` · saved ${t.saved_tokex ?? t.saved_tokens} (${t.saved_pct}%)` : ""
          }</div>${escapeHtml(assistant)}`;
          messagesEl.scrollTop = messagesEl.scrollHeight;
        } else if (evt.type === "error") {
          throw new Error(evt.error || "chat failed");
        }
      }
    }
    history.push({ role: "assistant", content: assistant });
    files = [];
    fileInput.value = "";
    renderAttachments();
  } catch (e) {
    showError(e.message || String(e));
    bubble.innerHTML = `<div class="meta">assistant</div>${escapeHtml("error: " + (e.message || e))}`;
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
  addBubble("assistant", "attach a pdf, docx, xlsx, csv, or image. tokenish optimizes every send automatically.");
};
promptEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

addBubble("assistant", "attach a pdf, docx, xlsx, csv, or image. tokenish optimizes every send automatically.");
loadProviders();
