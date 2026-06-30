// Small presentation helpers shared across pages.

// A fixed palette so a given speaker keeps the same colour across renders.
const SPEAKER_COLORS = [
  "#5b8cff",
  "#16b981",
  "#f5a524",
  "#f1576a",
  "#8a6cff",
  "#16c5d4",
  "#e879f9",
  "#84cc16",
];

/** "SPEAKER_00" -> "Speaker 1"; anything else passes through. */
export function speakerLabel(raw?: string | null): string {
  if (!raw) return "";
  const m = /^SPEAKER_(\d+)$/.exec(raw);
  if (m) return `Speaker ${parseInt(m[1], 10) + 1}`;
  return raw;
}

/** Stable colour for a speaker label/id. */
export function speakerColor(raw?: string | null): string {
  if (!raw) return SPEAKER_COLORS[0];
  const m = /^SPEAKER_(\d+)$/.exec(raw);
  let idx: number;
  if (m) {
    idx = parseInt(m[1], 10);
  } else {
    idx = 0;
    for (let i = 0; i < raw.length; i++) idx = (idx * 31 + raw.charCodeAt(i)) >>> 0;
  }
  return SPEAKER_COLORS[idx % SPEAKER_COLORS.length];
}

/** Seconds -> "m:ss" or "h:mm:ss". */
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
}

/** ISO timestamp -> human date, gracefully tolerant of bad input. */
export function formatDate(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** First letters for an avatar monogram. */
export function initials(title: string): string {
  const words = title.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "M";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}
