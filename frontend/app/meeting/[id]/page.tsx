"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, MeetingDetails, SummaryStatus } from "@/lib/api";
import { speakerColor, speakerLabel } from "@/lib/format";
import {
  AlertIcon,
  CheckIcon,
  DownloadIcon,
  FileTextIcon,
  SparklesIcon,
} from "@/components/Icons";

export default function MeetingPage() {
  const params = useParams();
  const id = params.id as string;
  const [meeting, setMeeting] = useState<MeetingDetails | null>(null);
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState<SummaryStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [savedTitle, setSavedTitle] = useState(false);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    setSavedTitle(true);
    setTimeout(() => setSavedTitle(false), 1800);
    load();
  }

  function onExport() {
    if (!meeting) return;
    const lines = meeting.transcripts
      .map((t) => (t.speaker ? `${speakerLabel(t.speaker)}: ${t.text}` : t.text))
      .join("\n");
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

  if (error)
    return (
      <div className="alert err fade-in">
        <AlertIcon size={18} />
        <span>{error}</span>
      </div>
    );
  if (!meeting)
    return (
      <div className="col fade-in">
        <div className="skeleton" style={{ height: 40, width: "50%" }} />
        <div className="skeleton card" style={{ height: 120 }} />
        <div className="skeleton card" style={{ height: 200 }} />
      </div>
    );

  const result = summary?.result;
  const status = summary?.status ?? "none";
  const statusClass =
    status === "completed" ? "ok" : status === "failed" ? "err" : "warn";
  const hasSpeakers = meeting.transcripts.some((t) => t.speaker);

  return (
    <div className="fade-in">
      <div className="page-head">
        <div className="search grow" style={{ maxWidth: 520 }}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={{ fontSize: 18, fontWeight: 600 }}
            aria-label="Meeting title"
          />
        </div>
        <div className="row">
          <button className="btn secondary" onClick={onSaveTitle}>
            {savedTitle ? <CheckIcon size={16} /> : null}
            {savedTitle ? "Saved" : "Save title"}
          </button>
          <button className="btn secondary" onClick={onExport}>
            <DownloadIcon size={16} />
            Export
          </button>
        </div>
      </div>

      <div className="section-head" style={{ marginTop: 0 }}>
        <SparklesIcon size={16} />
        <h2>Summary</h2>
      </div>
      <div className="card pad-lg">
        <div className="row spread">
          <span className={`badge ${statusClass}`}>
            <span className="dot" />
            {status === "none" ? "Not generated" : status}
          </span>
          <button className="btn" onClick={onGenerate} disabled={busy}>
            <SparklesIcon size={16} />
            {busy ? "Starting…" : result ? "Regenerate" : "Generate summary"}
          </button>
        </div>

        {summary?.error && (
          <div className="alert err" style={{ marginTop: 16, marginBottom: 0 }}>
            <AlertIcon size={18} />
            <span>{summary.error}</span>
          </div>
        )}

        {status === "processing" && (
          <p className="muted" style={{ marginTop: 16, marginBottom: 0 }}>
            Generating… this updates automatically.
          </p>
        )}

        {result && (
          <div style={{ marginTop: 18 }}>
            <div className="summary-block">
              <p style={{ margin: 0, color: "var(--text-2)" }}>{result.summary}</p>
            </div>

            {result.action_items.length > 0 && (
              <div className="summary-block">
                <div className="block-title">
                  <CheckIcon size={14} />
                  Action items
                </div>
                <ul className="check-list">
                  {result.action_items.map((a, i) => (
                    <li key={i}>
                      <CheckIcon size={15} />
                      <span>{a}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.key_points.length > 0 && (
              <div className="summary-block">
                <div className="block-title">
                  <SparklesIcon size={14} />
                  Key points
                </div>
                <ul className="check-list">
                  {result.key_points.map((k, i) => (
                    <li key={i}>
                      <SparklesIcon size={15} />
                      <span>{k}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="section-head">
        <FileTextIcon size={16} />
        <h2>Transcript</h2>
        {hasSpeakers && (
          <span className="badge brand" style={{ marginLeft: 4 }}>
            Speakers identified
          </span>
        )}
      </div>
      <div className="card">
        {meeting.transcripts.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            No transcript lines.
          </p>
        ) : (
          <div className="transcript">
            {meeting.transcripts.map((t) => (
              <div className={hasSpeakers ? "t-line" : "t-flat"} key={t.id}>
                {hasSpeakers && (
                  <div
                    className="who"
                    style={{ color: t.speaker ? speakerColor(t.speaker) : "var(--muted)" }}
                  >
                    {t.speaker && (
                      <span
                        className="swatch"
                        style={{ background: speakerColor(t.speaker) }}
                      />
                    )}
                    {t.speaker ? speakerLabel(t.speaker) : "—"}
                  </div>
                )}
                <div className="body">{t.text}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
