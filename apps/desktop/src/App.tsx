import { useEffect, useMemo, useRef, useState } from "react";

type Provider = {
  name: string;
  available: boolean;
  detail: string;
  models: string[];
};

type Meter = {
  original_tokens: number;
  optimized_tokens: number;
  saved_tokens: number;
  saved_pct: number;
  stages: string[];
};

type ChatMsg = {
  role: "user" | "assistant" | "system";
  content: string;
  meter?: Meter;
  envelope?: string;
  stages?: string[];
  provider?: string;
  model?: string;
};

const API = import.meta.env.VITE_TOKENISH_API ?? "/api";

export default function App() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [provider, setProvider] = useState("auto");
  const [model, setModel] = useState("gpt-4o");
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEnvelope, setShowEnvelope] = useState(true);
  const [enablePxpipe, setEnablePxpipe] = useState(true);
  const [enableHeadroom, setEnableHeadroom] = useState(true);
  const [enableIts, setEnableIts] = useState(true);
  const [pageRange, setPageRange] = useState("");
  const [lastMeter, setLastMeter] = useState<Meter | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API}/providers`)
      .then((r) => r.json())
      .then((data) => {
        setProviders(data.providers || []);
        const ollama = (data.providers || []).find((p: Provider) => p.name === "ollama");
        if (ollama?.available && ollama.models?.length) {
          setProvider("ollama");
          setModel(ollama.models[0]);
        }
      })
      .catch(() => setError("Engine offline — start tokenish-engine on :8741"));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const modelOptions = useMemo(() => {
    const set = new Set<string>();
    for (const p of providers) for (const m of p.models || []) set.add(m);
    if (model) set.add(model);
    return Array.from(set);
  }, [providers, model]);

  async function send() {
    if (!prompt.trim() && files.length === 0) return;
    setBusy(true);
    setError(null);
    const userText = prompt.trim() || "(attachment only)";
    const history = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: userText }]);
    setPrompt("");

    const fd = new FormData();
    fd.append("prompt", userText);
    fd.append("target_engine", model);
    fd.append("model", model);
    fd.append("provider", provider);
    fd.append("history", JSON.stringify(history));
    fd.append("stream", "true");
    fd.append("show_envelope", String(showEnvelope));
    fd.append("enable_pxpipe", String(enablePxpipe));
    fd.append("enable_headroom", String(enableHeadroom));
    fd.append("enable_its", String(enableIts));
    if (pageRange.trim()) fd.append("page_range", pageRange.trim());
    for (const f of files) fd.append("files", f);

    try {
      const res = await fetch(`${API}/chat`, { method: "POST", body: fd });
      if (!res.ok || !res.body) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistant = "";
      let meter: Meter | undefined;
      let envelope: string | undefined;
      let stages: string[] | undefined;
      let usedProvider = provider;
      let usedModel = model;
      setMessages((m) => [...m, { role: "assistant", content: "" }]);

      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          let evt: any;
          try {
            evt = JSON.parse(line);
          } catch {
            continue;
          }
          if (evt.type === "meta") {
            meter = evt.meter;
            envelope = evt.envelope;
            stages = evt.stages;
            usedProvider = evt.provider || usedProvider;
            usedModel = evt.model || usedModel;
            if (meter) setLastMeter(meter);
          } else if (evt.type === "delta") {
            assistant += evt.text || "";
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = {
                role: "assistant",
                content: assistant,
                meter,
                envelope,
                stages,
                provider: usedProvider,
                model: usedModel,
              };
              return copy;
            });
          } else if (evt.type === "error") {
            throw new Error(evt.error || "chat failed");
          }
        }
      }
      setFiles([]);
      if (fileRef.current) fileRef.current.value = "";
    } catch (e: any) {
      setError(e?.message || String(e));
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Error: ${e?.message || e}`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <h1>Tokenish</h1>
          <span>Split-Execution token saver</span>
        </div>

        <div className="section-label">Provider</div>
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="auto">auto</option>
          <option value="ollama">ollama</option>
          <option value="openai">openai</option>
          <option value="anthropic">anthropic</option>
          <option value="groq">groq</option>
        </select>

        <div className="section-label">Model</div>
        <input
          list="models"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder="model id"
        />
        <datalist id="models">
          {modelOptions.map((m) => (
            <option key={m} value={m} />
          ))}
        </datalist>

        <div className="section-label">Providers</div>
        <div className="provider-list">
          {providers.map((p) => (
            <div className="provider" key={p.name}>
              <span>
                <span className={`dot ${p.available ? "ok" : "bad"}`} />
                {p.name}
              </span>
              <span style={{ color: "var(--muted)", fontSize: "0.75rem" }}>{p.detail}</span>
            </div>
          ))}
        </div>

        <div className="section-label">Optimizer</div>
        <div className="toggles">
          <label>
            <input type="checkbox" checked={enablePxpipe} onChange={(e) => setEnablePxpipe(e.target.checked)} />
            pxpipe (vision pack)
          </label>
          <label>
            <input type="checkbox" checked={enableHeadroom} onChange={(e) => setEnableHeadroom(e.target.checked)} />
            headroom
          </label>
          <label>
            <input type="checkbox" checked={enableIts} onChange={(e) => setEnableIts(e.target.checked)} />
            ITS gate
          </label>
          <label>
            <input type="checkbox" checked={showEnvelope} onChange={(e) => setShowEnvelope(e.target.checked)} />
            show compiled envelope
          </label>
        </div>

        <div className="section-label">PDF page range</div>
        <input
          type="text"
          placeholder="e.g. 12-15"
          value={pageRange}
          onChange={(e) => setPageRange(e.target.value)}
        />
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="meter">
            {lastMeter ? (
              <>
                <span>
                  before <strong>{lastMeter.original_tokens}</strong>
                </span>
                <span>
                  after <strong>{lastMeter.optimized_tokens}</strong>
                </span>
                <span>
                  saved <strong>{lastMeter.saved_tokens}</strong> ({lastMeter.saved_pct}%)
                </span>
                <span>{lastMeter.stages?.join(" → ")}</span>
              </>
            ) : (
              <span>Token meter appears after each send</span>
            )}
          </div>
          <button className="btn" onClick={() => setMessages([])} disabled={busy}>
            New chat
          </button>
        </div>

        <div className="messages">
          {messages.length === 0 && (
            <div className="bubble assistant">
              <div className="meta">tokenish</div>
              Drop a PDF, DOCX, XLSX, CSV, or image. Your prompt is LCS-compressed; document text stays
              verbatim in #D. Pick a local or cloud model and send.
            </div>
          )}
          {messages.map((m, i) => (
            <div className={`bubble ${m.role}`} key={i}>
              <div className="meta">
                {m.role}
                {m.provider ? ` · ${m.provider}/${m.model}` : ""}
                {m.meter
                  ? ` · ${m.meter.original_tokens}→${m.meter.optimized_tokens} (−${m.meter.saved_pct}%)`
                  : ""}
              </div>
              {m.content}
              {showEnvelope && m.envelope ? <div className="envelope">{m.envelope}</div> : null}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="composer">
          {files.length > 0 && (
            <div className="attachments">
              {files.map((f) => (
                <span className="chip" key={f.name}>
                  {f.name}
                </span>
              ))}
            </div>
          )}
          {error && <div className="error">{error}</div>}
          <div className="row">
            <button className="btn" onClick={() => fileRef.current?.click()} disabled={busy}>
              Attach
            </button>
            <input
              ref={fileRef}
              type="file"
              multiple
              hidden
              onChange={(e) => setFiles(Array.from(e.target.files || []))}
              accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.txt,.md,.json,.png,.jpg,.jpeg,.webp"
            />
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Message Tokenish…"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
            <button className="btn primary" onClick={() => void send()} disabled={busy}>
              {busy ? "…" : "Send"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
