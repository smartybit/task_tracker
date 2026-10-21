import { useEffect, useRef, useState } from 'react';
import { api, ApiError, type Project } from './api';
import { Modal, TaskPicker } from './TimeComponents';
import { type Day, type PickerTask, type PickerStatus, instant, localStamp, nextDate } from './timesheet';

let nextDraftKey = 0;
const draftKey = () => `draft-${Date.now()}-${++nextDraftKey}`;

interface DraftRow {
  key: string; id?: string; kind: 'task' | 'break'; task: string | null; label: string;
  start: string; end: string; originalStart?: string; originalEnd?: string | null;
}
interface DraftSession {
  key: string; id?: string; state: 'active' | 'unfinished' | 'closed'; marker: string;
  before: boolean; after: boolean; rows: DraftRow[];
}
function copyDay(day: Day): DraftSession[] {
  return day.sessions.map(s => ({ key: s.id, id: s.id, state: s.state, marker: s.ended_at ? localStamp(s.ended_at, day.time_zone) : '', before: s.continues_before, after: s.continues_after,
    rows: s.rows.map(r => ({ key: r.id, id: r.id, kind: r.kind, task: r.task, label: r.task_label, start: localStamp(r.started_at, day.time_zone), end: r.ended_at ? localStamp(r.ended_at, day.time_zone) : '', originalStart: r.started_at, originalEnd: r.ended_at })) }));
}
function chronological(rows: DraftRow[]): DraftRow[] {
  return [...rows].sort((a, b) => !a.start && !b.start ? 0 : !a.start ? 1 : !b.start ? -1 : a.start.localeCompare(b.start));
}
function messages(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(messages);
  if (value && typeof value === 'object') return Object.values(value).flatMap(messages);
  return [];
}
function issues(sessions: DraftSession[], day: string): Record<string, string[]> {
  const result: Record<string, string[]> = {};
  const add = (key: string, message: string) => { (result[key] ??= []).push(message); };
  const midnight = `${day}T00:00:00`;
  const next = `${nextDate(day)}T00:00:00`;
  const numeric = (value: string) => Date.parse(`${value}Z`);
  const same = (a: string, b: string) => numeric(a) === numeric(b);
  const known: DraftRow[] = [];
  for (const session of sessions) {
    const rows = chronological(session.rows);
    if (!rows.length) add(session.key, 'Remove this independent session or add rows.');
    rows.forEach((r, index) => {
      if (!r.start || !Number.isFinite(numeric(r.start))) add(r.key, 'Enter a start time.');
      else if (numeric(r.start) < numeric(midnight) || numeric(r.start) >= numeric(next)) add(r.key, 'Start must be on the selected day.');
      if (r.kind === 'task' && !r.task) add(r.key, 'Choose a task.');
      if (r.end && numeric(r.end) <= numeric(r.start)) add(r.key, 'End must follow start.');
      if (r.end && numeric(r.end) > numeric(next)) add(r.key, 'End must not pass midnight.');
      if (index < rows.length - 1 && r.start && rows[index + 1].start && !same(r.end, rows[index + 1].start)) {
        const overlap = r.end && numeric(r.end) > numeric(rows[index + 1].start);
        add(r.key, overlap ? 'Overlap with the next row.' : 'Gap before the next row; add an explicit break.');
      }
      if (r.start && r.end) known.push(r);
    });
    const first = rows[0], last = rows.at(-1);
    if (session.before && first && !same(first.start, midnight)) add(first.key, 'Incoming midnight boundary is fixed.');
    if (session.after && last && !same(last.end, next)) add(last.key, 'Outgoing midnight boundary is fixed.');
    if (!session.after && last) {
      if (session.state === 'closed' && (!session.marker || !same(session.marker, last.end))) add(last.key, 'End of Working Day must match the last end time.');
      if (session.state !== 'closed' && (last.end || session.marker)) add(last.key, 'An active or unfinished session needs an open last row and no closing marker.');
    }
  }
  known.sort((a, b) => numeric(a.start) - numeric(b.start));
  known.forEach((r, index) => { if (index && numeric(known[index - 1].end) > numeric(r.start)) add(r.key, 'Known work overlaps another row.'); });
  return result;
}

