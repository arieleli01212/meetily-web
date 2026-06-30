"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, Meeting } from "@/lib/api";
import { initials } from "@/lib/format";
import DiarizeProgress from "@/components/DiarizeProgress";
import {
  AlertIcon,
  ListIcon,
  PlusIcon,
  SearchIcon,
  TrashIcon,
  UploadIcon,
} from "@/components/Icons";

type SearchHit = { meeting_id: string; title: string; transcript: string };

export default function MeetingsPage() {
  const router = useRouter();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchHit[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importJobId, setImportJobId] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
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
      setSearched(false);
      return;
    }
    try {
      const r = await api.searchTranscripts(query.trim());
      setResults(r.results);
      setSearched(true);
    } catch (e) {
      setError(String(e));
    }
  }

  async function onDelete(id: string) {
    if (confirmId !== id) {
      setConfirmId(id);
      return;
    }
    setConfirmId(null);
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
      // Show inline progress; navigation happens when the job completes.
      setImportJobId(meeting_id);
    } catch (err) {
      setError(`Import failed: ${err}`);
    } finally {
      setImporting(false);
      e.target.value = "";
    }
  }

  return (
    <div className="fade-in">
      <div className="page-head">
        <div>
          <h1>Meetings</h1>
          <div className="subtitle">
            Record, transcribe, and summarize — all on your own infrastructure.
          </div>
        </div>
        <div className="row">
          <button
            className="btn secondary"
            disabled={importing}
            onClick={() => fileRef.current?.click()}
          >
            <UploadIcon size={16} />
            {importing ? "Importing…" : "Import audio"}
          </button>
          <Link href="/record" className="btn">
            <PlusIcon size={16} />
            New recording
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

      <form className="row" onSubmit={onSearch} style={{ marginBottom: 24 }}>
        <div className="search">
          <SearchIcon size={17} />
          <input
            placeholder="Search across all transcripts…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (!e.target.value) {
                setResults([]);
                setSearched(false);
              }
            }}
          />
        </div>
        <button className="btn secondary" type="submit">
          Search
        </button>
      </form>

      {error && (
        <div className="alert err">
          <AlertIcon size={18} />
          <span>{error}</span>
        </div>
      )}

      {importJobId && (
        <div style={{ marginBottom: 24 }}>
          <DiarizeProgress
            meetingId={importJobId}
            onComplete={(id) => router.push(`/meeting/${id}`)}
            onError={(err) => {
              setError(err);
              setImportJobId(null);
            }}
          />
        </div>
      )}

      {searched && (
        <div style={{ marginBottom: 24 }}>
          <div className="section-head" style={{ marginTop: 0 }}>
            <SearchIcon size={16} />
            <h2>
              {results.length} result{results.length === 1 ? "" : "s"} for
              “{query}”
            </h2>
          </div>
          {results.map((r, i) => (
            <Link key={i} href={`/meeting/${r.meeting_id}`} className="card card-link">
              <strong>{r.title}</strong>
              <div className="muted" style={{ marginTop: 4 }}>
                {r.transcript.slice(0, 160)}…
              </div>
            </Link>
          ))}
        </div>
      )}

      {loading && (
        <div className="col">
          {[0, 1, 2].map((i) => (
            <div className="card" key={i}>
              <div className="meeting-row">
                <div className="skeleton avatar" style={{ borderRadius: 12 }} />
                <div className="grow col" style={{ gap: 8 }}>
                  <div className="skeleton" style={{ height: 14, width: "40%" }} />
                  <div className="skeleton" style={{ height: 11, width: "22%" }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && meetings.length === 0 && !error && (
        <div className="empty card pad-lg">
          <div className="empty-icon">
            <ListIcon size={24} />
          </div>
          <h3>No meetings yet</h3>
          <p>Start a recording or import an audio file to get going.</p>
          <Link href="/record" className="btn" style={{ marginTop: 8 }}>
            <PlusIcon size={16} />
            New recording
          </Link>
        </div>
      )}

      {!loading && !searched && meetings.length > 0 && (
        <div className="col">
          {meetings.map((m) => (
            <div className="card card-link" key={m.id}>
              <div className="meeting-row">
                <div className="avatar">{initials(m.title)}</div>
                <Link href={`/meeting/${m.id}`} className="meta">
                  <div className="title">{m.title}</div>
                  <div className="sub">Tap to open transcript & summary</div>
                </Link>
                <div className="actions">
                  <button
                    className={`btn ${confirmId === m.id ? "danger" : "ghost"} sm`}
                    onClick={() => onDelete(m.id)}
                    onBlur={() => setConfirmId(null)}
                  >
                    <TrashIcon size={15} />
                    {confirmId === m.id ? "Confirm delete" : "Delete"}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
