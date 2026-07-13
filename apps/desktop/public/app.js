const messagesEl = document.getElementById("messages");
const meterEl = document.getElementById("meter");
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

function addBubble(role, content, meta = {}) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  const metaBits = [role];
  if (meta.provider) metaBits.push(`${meta.provider}/${meta.model || ""}`);
  if (meta.meter) {
    metaBits.push(
      `${meta.meter.original_tokens}→${meta.meter.optimized_tokens} (−${meta.meter.saved_pct}%)`
    );
  }
  let html = `<div class="meta">${metaBits.join(" · ")}</div>${escapeHtml(content)}`;
  if (document.getElementById("showEnv").checked && meta.envelope) {
    html += `<div class="envelope">${escapeHtml(meta.envelope)}</div>`;
  }
  div.innerHTML = html;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
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
      if (p.name === "ollama" && p.available && p.models?.length) {
        document.getElementById("provider").value = "ollama";
        document.getElementById("model").value = p.models[0];
      }
    }
    modelsList.innerHTML = [...modelSet].map((m) => `<option value="${m}"></option>`).join("");
  } catch {
    showError("Engine offline");
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
  fd.append("show_envelope", String(document.getElementById("showEnv").checked));
  fd.append("enable_pxpipe", String(document.getElementById("pxpipe").checked));
  fd.append("enable_headroom", String(document.getElementById("headroom").checked));
  fd.append("enable_its", String(document.getElementById("its").checked));
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
        try {
          evt = JSON.parse(line);
        } catch {
          continue;
        }
        if (evt.type === "meta") {
          meta = evt;
          if (evt.meter) {
            meterEl.innerHTML = `before <strong>${evt.meter.original_tokens}</strong> · after <strong>${evt.meter.optimized_tokens}</strong> · saved <strong>${evt.meter.saved_tokens}</strong> (${evt.meter.saved_pct}%) · ${(evt.stages || []).join(" → ")}`;
          }
        } else if (evt.type === "delta") {
          assistant += evt.text || "";
          bubble.innerHTML = `<div class="meta">assistant${meta.provider ? ` · ${meta.provider}/${meta.model}` : ""}${
            meta.meter
              ? ` · ${meta.meter.original_tokens}→${meta.meter.optimized_tokens} (−${meta.meter.saved_pct}%)`
              : ""
          }</div>${escapeHtml(assistant)}${
            document.getElementById("showEnv").checked && meta.envelope
              ? `<div class="envelope">${escapeHtml(meta.envelope)}</div>`
              : ""
          }`;
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
    bubble.innerHTML = `<div class="meta">assistant</div>${escapeHtml("Error: " + (e.message || e))}`;
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
  addBubble(
    "assistant",
    "Drop a PDF, DOCX, XLSX, CSV, or image. Your prompt is LCS-compressed; document text stays verbatim in #D."
  );
};
promptEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

addBubble(
  "assistant",
  "Drop a PDF, DOCX, XLSX, CSV, or image. Your prompt is LCS-compressed; document text stays verbatim in #D. Pick a local or cloud model and send."
);
loadProviders();
