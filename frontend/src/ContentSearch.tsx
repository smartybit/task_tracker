import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, ApiError } from './api';
import { type OpenReference } from './Content';

type Match = { kind: string; id: string; task: string; label: string; snippets: string[] };
type Results = { count: number; next: number | null; results: Match[] };

export function ContentSearch({ version, onOpen, onError }: { version: number; onOpen: OpenReference; onError: (error: unknown) => void }) {
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<Results | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const generation = useRef(0);
  useEffect(() => { generation.current += 1; setResult(null); setMessage(''); setBusy(false); return () => { generation.current += 1; }; }, [version]);
  async function search(value: string, page = 1) {
    const request = ++generation.current;
    setBusy(true); setMessage(''); setResult(null); setQuery(value);
    try {
      const response = await api<Results>(`search/?q=${encodeURIComponent(value)}&page=${page}`);
      if (request === generation.current) setResult(response);
    } catch (error) {
      if (request === generation.current) {
        setMessage(error instanceof Error ? error.message : 'Search failed. Try again.');
        if (error instanceof ApiError && error.code === 'authentication_required') onError(error);
      }
    } finally { if (request === generation.current) setBusy(false); }
  }
  function submit(event: FormEvent) { event.preventDefault(); void search(draft.trim()); }
  return <section className="content-search" aria-label="Content search">
    <form aria-label="Search content" onSubmit={submit}><fieldset disabled={busy}>
      <label>Search tasks and remarks<input type="search" value={draft} onChange={event => setDraft(event.target.value)} maxLength={200} required /></label>
      <button disabled={!draft.trim()}>Search content</button>
    </fieldset></form>
    <p className="content-help">English and Russian word forms, including mixed text. Results require all search words in one task or remark.</p>
    {busy && <p role="status">Searching…</p>}{message && <p role="alert">{message}</p>}
    {result && <><p role="status">{result.count} results for “{query}”</p>
      <ol aria-label="Search results">{result.results.map(row => <li key={`${row.kind}:${row.id}`}>
        <button className="task-link" onClick={() => onOpen(row.task, row.kind === 'remark' ? row.id : undefined)}>{row.kind === 'remark' ? 'Remark in ' : 'Task: '}{row.label}</button>
        {row.snippets.map((snippet, index) => <p className="description" key={index}>{snippet}</p>)}
      </li>)}</ol>
      {result.next && <button className="secondary" onClick={() => void search(query, result.next!)}>Next search page</button>}
      {!result.results.length && <p>No readable content matches these words.</p>}
    </>}
  </section>;
}
