"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Recorder } from "@/lib/recorder";
import { api, TranscriptLine } from "@/lib/api";
import { formatClock } from "@/lib/format";
import DiarizeProgress from "@/components/DiarizeProgress";
import {
  AlertIcon,
  FileTextIcon,
  MicIcon,
  StopIcon,
  UsersIcon,
} from "@/components/Icons";

export default function RecordPage() {
  const router = useRouter();
  const [recording, setRecording] = useState(false);
  const [title, setTitle] = useState("Untitled meeting");
  const [systemAudio, setSystemAudio] = useState(false);
  const [identifySpeakers, setIdentifySpeakers] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [diarizeJobId, setDiarizeJobId] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const recorderRef = useRef<Recorder | null>(null);
  const linesEndRef = useRef<HTMLDivElement | null>(null);

  // Live elapsed-time clock while recording.
  useEffect(() => {
    if (!recording) return;
    const started = Date.now();
    setElapsed(0);
    const t = setInterval(() => setElapsed((Date.now() - started) / 1000), 250);
    return () => clearInterval(t);
  }, [recording]);

  // Keep the newest transcript chunk in view.
  useEffect(() => {
    linesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lines]);

  async function start() {
    setError(null);
    setLines([]);
    const rec = new Recorder({
      captureSystemAudio: systemAudio,
      keepFullAudio: identifySpeakers,
      onTranscript: (t) => setLines((prev) => [...prev, t]),
      onError: (e) => setError(e),
    });
    recorderRef.current = rec;
    try {
      await rec.start();
      setRecording(true);
    } catch (e) {
      setError(`Could not start recording: ${e}`);
    }
  }

  async function stopAndSave() {
    const rec = recorderRef.current;
    setSaving(true);
    await rec?.stop();
    setRecording(false);
    const now = new Date().toISOString();
    const transcripts: TranscriptLine[] = lines.map((text, i) => ({
      id: `${now}-${i}`,
      text,
      timestamp: now,
    }));
    try {
      setStatus("Saving meeting…");
      const { meeting_id } = await api.saveTranscript({
        meeting_title: title,
        transcripts,
      });

      // Post-meeting diarization on the full recording (replaces transcript
      // with speaker-labeled segments).
      if (identifySpeakers) {
        const wav = rec?.getFullWav();
        if (wav) {
          setStatus("Uploading recording for speaker identification…");
          const { meeting_id: mid } = await api.transcribeDiarized(wav, {
            meeting_id,
          });
          // Show inline progress widget; navigate when the job finishes.
          setSaving(false);
          setStatus(null);
          setDiarizeJobId(mid);
          return;
        }
      }
      router.push(`/meeting/${meeting_id}`);
    } catch (e) {
      setError(`Failed: ${e}`);
      setStatus(null);
      setSaving(false);
    }
  }

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>Record meeting</h1>
          <div className="subtitle">
            Audio is transcribed in short chunks as you speak.
          </div>
        </div>
      </div>

      {error && (
        <div className="alert err">
          <AlertIcon size={18} />
          <span>{error}</span>
        </div>
      )}

      <div className="card pad-lg">
        <div className="rec-stage">
          <div className={`rec-orb${recording ? " live" : ""}`}>
            <MicIcon size={34} />
          </div>
          <div className="rec-timer">{formatClock(elapsed)}</div>
          {recording ? (
            <span className="badge err">
              <span className="dot" />
              Recording
            </span>
          ) : (
            <span className="muted">Ready to record</span>
          )}

          <div className="row" style={{ marginTop: 8 }}>
            {!recording ? (
              <button className="btn lg" onClick={start} disabled={saving}>
                <MicIcon size={18} />
                Start recording
              </button>
            ) : (
              <button className="btn danger lg" onClick={stopAndSave} disabled={saving}>
                <StopIcon size={18} />
                Stop &amp; save
              </button>
            )}
          </div>
          {status && <p className="muted">{status}</p>}
        </div>

        <div className="divider" />

        <div className="field">
          <label>Meeting title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={recording}
          />
        </div>

        <label className="switch" style={{ marginBottom: 14 }}>
          <input
            type="checkbox"
            checked={systemAudio}
            disabled={recording}
            onChange={(e) => setSystemAudio(e.target.checked)}
          />
          <span className="track" />
          <span>
            <span className="switch-label">Capture system / tab audio</span>
            <br />
            <span className="switch-sub">Prompts to share a screen or tab</span>
          </span>
        </label>

        <label className="switch">
          <input
            type="checkbox"
            checked={identifySpeakers}
            disabled={recording}
            onChange={(e) => setIdentifySpeakers(e.target.checked)}
          />
          <span className="track" />
          <span>
            <span className="switch-label">
              <UsersIcon size={14} style={{ verticalAlign: "-2px", marginRight: 6 }} />
              Identify speakers
            </span>
            <br />
            <span className="switch-sub">
              Diarizes the full recording after you stop
            </span>
          </span>
        </label>
      </div>

      {diarizeJobId && (
        <div style={{ marginTop: 24 }}>
          <DiarizeProgress
            meetingId={diarizeJobId}
            onComplete={(id) => router.push(`/meeting/${id}`)}
            onError={(err) => {
              setError(err);
              setDiarizeJobId(null);
            }}
          />
        </div>
      )}

      <div className="section-head">
        <FileTextIcon size={16} />
        <h2>Live transcript</h2>
      </div>
      <div className="card">
        {lines.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            Transcript chunks will appear here as you speak.
          </p>
        ) : (
          <div className="transcript">
            {lines.map((l, i) => (
              <div className="t-flat fade-in" key={i}>
                {l}
              </div>
            ))}
            <div ref={linesEndRef} />
          </div>
        )}
      </div>
    </div>
  );
}
