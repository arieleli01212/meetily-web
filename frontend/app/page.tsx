"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, Meeting } from "@/lib/api";

export default function MeetingsPage() {
  const router = useRouter();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<
    Array<{ meeting_id: string; title: string; transcript: string }>
  >([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  async function load() {
    try {
      setMeetings(await api.getMeetings());
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const r = await api.searchTranscripts(query.trim());
    setResults(r.results);
  }

  async function onDelete(id: string) {
    await api.deleteMeeting(id);
    load();
  }

  async function onImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError(null);
    try {
      const { meeting_id } = await api.transcribeDiarized(file, {
        meeting_title: file.name,
      });
      router.push(`/meeting/${meeting_id}`);
    } catch (err) {
      setError(`Import failed: ${err}`);
    } finally {
      setImporting(false);
    }
  }

  return (
    <div>
      <div className="row spread">
        <h1>Meetings</h1>
        <div className="row">
          <button
            className="btn secondary"
            disabled={importing}
            onClick={() => fileRef.current?.click()}
          >
            {importing ? "Importing…" : "Import audio (diarize)"}
          </button>
          <Link href="/record" className="btn">
            + New recording
          </Link>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="audio/*"
          style={{ display: "none" }}
          onChange={onImport}
        />
      </div>

      <form className="row" onSubmit={onSearch} style={{ margin: "12px 0" }}>
        <input
          placeholder="Search transcripts…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn secondary" type="submit">
          Search
        </button>
      </form>

      {error && <div className="card pill err">Backend error: {error}</div>}
      {loading && <p className="muted">Loading…</p>}

      {results.length > 0 && (
        <div>
          <h2>Search results</h2>
          {results.map((r, i) => (
            <Link key={i} href={`/meeting/${r.meeting_id}`}>
              <div className="card">
                <strong>{r.title}</strong>
                <div className="muted">{r.transcript.slice(0, 140)}…</div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {!loading && meetings.length === 0 && !error && (
        <p className="muted">No meetings yet. Start a recording.</p>
      )}

      {meetings.map((m) => (
        <div className="card row spread" key={m.id}>
          <Link href={`/meeting/${m.id}`}>
            <strong>{m.title}</strong>
          </Link>
          <button className="btn danger" onClick={() => onDelete(m.id)}>
            Delete
          </button>
        </div>
      ))}
    </div>
  );
}
