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
  const [identifySpeakers, setIdentifySpeakers] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<Recorder | null>(null);

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
          setStatus("Identifying speakers… (this can take a while)");
          await api.transcribeDiarized(wav, { meeting_id });
        }
      }
      router.push(`/meeting/${meeting_id}`);
    } catch (e) {
      setError(`Failed: ${e}`);
      setStatus(null);
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

        <label className="row">
          <input
            type="checkbox"
            checked={identifySpeakers}
            disabled={recording}
            onChange={(e) => setIdentifySpeakers(e.target.checked)}
            style={{ width: "auto" }}
          />
          <span style={{ marginLeft: 8 }}>
            Identify speakers (diarize full recording after stop)
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
        {status && (
          <p className="muted" style={{ marginTop: 10 }}>
            {status}
          </p>
        )}
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