export function DayEditor({ owner, day, tasks, projects, statuses, onSaved, onClose, onReload, onError }: {
  owner: string; day: Day; tasks: PickerTask[]; projects: Project[]; statuses: PickerStatus[];
  onSaved: () => Promise<void>; onClose: () => void; onReload: () => Promise<Day>; onError: (error: unknown) => void;
}) {
  const [base, setBase] = useState(day);
  const [draft, setDraft] = useState(() => copyDay(day));
  const [initial, setInitial] = useState(() => JSON.stringify(copyDay(day)));
  const [error, setError] = useState('');
  const [fields, setFields] = useState<Record<string, unknown>>({});
  const [stale, setStale] = useState(false);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [picker, setPicker] = useState<{ session: string; row: string } | null>(null);
  const dirty = initial !== JSON.stringify(draft);
  const warnings = issues(draft, base.date);
  useEffect(() => {
    function prevent(event: BeforeUnloadEvent) { if (dirty) event.preventDefault(); }
    window.addEventListener('beforeunload', prevent);
    return () => window.removeEventListener('beforeunload', prevent);
  }, [dirty]);
  function dismiss() { if (!lock.current && (!dirty || window.confirm('Discard unsaved day changes?'))) onClose(); }
  function editSession(key: string, update: Partial<DraftSession>) {
    setDraft(value => value.map(s => s.key === key ? { ...s, ...update } : s)); setFields({});
  }
  function editRow(sid: string, rid: string, update: Partial<DraftRow>) {
    setDraft(value => value.map(s => s.key === sid ? { ...s, rows: s.rows.map(r => r.key === rid ? { ...r, ...update } : r) } : s)); setFields({});
  }
  function sort(sid: string, target: EventTarget | null) {
    setDraft(value => value.map(s => s.key === sid ? { ...s, rows: chronological(s.rows) } : s));
    // React retains keyed inputs; restore the next keyboard target if a DOM move blurred it.
    requestAnimationFrame(() => { if (target instanceof HTMLElement && target.isConnected) target.focus(); });
  }
  const textErrors = (key: string) => [...(warnings[key] ?? []), ...messages(fields[key])];
  async function save() {
    if (lock.current || stale) return;
    lock.current = true; setBusy(true); setError(''); setFields({});
    let committed = false;
    try {
      const timestamp = (value: string, original?: string | null) => original && localStamp(original, base.time_zone) === value ? original : instant(value, base.time_zone);
      const sessions = draft.map(s => ({ ...(s.id ? { id: s.id } : { client_key: s.key }), state: s.state, ended_at: timestamp(s.marker, base.sessions.find(original => original.id === s.id)?.ended_at), rows: s.rows.map(r => {
        const start = timestamp(r.start, r.originalStart);
        if (!start) throw new Error('Complete each start time before saving. The draft is preserved.');
        return { ...(r.id ? { id: r.id } : { client_key: r.key }), kind: r.kind, task: r.task, started_at: start, ended_at: timestamp(r.end, r.originalEnd) };
      }) }));
      await api(`timesheets/${owner}/commands/`, 'POST', { command: 'replace_day', date: base.date, expected_revision: base.revision, sessions });
      committed = true; setInitial(JSON.stringify(draft));
      await onSaved(); onClose();
    } catch (failure) {
      const detail = failure instanceof Error ? failure.message : 'Request failed. Your draft is preserved.';
      setError(committed ? `Day changes were saved, but reload failed. ${detail}` : detail);
      if (committed) setStale(true);
      if (failure instanceof ApiError) { setFields(failure.fields); if (['stale_revision', 'permission_denied', 'not_found'].includes(failure.code)) setStale(true); if (failure.code === 'authentication_required') onError(failure); }
    } finally { lock.current = false; setBusy(false); }
  }
  return <Modal name={picker ? "Choose draft task" : "Edit day"} onDismiss={() => { if (picker) setPicker(null); else dismiss(); }}>
    <div hidden={!!picker}>
    <h2>Edit day · {base.date}</h2><p>All times use {base.time_zone}. Add, remove, and change rows freely. Fill internal gaps with Break rows; stored work changes only after a valid Save changes.</p>
    {error && <p role="alert">{error}</p>}
    {Object.keys(warnings).length > 0 && <p className="draft-warning" role="status">Draft needs review: highlighted rows have gaps, overlaps, or incomplete values.</p>}
    {stale && <p role="status">Your draft is preserved. Reload the day and review current work before saving again.</p>}
    <fieldset disabled={busy}>
      {draft.map((session, si) => <section className="draft-session" key={session.key} aria-label={`Draft session ${si + 1}`}>
        <h3>Session {si + 1}</h3>
        {(session.before || session.after) && <p>Connected overnight work: {session.before && 'incoming midnight is fixed. '}{session.after && 'outgoing midnight and lifecycle are fixed.'} Edit neighboring days separately.</p>}
        <label>Session state<select value={session.state} disabled={session.after} onChange={event => editSession(session.key, { state: event.target.value as DraftSession['state'] })}>{(base.sessions.find(s => s.id === session.id)?.state === 'active') && <option value="active">Active</option>}<option value="unfinished">Unfinished</option><option value="closed">Closed</option></select></label>
        <div className="time-table-wrap"><table className="draft-table"><caption>Draft session {si + 1}</caption><thead><tr><th>Task</th><th>Start Time</th><th>End Time</th><th>Actions</th></tr></thead><tbody>
          {session.rows.map((row, ri) => <tr key={row.key} className={textErrors(row.key).length ? 'invalid-row' : ''}>
            <td><label>Row {ri + 1} type<select value={row.kind} onChange={event => editRow(session.key, row.key, { kind: event.target.value as DraftRow['kind'], task: null, label: 'Break' })}><option value="task">Task</option><option value="break">Break</option></select></label>
              {row.kind === 'task' && <><span>{tasks.find(t => t.id === row.task)?.title ?? row.label ?? 'Choose a task'}</span><button type="button" className="secondary compact" onClick={() => setPicker({ session: session.key, row: row.key })}>Choose task for row {ri + 1}</button></>}
              {textErrors(row.key).length > 0 && <ul className="row-errors" id={`errors-${row.key}`}>{textErrors(row.key).map((message, i) => <li key={i}>{message}</li>)}</ul>}</td>
            <td><input aria-label={`Row ${ri + 1} start`} aria-invalid={textErrors(row.key).length > 0} aria-describedby={textErrors(row.key).length ? `errors-${row.key}` : undefined} type="datetime-local" step="any" value={row.start} disabled={ri === 0 && session.before} onChange={event => editRow(session.key, row.key, { start: event.target.value })} onBlur={event => sort(session.key, event.relatedTarget)} /></td>
            <td><input aria-label={`Row ${ri + 1} end`} aria-invalid={textErrors(row.key).length > 0} type="datetime-local" step="any" value={row.end} disabled={ri === session.rows.length - 1 && session.after} onChange={event => editRow(session.key, row.key, { end: event.target.value })} onBlur={event => sort(session.key, event.relatedTarget)} /></td>
            <td><button type="button" className="secondary compact" onClick={() => editSession(session.key, { rows: session.rows.filter(r => r.key !== row.key) })}>Remove row {ri + 1}</button></td>
          </tr>)}
        </tbody></table></div>
        {textErrors(session.key).length > 0 && <p className="row-errors">{textErrors(session.key).join(' ')}</p>}
        <button type="button" className="secondary" onClick={() => editSession(session.key, { rows: [...session.rows, { key: draftKey(), kind: 'break', task: null, label: 'Break', start: '', end: '' }] })}>Add row to session {si + 1}</button>
        <label>End of Working Day<input type="datetime-local" step="any" value={session.marker} disabled={session.after} onChange={event => editSession(session.key, { marker: event.target.value })} /></label>
        {!session.before && !session.after && <button type="button" className="danger" onClick={() => setDraft(value => value.filter(s => s.key !== session.key))}>Remove session {si + 1}</button>}
      </section>)}
      <button type="button" className="secondary" onClick={() => setDraft(value => [...value, { key: draftKey(), state: 'unfinished', marker: '', before: false, after: false, rows: [{ key: draftKey(), kind: 'break', task: null, label: 'Break', start: '', end: '' }] }])}>Add independent session</button>
      <p>Active and unfinished last rows may have a blank end. Independent days can be cleared by removing their sessions.</p>
      <div className="inline"><button type="button" disabled={stale} onClick={() => void save()}>{busy ? 'Saving…' : 'Save changes'}</button><button type="button" className="secondary" onClick={dismiss}>Cancel</button>
        {stale && <button type="button" className="secondary" onClick={() => {
          if (dirty && !window.confirm('Discard this draft and reload the latest day for review?')) return;
          if (lock.current) return;
          lock.current = true; setBusy(true);
          void onReload().then(current => { setBase(current); const next = copyDay(current); setDraft(next); setInitial(JSON.stringify(next)); setFields({}); setError('Current day loaded. Review before saving.'); setStale(false); }).catch(failure => setError(failure instanceof Error ? failure.message : 'Reload failed; draft preserved.')).finally(() => { lock.current = false; setBusy(false); });
        }}>Reload day and discard draft</button>}
      </div>
    </fieldset>
    </div>
    {picker && <section><h3>Choose task for draft row</h3><TaskPicker tasks={tasks} projects={projects} statuses={statuses} value={draft.find(s => s.key === picker.session)?.rows.find(r => r.key === picker.row)?.task ?? ''} onChange={task => { editRow(picker.session, picker.row, { task, label: tasks.find(t => t.id === task)?.title ?? '' }); }} prefix="Draft picker" /><button onClick={() => setPicker(null)}>Done choosing task</button></section>}
  </Modal>;
}
