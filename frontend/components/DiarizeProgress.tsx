"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { UsersIcon, CheckCircleIcon, AlertIcon } from "./Icons";

const STEP_LABELS: Record<string, string> = {
  queued: "Job queued, waiting to start…",
  sending: "Uploading audio to WhisperX…",
  processing: "WhisperX is processing the audio…",
  saving: "Saving speaker-labeled transcript…",
  completed: "Done!",
  failed: "Failed",
};

interface Props {
  meetingId: string;
  onComplete: (meetingId: string) => void;
  onError: (err: string) => void;
}

function elapsed(createdAt: string): string {
  const s = Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 1000));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

export default function DiarizeProgress({ meetingId, onComplete, onError }: Props) {
  const [status, setStatus] = useState("queued");
  const [step, setStep] = useState("queued");
  const [createdAt, setCreatedAt] = useState<string>(new Date().toISOString());
  const [tick, setTick] = useState(0);

  // Increment tick every second for the elapsed timer.
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);

  // Poll the server every 3 s.
  useEffect(() => {
    if (status === "completed" || status === "failed") return;
    const poll = async () => {
      try {
        const j = await api.getDiarizeStatus(meetingId);
        setStatus(j.status);
        setStep(j.step ?? j.status);
        if (j.created_at) setCreatedAt(j.created_at);
        if (j.status === "completed") onComplete(meetingId);
        if (j.status === "failed") onError(j.error ?? "Diarization failed");
      } catch {
        /* transient error — keep polling */
      }
    };
    poll();
    const t = setInterval(poll, 3000);
    return () => clearInterval(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meetingId, status]);

  const done = status === "completed";
  const failed = status === "failed";
  const label = STEP_LABELS[step] ?? step;

  return (
    <div className="card pad-lg fade-in">
      <div className="row" style={{ gap: 16 }}>
        <div
          style={{
            display: "grid",
            placeItems: "center",
            width: 42,
            height: 42,
            borderRadius: "var(--r-md)",
            background: failed ? "var(--danger-soft)" : "var(--brand-soft)",
            color: failed ? "var(--danger)" : "var(--brand)",
            flex: "none",
          }}
        >
          {done ? (
            <CheckCircleIcon size={22} />
          ) : failed ? (
            <AlertIcon size={22} />
          ) : (
            <UsersIcon size={22} className={done ? "" : "spin"} />
          )}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            {done
              ? "Speaker identification complete"
              : failed
              ? "Speaker identification failed"
              : "Identifying speakers…"}
          </div>
          <div className="muted" style={{ fontSize: 13 }}>
            {label}
          </div>
        </div>
        <div
          className="mono muted"
          style={{ fontSize: 13, flexShrink: 0 }}
          suppressHydrationWarning
        >
          {tick >= 0 ? elapsed(createdAt) : ""}
        </div>
      </div>

      {!done && !failed && (
        <div style={{ marginTop: 14 }}>
          <div
            style={{
              height: 4,
              borderRadius: "var(--r-pill)",
              background: "var(--surface-3)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                borderRadius: "var(--r-pill)",
                background: "var(--brand-grad)",
                width: "60%",
                animation: "shimmer 1.8s ease-in-out infinite",
                backgroundSize: "200% 100%",
              }}
            />
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            Large files can take 10–60 minutes depending on your hardware. This
            page will update automatically — you can leave it open.
          </div>
        </div>
      )}
    </div>
  );
}
