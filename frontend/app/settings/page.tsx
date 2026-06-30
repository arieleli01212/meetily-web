"use client";

import { useEffect, useState } from "react";
import { api, API_BASE, RuntimeConfig } from "@/lib/api";
import {
  AlertIcon,
  CheckIcon,
  KeyIcon,
  ServerIcon,
  SparklesIcon,
} from "@/components/Icons";

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
      setTimeout(() => setSaved(false), 1800);
    } catch (e) {
      setError(String(e));
    }
  }

  const healthy = health === "ok";

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <div className="subtitle">
            Connection endpoints come from environment variables; the model
            selection below is editable at runtime.
          </div>
        </div>
      </div>

      {error && (
        <div className="alert err">
          <AlertIcon size={18} />
          <span>{error}</span>
        </div>
      )}

      <div className="section-head" style={{ marginTop: 0 }}>
        <ServerIcon size={16} />
        <h2>Connections</h2>
      </div>
      <div className="card pad-lg">
        <div className="kv">
          <span className="k">Backend health</span>
          <span className={`badge ${healthy ? "ok" : "err"}`}>
            <span className="dot" />
            {health}
          </span>
        </div>
        <div className="kv">
          <span className="k">Backend</span>
          <span className="v">{API_BASE}</span>
        </div>
        {config && (
          <>
            <div className="kv">
              <span className="k">Whisper server</span>
              <span className="v">{config.whisper_server_url}</span>
            </div>
            <div className="kv">
              <span className="k">Transcription language</span>
              <span className="v">{config.whisper_language || "auto-detect"}</span>
            </div>
            <div className="kv">
              <span className="k">Diarization (WhisperX)</span>
              <span className="v">{config.diarize_server_url}</span>
            </div>
            <div className="kv">
              <span className="k">LLM base URL</span>
              <span className="v">{config.llm_base_url}</span>
            </div>
            <div className="kv">
              <span className="k">Chunk size / overlap</span>
              <span className="v">
                {config.chunk_size} / {config.chunk_overlap}
              </span>
            </div>
          </>
        )}
      </div>

      <div className="section-head">
        <SparklesIcon size={16} />
        <h2>Summarization model</h2>
      </div>
      <form className="card pad-lg" onSubmit={onSave}>
        <div className="field">
          <label>Provider</label>
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="ollama">Ollama (local)</option>
            <option value="openai">OpenAI-compatible</option>
            <option value="groq">Groq</option>
            <option value="openrouter">OpenRouter</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </div>

        <div className="field">
          <label>Model</label>
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="llama3.2"
          />
        </div>

        <div className="field">
          <label>Whisper model</label>
          <input
            value={whisperModel}
            onChange={(e) => setWhisperModel(e.target.value)}
            placeholder="base.en"
          />
        </div>

        <div className="field">
          <label>API key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Leave blank for local / no-auth"
          />
          <div className="hint">
            <KeyIcon size={12} style={{ verticalAlign: "-2px", marginRight: 4 }} />
            Stored on the backend; never exposed to the browser.
          </div>
        </div>

        <div className="row">
          <button className="btn" type="submit">
            {saved ? <CheckIcon size={16} /> : null}
            {saved ? "Saved" : "Save changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
