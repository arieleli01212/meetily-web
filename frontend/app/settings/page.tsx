"use client";

import { useEffect, useState } from "react";
import { api, API_BASE, RuntimeConfig } from "@/lib/api";

export default function SettingsPage() {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [health, setHealth] = useState<string>("checking…");
  const [provider, setProvider] = useState("ollama");
  const [model, setModel] = useState("");
  const [whisperModel, setWhisperModel] = useState("base.en");
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await api.getConfig();
        setConfig(cfg);
        setProvider(cfg.llm_provider);
        setModel(cfg.llm_model);
      } catch (e) {
        setError(String(e));
      }
      try {
        const h = await api.health();
        setHealth(h.status);
      } catch {
        setHealth("unreachable");
      }
      try {
        const mc = await api.getModelConfig();
        setProvider(mc.provider);
        setModel(mc.model);
        setWhisperModel(mc.whisperModel);
      } catch {
        /* fall back to env config above */
      }
    })();
  }, []);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setSaved(false);
    try {
      await api.saveModelConfig({ provider, model, whisperModel, apiKey });
      setSaved(true);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div>
      <h1>Settings</h1>

      <h2>Connections</h2>
      <div className="card">
        <div className="row spread">
          <span>Backend</span>
          <span className="muted">{API_BASE}</span>
        </div>
        <div className="row spread">
          <span>Backend health</span>
          <span className={`pill ${health === "ok" ? "ok" : "err"}`}>
            {health}
          </span>
        </div>
        {config && (
          <>
            <div className="row spread">
              <span>Whisper server URL</span>
              <span className="muted">{config.whisper_server_url}</span>
            </div>
            <div className="row spread">
              <span>LLM base URL</span>
              <span className="muted">{config.llm_base_url}</span>
            </div>
            <div className="row spread">
              <span>Chunk size / overlap</span>
              <span className="muted">
                {config.chunk_size} / {config.chunk_overlap}
              </span>
            </div>
          </>
        )}
        <p className="muted" style={{ marginTop: 10 }}>
          Connection URLs are set via environment variables (WHISPER_SERVER_URL,
          LLM_BASE_URL, …) so the deployment can point at local, air-gapped
          services. The model/provider selection below is editable at runtime.
        </p>
      </div>

      <h2>Summarization model</h2>
      <form className="card" onSubmit={onSave}>
        <label>Provider</label>
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="ollama">Ollama (local)</option>
          <option value="openai">OpenAI-compatible</option>
          <option value="groq">Groq</option>
          <option value="openrouter">OpenRouter</option>
          <option value="anthropic">Anthropic</option>
        </select>

        <label>Model</label>
        <input
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder="llama3.2"
        />

        <label>Whisper model</label>
        <input
          value={whisperModel}
          onChange={(e) => setWhisperModel(e.target.value)}
          placeholder="base.en"
        />

        <label>API key (leave blank for local/no-auth)</label>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="optional"
        />

        <div style={{ marginTop: 14 }}>
          <button className="btn" type="submit">
            Save
          </button>
          {saved && (
            <span className="pill ok" style={{ marginLeft: 10 }}>
              Saved
            </span>
          )}
        </div>
      </form>

      {error && <div className="card pill err">{error}</div>}
    </div>
  );
}
