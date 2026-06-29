"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Meeting } from "@/lib/api";

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<
    Array<{ meeting_id: string; title: string; transcript: string }>
  >([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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

  return (
    <div>
      <div className="row spread">
        <h1>Meetings</h1>
        <Link href="/record" className="btn">
          + New recording
        </Link>
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
