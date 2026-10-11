import { useEffect, useRef, useState } from 'react';
import { api, allPages, ApiError, type User, type Project } from './api';
import { DayEditor } from './DayEditor';
import { DayTable, Modal, TaskPicker } from './TimeComponents';
import { type Day, type SheetContext, type PickerTask, type PickerStatus, instant, localStamp, hours } from './timesheet';

type Command = Record<string, unknown>;
interface Preview { domain_revision: number; before: Day; after: Day; advice: string }
export function Timesheet({ user, version, request, openTask, onError }: {
  user: User; version: number; request: { id: string; nonce: number } | null;
  openTask: (id: string) => void; onError: (error: unknown) => void;
}) {
  const [owner, setOwner] = useState(user.id);
  const [people, setPeople] = useState<{ id: string; display_name: string }[]>([]);
  const [date, setDate] = useState('');
  const [context, setContext] = useState<SheetContext | null>(null);
  const [day, setDay] = useState<Day | null>(null);
  const [catalog, setCatalog] = useState<{ tasks: PickerTask[]; projects: Project[]; statuses: PickerStatus[] }>({ tasks: [], projects: [], statuses: [] });
  const [task, setTask] = useState('');
  const [session, setSession] = useState('');
  const [at, setAt] = useState('');
  const [useNow, setUseNow] = useState(true);
  const [continuation, setContinuation] = useState('');
  const [edit, setEdit] = useState(false);
  const [pending, setPending] = useState<{ body: Command; preview: Preview } | null>(null);
  const [boundary, setBoundary] = useState<{ entry: string; edge: 'start' | 'end'; at: string } | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(false);
  const lock = useRef(false);
  const generation = useRef(0);
  const loadedKey = useRef('');
  const form = useRef<HTMLFormElement>(null);
  const errorHandler = useRef(onError); errorHandler.current = onError;
  const readable = owner === user.id || user.read_others_timesheets;
  const writable = owner === user.id || user.write_others_timesheets;

  function failed(error: unknown) {
    setMessage(error instanceof Error ? error.message : 'Request failed.');
    if (error instanceof ApiError) {
      if (['stale_revision', 'stale_preview'].includes(error.code)) { setStale(true); setPending(null); }
      if (error.code === 'permission_denied') { setStale(true); setPending(null); }
      if (error.code === 'authentication_required') errorHandler.current(error);
    }
  }
  useEffect(() => {
    let current = true;
    allPages<{ id: string; display_name: string }>('timesheets/').then(result => { if (current) { setPeople(result); if (!result.some(p => p.id === owner)) setOwner(user.id); } }).catch(error => { if (current) failed(error); });
    return () => { current = false; };
  }, [version, user.id, user.read_others_timesheets, user.write_others_timesheets, owner]);

  async function catalogs() {
    const [tasks, projects, statuses] = await Promise.all([allPages<PickerTask>('tasks/'), allPages<Project>('projects/'), allPages<PickerStatus>('statuses/')]);
    return { tasks, projects, statuses };
  }
  useEffect(() => {
    let current = true;
    catalogs().then(value => { if (current) { setCatalog(value); setTask(id => value.tasks.some(t => t.id === id) ? id : ''); } }).catch(error => { if (current) failed(error); });
    return () => { current = false; };
  }, [version]);

  async function load(selectedDate = date) {
    const token = ++generation.current;
    const meta = await api<SheetContext>(`timesheets/${owner}/context/`);
    const selected = selectedDate || meta.today;
    const result = await api<Day>(`timesheets/${owner}/days/${selected}/`);
    if (token === generation.current) {
      loadedKey.current = `${owner}:${selected}:${version}`;
      setContext(meta); setDate(selected); setDay(result); setStale(false);
      setSession(result.sessions.at(-1)?.id ?? '');
    }
    return result;
  }
  useEffect(() => {
    if (readable && loadedKey.current === `${owner}:${date}:${version}`) return;
    loadedKey.current = '';
    setDay(null); setContext(null); setPending(null); setBoundary(null); setStale(false); setMessage('');
    if (readable) void load().catch(failed);
    return () => { generation.current++; };
  }, [owner, date, version, readable]);

  useEffect(() => {
    if (context) { setUseNow(date === context.today); setAt(date === context.today ? localStamp(new Date().toISOString(), context.time_zone) : `${date}T09:00:00`); }
  }, [date, context?.time_zone, context?.today]);
  useEffect(() => {
    if (!request) return;
    setTask(request.id);
    form.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    form.current?.querySelector<HTMLButtonElement>('[data-record]')?.focus();
  }, [request]);

  async function run(operation: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setMessage('');
    try { await operation(); } catch (error) { failed(error); } finally { lock.current = false; setBusy(false); }
  }
  function payload(command: string, extra: Command): Command {
    return { command, date, expected_revision: day!.revision, ...extra };
  }
  async function send(body: Command) {
    await api(`timesheets/${owner}/commands/`, 'POST', body);
    setPending(null); setBoundary(null); await load(); setMessage('Timesheet saved.');
  }
  async function preview(body: Command) {
    const result = await api<Preview>(`timesheets/${owner}/commands/preview/`, 'POST', body);
    setBoundary(null); setPending({ body, preview: result });
  }
  function timestamp() {
    if (!context) throw new Error('Load the timesheet first.');
    const result = date === context.today && useNow ? new Date().toISOString() : instant(at, context.time_zone);
    if (!result) throw new Error('Enter a time on the selected day.');
    return result;
  }
  function record(taskId: string | null, atOverride?: string) {
    if (!day || !writable || stale) return;
    void run(async () => {
      if (taskId === '') throw new Error('Choose a readable task first.');
      const target = day.sessions.find(s => s.id === session);
      const time = atOverride ?? timestamp();
      if (target?.state === 'closed') await preview(payload('resume', { session, at: time, task: taskId }));
      else await send(payload(target ? 'append' : 'start', { ...(target ? { session } : {}), at: time, task: taskId }));
    });
  }
  return <section className="workspace timesheet-panel" aria-label="Timesheet" onDragOver={event => { if (writable && day && !stale && event.dataTransfer.types.includes('application/x-task-tracker-task')) event.preventDefault(); }} onDrop={event => {
    event.preventDefault(); const id = event.dataTransfer.getData('application/x-task-tracker-task');
    if (!id || !writable || !day || stale || busy) return;
    setTask(id);
    if (context && date === context.today) record(id, new Date().toISOString());
    else { setMessage('Task selected. Enter a start time on the selected day, then choose Record task.'); form.current?.querySelector<HTMLInputElement>('input[type="datetime-local"]')?.focus(); }
  }}>
    <h2>Timesheet</h2><p>Drop a task here or use the picker. Daily totals include the whole timesheet, across all projects.</p>
    {message && <p role="alert">{message}</p>}
    <label>Timesheet person<select value={owner} disabled={busy} onChange={event => { setDay(null); setOwner(event.target.value); }}><option value={user.id}>My timesheet</option>{people.filter(p => p.id !== user.id).map(p => <option value={p.id} key={p.id}>{p.display_name}</option>)}</select></label>
    {!readable ? <p>Reading this timesheet requires Read Others’ Timesheets. Write-only commands remain available through the revision-aware API.</p> : <>
      <label>Day<input type="date" value={date} disabled={busy} onChange={event => { if (event.target.value) { setDay(null); setDate(event.target.value); } }} /></label>
      <button className="secondary" disabled={busy} onClick={() => { void run(async () => { await load(); setCatalog(await catalogs()); setMessage('Timesheet reloaded. Review current work before making changes.'); }); }}>Reload timesheet</button>
      {!day || !context ? <p>Loading timesheet…</p> : <>
        <p>Working time zone: {day.time_zone}. Total: <strong>{hours(day.work_seconds)}</strong>. Unfinished rows count zero until closed.</p>
        {day.unfinished && <p className="draft-warning" role="status">Unfinished: this day has a row without an end time. Only closed task intervals contribute to its partial total.</p>}
        {context.open_sessions.filter(s => s.date !== date).map(s => <p key={s.id}>{s.state === 'active' ? 'Active recording' : 'Unfinished session'} on <button className="task-link" onClick={() => setDate(s.date)}>{s.date}</button> · {s.tail.task_label} · no end recorded.</p>)}
        <DayTable day={day} openTask={openTask} boundary={writable && !busy && !stale ? (entry, edge, at) => setBoundary({ entry, edge, at: localStamp(at, day.time_zone) }) : undefined} remove={writable && !busy && !stale ? entry => { void run(() => preview(payload('delete_last', { entry }))); } : undefined} />
        {stale && <p role="status">Access or data changed. Reload timesheet and review before making another change.</p>}
        {writable && <>
          <button className="secondary" disabled={busy || stale} onClick={() => setEdit(true)}>Edit day…</button>
          <form ref={form} aria-label="Record work" onSubmit={event => { event.preventDefault(); record(task); }}><fieldset disabled={busy || stale}>
            <h3>Record work</h3>
            {day.sessions.length > 0 && <label>Target session<select value={session} onChange={event => setSession(event.target.value)}>{day.sessions.map((s, i) => <option key={s.id} value={s.id}>Session {i + 1} · {s.state}</option>)}</select></label>}
            {date === context.today && <label className="check"><input type="checkbox" checked={useNow} onChange={event => setUseNow(event.target.checked)} />Use current time</label>}
            {!(date === context.today && useNow) && <label>Selected-day time<input type="datetime-local" step="any" value={at} onChange={event => setAt(event.target.value)} required /></label>}
            <TaskPicker {...catalog} value={task} onChange={setTask} prefix="Recording picker" />
            {day.sessions.find(s => s.id === session)?.state === 'closed' && <p>Adding work after End of Working Day requires confirmation to convert the marker to a break.</p>}
            <div className="inline"><button data-record disabled={!task}>Record task</button><button type="button" className="secondary" onClick={() => record(null)}>Break</button>
              {day.sessions.find(s => s.id === session)?.state !== 'closed' && session && <button type="button" onClick={() => { void run(() => send(payload('end_day', { session, at: timestamp() }))); }}>End of Working Day</button>}
            </div>
            {date === context.today && context.open_sessions.some(s => s.date < date) && <fieldset className="continuation"><legend>Continue previous session…</legend><p>Starting today normally creates an independent session. Continue only for real overnight work; the previous open interval will be closed at the supplied time.</p>
              <label>Previous session<select value={continuation} onChange={event => setContinuation(event.target.value)}><option value="">Choose an unfinished session</option>{context.open_sessions.filter(s => s.date < date).map(s => <option value={s.id} key={s.id}>{s.date} · {s.tail.task_label} · {s.state}</option>)}</select></label>
              <button type="button" disabled={!continuation || !task} onClick={() => { void run(() => send(payload('continue', { session: continuation, at: timestamp(), task }))); }}>Continue previous session</button>
              {context.open_sessions.some(s => s.state === 'active' && s.date < date) && <button type="button" className="secondary" onClick={() => { const active = context.open_sessions.find(s => s.state === 'active' && s.date < date)!; void run(() => send(payload('end_day', { session: active.id, at: timestamp() }))); }}>Close overnight recording</button>}
            </fieldset>}
          </fieldset></form>
        </>}
        {edit && <DayEditor owner={owner} day={day} {...catalog} onClose={() => setEdit(false)} onError={onError} onSaved={async () => { await load(); setMessage('Day changes saved.'); }} onReload={async () => { const result = await load(); setCatalog(await catalogs()); return result; }} />}
      </>}
    </>}
    {boundary && <Modal name="Edit time boundary" onDismiss={() => { if (!busy) setBoundary(null); }}><h3>Edit shared {boundary.edge} boundary</h3><p>The adjoining row will change together. Midnight connections stay fixed.</p><form onSubmit={event => { event.preventDefault(); void run(async () => { const at = instant(boundary.at, day!.time_zone); if (!at) throw new Error('Enter a boundary time.'); await preview(payload('boundary', { entry: boundary.entry, edge: boundary.edge, at })); }); }}><label>Boundary time<input type="datetime-local" step="any" value={boundary.at} onChange={event => setBoundary({ ...boundary, at: event.target.value })} required /></label><button disabled={busy}>Preview boundary change</button><button type="button" className="secondary" disabled={busy} onClick={() => setBoundary(null)}>Cancel boundary</button>{message && <p role="alert">{message}</p>}</form></Modal>}
    {pending && <Modal name="Confirm timesheet change" onDismiss={() => { if (!busy) setPending(null); }}><h3>Review timesheet change</h3><p>{pending.preview.advice}</p><h4>Before</h4><DayTable day={pending.preview.before} /><h4>After</h4><DayTable day={pending.preview.after} />
      {message && <p role="alert">{message}</p>}<button disabled={busy} onClick={() => { void run(() => send({ ...pending.body, confirm: true, expected_domain_revision: pending.preview.domain_revision })); }}>{busy ? 'Applying…' : 'Confirm timesheet change'}</button><button className="secondary" disabled={busy} onClick={() => setPending(null)}>Cancel change</button>
    </Modal>}
  </section>;
}
