"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Recorder } from "@/lib/recorder";
import { api, TranscriptLine } from "@/lib/api";

export default function RecordPage() {
  const router = useRouter();
  const [recording, setRecording] = useState(false);
  const [title, setTitle] = useState("Untitled meeting");
  const [systemAudio, setSystemAudio] = useState(false);
  const [lines, setLines] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<Recorder | null>(null);

  async function start() {
    setError(null);
    setLines([]);
    const rec = new Recorder({
      captureSystemAudio: systemAudio,
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
    await recorderRef.current?.stop();
    setRecording(false);
    const now = new Date().toISOString();
    const transcripts: TranscriptLine[] = lines.map((text, i) => ({
      id: `${now}-${i}`,
      text,
      timestamp: now,
    }));
    try {
      const { meeting_id } = await api.saveTranscript({
        meeting_title: title,
        transcripts,
      });
      router.push(`/meeting/${meeting_id}`);
    } catch (e) {
      setError(`Failed to save meeting: ${e}`);
    }
  }

  return (
    <div>
      <h1>Record meeting</h1>

      <div className="card">
        <label>Meeting title</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />

        <label className="row" style={{ marginTop: 12 }}>
          <input
            type="checkbox"
            checked={systemAudio}
            disabled={recording}
            onChange={(e) => setSystemAudio(e.target.checked)}
            style={{ width: "auto" }}
          />
          <span style={{ marginLeft: 8 }}>
            Also capture system / tab audio (screen-share prompt)
          </span>
        </label>

        <div className="row" style={{ marginTop: 14 }}>
          {!recording ? (
            <button className="btn" onClick={start}>
              ● Start recording
            </button>
          ) : (
            <button className="btn danger" onClick={stopAndSave}>
              ■ Stop & save
            </button>
          )}
          {recording && <span className="pill ok">recording…</span>}
        </div>
      </div>

      {error && <div className="card pill err">{error}</div>}

      <h2>Live transcript</h2>
      <div className="card">
        {lines.length === 0 && (
          <p className="muted">
            Transcript chunks will appear here as you speak.
          </p>
        )}
        {lines.map((l, i) => (
          <div className="transcript-line" key={i}>
            {l}
          </div>
        ))}
      </div>
    </div>
  );
}
