// Typed client for the meetily web backend. The backend base URL is fully
// configurable via NEXT_PUBLIC_API_URL so the frontend can point at any
// backend host in an air-gapped deployment.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:5167";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export interface Meeting {
  id: string;
  title: string;
}

export interface TranscriptLine {
  id: string;
  text: string;
  timestamp: string;
  audio_start_time?: number | null;
  audio_end_time?: number | null;
  duration?: number | null;
}

export interface MeetingDetails {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  transcripts: TranscriptLine[];
}

export interface SummaryResult {
  summary: string;
  action_items: string[];
  key_points: string[];
}

export interface SummaryStatus {
  meeting_id: string;
  status: string;
  error?: string | null;
  result?: SummaryResult | null;
}

export interface RuntimeConfig {
  backend_host: string;
  backend_port: number;
  whisper_server_url: string;
  whisper_language: string;
  llm_provider: string;
  llm_base_url: string;
  llm_model: string;
  chunk_size: number;
  chunk_overlap: number;
}

export const api = {
  getMeetings: () => req<Meeting[]>("/get-meetings"),
  getMeeting: (id: string) => req<MeetingDetails>(`/get-meeting/${id}`),
  saveMeetingTitle: (meeting_id: string, title: string) =>
    req("/save-meeting-title", {
      method: "POST",
      body: JSON.stringify({ meeting_id, title }),
    }),
  deleteMeeting: (meeting_id: string) =>
    req("/delete-meeting", {
      method: "POST",
      body: JSON.stringify({ meeting_id }),
    }),
  saveTranscript: (payload: {
    meeting_title: string;
    transcripts: TranscriptLine[];
    meeting_id?: string;
  }) =>
    req<{ meeting_id: string }>("/save-transcript", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  searchTranscripts: (query: string) =>
    req<{ results: Array<{ meeting_id: string; title: string; transcript: string }> }>(
      "/search-transcripts",
      { method: "POST", body: JSON.stringify({ query }) },
    ),
  processTranscript: (meeting_id: string, model: string, model_name: string) =>
    req<{ process_id: string }>("/process-transcript", {
      method: "POST",
      body: JSON.stringify({ meeting_id, model, model_name }),
    }),
  getSummary: (id: string) => req<SummaryStatus>(`/get-summary/${id}`),
  getModelConfig: () =>
    req<{ provider: string; model: string; whisperModel: string }>(
      "/get-model-config",
    ),
  saveModelConfig: (payload: {
    provider: string;
    model: string;
    whisperModel: string;
    apiKey?: string;
  }) =>
    req("/save-model-config", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getConfig: () => req<RuntimeConfig>("/get-config"),
  health: () => req<{ status: string }>("/health"),
  transcribeUrl: () => `${API_BASE}/transcribe`,
};
