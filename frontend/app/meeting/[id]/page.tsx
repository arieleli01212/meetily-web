"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, MeetingDetails, SummaryStatus } from "@/lib/api";

export default function MeetingPage() {
  const params = useParams();
  const id = params.id as string;
  const [meeting, setMeeting] = useState<MeetingDetails | null>(null);
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState<SummaryStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const m = await api.getMeeting(id);
      setMeeting(m);
      setTitle(m.title);
    } catch (e) {
      setError(String(e));
    }
    try {
      setSummary(await api.getSummary(id));
    } catch {
      setSummary(null);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  // Poll while a summary is processing.
  useEffect(() => {
    if (summary?.status !== "processing") return;
    const t = setInterval(async () => {
      setSummary(await api.getSummary(id));
    }, 2000);
    return () => clearInterval(t);
  }, [summary?.status, id]);

  async function onGenerate() {
    setBusy(true);
    try {
      const cfg = await api.getModelConfig();
      await api.processTranscript(id, cfg.provider, cfg.model);
      setSummary(await api.getSummary(id));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSaveTitle() {
    await api.saveMeetingTitle(id, title);
    load();
  }

  function onExport() {
    if (!meeting) return;
    const lines = meeting.transcripts.map((t) => t.text).join("\n");
    const s = summary?.result;
    let md = `# ${meeting.title}\n\n## Transcript\n\n${lines}\n`;
    if (s) {
      md += `\n## Summary\n\n${s.summary}\n\n### Action Items\n`;
      md += s.action_items.map((a) => `- ${a}`).join("\n");
      md += `\n\n### Key Points\n`;
      md += s.key_points.map((k) => `- ${k}`).join("\n");
    }
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${meeting.title || "meeting"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (error) return <div className="card pill err">{error}</div>;
  if (!meeting) return <p className="muted">Loading…</p>;

  const result = summary?.result;

  return (
    <div>
      <div className="row spread">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          style={{ maxWidth: 480 }}
        />
        <div className="row">
          <button className="btn secondary" onClick={onSaveTitle}>
            Save title
          </button>
          <button className="btn secondary" onClick={onExport}>
            Export .md
          </button>
        </div>
      </div>

      <h2>Summary</h2>
      <div className="card">
        <div className="row spread">
          <span className="pill">{summary?.status ?? "none"}</span>
          <button className="btn" onClick={onGenerate} disabled={busy}>
            {busy ? "Starting…" : "Generate summary"}
          </button>
        </div>
        {summary?.error && (
          <p className="pill err" style={{ marginTop: 10 }}>
            {summary.error}
          </p>
        )}
        {result && (
          <div style={{ marginTop: 10 }}>
            <p>{result.summary}</p>
            {result.action_items.length > 0 && (
              <>
                <strong>Action items</strong>
                <ul>
                  {result.action_items.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </>
            )}
            {result.key_points.length > 0 && (
              <>
                <strong>Key points</strong>
                <ul>
                  {result.key_points.map((k, i) => (
                    <li key={i}>{k}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </div>

      <h2>Transcript</h2>
      <div className="card">
        {meeting.transcripts.length === 0 && (
          <p className="muted">No transcript lines.</p>
        )}
        {meeting.transcripts.map((t) => (
          <div className="transcript-line" key={t.id}>
            {t.text}
          </div>
        ))}
      </div>
    </div>
  );
}
