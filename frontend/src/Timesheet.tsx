import { useEffect, useRef, useState } from 'react';
import { api, allPages, ApiError, type User, type Project } from './api';
import { DayEditor } from './DayEditor';
import { DayTable, Modal, TaskPicker } from './TimeComponents';
import { type Day, type SheetContext, type PickerTask, type PickerStatus, instant, localStamp, hours } from './timesheet';

type Command = Record<string, unknown>;
interface Preview { domain_revision: number; before?: Day; after?: Day; advice: string }
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
  const [tool, setTool] = useState<'record' | 'break' | 'end' | 'continue' | null>(null);
  const [dirty, setDirty] = useState(false);
  const [dragging, setDragging] = useState(false);
  function dismiss() {
    if (busy) return;
    if (pending) { setPending(null); return; }
    if (dirty && !window.confirm('Discard unsaved recording changes?')) return;
    setTool(null); setBoundary(null); setDirty(false);
  }
  function openTool(next: 'record' | 'break' | 'end' | 'continue') { setTool(next); setDirty(false); setMessage(''); setUseNow(date === context?.today); if (day && day.sessions.length > 1) setSession(''); }
  const [edit, setEdit] = useState(false);
  const [pending, setPending] = useState<{ body: Command; preview: Preview & { before: Day; after: Day } } | null>(null);
  const [boundary, setBoundary] = useState<{ entry: string; edge: 'start' | 'end'; at: string; original: string } | null>(null);
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
    openTool('record');
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
    setPending(null); setBoundary(null); setTool(null); setDirty(false);
    try { await load(); setMessage('Timesheet saved.'); }
    catch (error) {
      setStale(true);
      const message = `Timesheet was saved, but reload failed. ${error instanceof Error ? error.message : 'Reload and review current work.'}`;
      throw error instanceof ApiError ? new ApiError(error.code, message, error.fields) : new Error(message);
    }
  }
  async function preview(body: Command) {
    const result = await api<Preview>(`timesheets/${owner}/commands/preview/`, 'POST', body);
    if (!result.before || !result.after) throw new ApiError('permission_denied', 'Timesheet read access changed. Refresh access before reviewing this change.');
    setBoundary(null); setPending({ body, preview: { ...result, before: result.before, after: result.after } });
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
      if (day.sessions.length > 1 && !session) throw new Error('Choose the target session.');
      const target = day.sessions.find(s => s.id === session);
      const time = atOverride ?? timestamp();
      if (target?.state === 'closed') await preview(payload('resume', { session, at: time, task: taskId }));
      else await send(payload(target ? 'append' : 'start', { ...(target ? { session } : {}), at: time, task: taskId }));
    });
  }
  return <section className={`workspace timesheet-panel${dragging ? " drag-target" : ""}`} onDragEnter={() => setDragging(true)} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false); }} aria-label="Timesheet" onDragOver={event => { if (writable && day && !stale && event.dataTransfer.types.includes('application/x-task-tracker-task')) event.preventDefault(); }} onDrop={event => {
    event.preventDefault(); setDragging(false); const id = event.dataTransfer.getData('application/x-task-tracker-task');
    if (!id || !writable || !day || stale || busy) return;
    setTask(id);
    if (context && date === context.today && day.sessions.length <= 1) record(id, new Date().toISOString());
    else { openTool('record'); }
  }}>
    <h2>Timesheet</h2><p className="drop-hint">Drop a task here to record work.</p>
    {!tool && !boundary && !pending && message && <p role="alert">{message}</p>}
    <label>Timesheet person<select value={owner} disabled={busy} onChange={event => { setDay(null); setOwner(event.target.value); }}><option value={user.id}>My timesheet</option>{people.filter(p => p.id !== user.id).map(p => <option value={p.id} key={p.id}>{p.display_name}</option>)}</select></label>
    {!readable ? <p>Reading this timesheet requires Read Others’ Timesheets.</p> : <>
      <label>Day<input type="date" value={date} disabled={busy} onChange={event => { if (event.target.value) { setDay(null); setDate(event.target.value); } }} /></label>
      <button className="secondary" disabled={busy} onClick={() => { void run(async () => { await load(); setCatalog(await catalogs()); setMessage('Timesheet reloaded. Review current work before making changes.'); }); }}>Reload timesheet</button>
      {!day || !context ? <p>Loading timesheet…</p> : <>
        <p>Working time zone: {day.time_zone}. Total (all projects): <strong>{hours(day.work_seconds)}</strong>.</p>
        {day.unfinished && <p className="draft-warning" role="status">Unfinished: this day has a row without an end time. Only closed task intervals contribute to its partial total.</p>}
        {context.open_sessions.filter(s => s.date !== date).map(s => <p key={s.id}>{s.state === 'active' ? 'Active recording' : 'Unfinished session'} on <button className="task-link" onClick={() => setDate(s.date)}>{s.date}</button> · {s.tail.task_label} · no end recorded.</p>)}
        <DayTable day={day} openTask={openTask} boundary={writable && !busy && !stale ? (entry, edge, at) => (setDirty(false), setBoundary({ entry, edge, at: localStamp(at, day.time_zone), original: at })) : undefined} remove={writable && !busy && !stale ? entry => { void run(() => preview(payload('delete_last', { entry }))); } : undefined} />
        {stale && <p role="status">Access or data changed. Reload timesheet and review before making another change.</p>}
        {writable && <>
          <button className="secondary" disabled={busy || stale} onClick={() => setEdit(true)}>Edit day…</button>
          <button className="secondary" disabled={busy || stale} onClick={() => openTool('record')}>Record work…</button>
          <button className="secondary" disabled={busy || stale} onClick={() => {
            if (date !== context.today || day.sessions.length > 1) openTool('break'); else record(null, new Date().toISOString());
          }}>Break</button>
          {day.sessions.length > 0 && <button disabled={busy || stale || day.sessions.every(s => s.state === 'closed')} onClick={() => {
            if (date !== context.today || day.sessions.length > 1) openTool('end');
            else { void run(() => send(payload('end_day', { session, at: new Date().toISOString() }))); }
          }}>End of Working Day</button>}
          {date === context.today && context.open_sessions.some(s => s.date < date) && <button className="secondary" disabled={busy || stale} onClick={() => openTool('continue')}>Overnight work…</button>}
        </>}
        {edit && <DayEditor owner={owner} day={day} {...catalog} onClose={() => setEdit(false)} onError={onError} onSaved={async () => { try { await load(); setMessage('Day changes saved.'); } catch (error) { setStale(true); throw error; } }} onReload={async () => { const result = await load(); setCatalog(await catalogs()); return result; }} />}
      </>}
    </>}
    {(tool || boundary || pending) && day && context && <Modal name={pending ? 'Confirm timesheet change' : boundary ? 'Edit time boundary' : tool === 'continue' ? 'Overnight work' : tool === 'break' ? 'Record break' : tool === 'end' ? 'End of Working Day' : 'Record work'} dirty={dirty} onDismiss={dismiss}>
      {message && <p role="alert">{message}</p>}
      {stale && <p role="status">Access or data changed. Close this window, reload the timesheet and review before saving again. Your input is retained until you close.</p>}
      <div hidden={!!pending}>
      {tool && <form ref={form} aria-label="Record work" onChange={() => setDirty(true)} onSubmit={event => {
        event.preventDefault();
        if (tool === 'end') { void run(() => send(payload('end_day', { session, at: timestamp() }))); }
        else if (tool === 'continue') { void run(() => send(payload('continue', { session: continuation, at: timestamp(), task }))); }
        else record(tool === 'break' ? null : task);
      }}><fieldset disabled={busy || stale}>
        <h3>{tool === 'continue' ? 'Overnight work' : tool === 'break' ? 'Record break' : tool === 'end' ? 'End of Working Day' : 'Record work'}</h3>
        <p>{date} · {context.time_zone}</p>
        {day.sessions.length > 0 && tool !== 'continue' && <label>Target session<select value={session} required onChange={event => setSession(event.target.value)}><option value="" disabled>Choose a session</option>{day.sessions.map((s, i) => <option key={s.id} value={s.id} disabled={tool === 'end' && s.state === 'closed'}>Session {i + 1} · {s.state}</option>)}</select></label>}
        {date === context.today && <label className="check"><input type="checkbox" checked={useNow} onChange={event => setUseNow(event.target.checked)} />Use current time</label>}
        {!(date === context.today && useNow) && <label>Selected-day time<input type="datetime-local" step="any" value={at} onChange={event => setAt(event.target.value)} required /></label>}
        {(tool === 'record' || tool === 'continue') && <TaskPicker {...catalog} value={task} onChange={setTask} prefix="Recording picker" />}
        {tool === 'record' && day.sessions.find(s => s.id === session)?.state === 'closed' && <p>Adding work after End of Working Day requires confirmation to convert the marker to a break.</p>}
        {tool === 'continue' && <><p>Continue only for real overnight work. Starting today normally leaves earlier sessions unfinished.</p>
          <label>Previous session<select value={continuation} onChange={event => setContinuation(event.target.value)}><option value="">Choose an unfinished session</option>{context.open_sessions.filter(s => s.date < date).map(s => <option value={s.id} key={s.id}>{s.date} · {s.tail.task_label} · {s.state}</option>)}</select></label>
          <button disabled={!continuation || !task}>Continue previous session</button>
          {context.open_sessions.some(s => s.state === 'active' && s.date < date) && <button type="button" className="secondary" onClick={() => { const active = context.open_sessions.find(s => s.state === 'active' && s.date < date)!; void run(() => send(payload('end_day', { session: active.id, at: timestamp() }))); }}>Close overnight recording</button>}
        </>}
        {tool !== 'continue' && <button data-record disabled={(day.sessions.length > 1 && !session) || (tool === 'record' ? !task : tool === 'end' ? !session : false)}>{tool === 'record' ? 'Record task' : tool === 'break' ? 'Record break' : 'End of Working Day'}</button>}
      </fieldset></form>}
      {boundary && <><h3>Edit shared {boundary.edge} boundary</h3><p>The adjoining row will change together. Midnight connections stay fixed. Working time zone: {day.time_zone}.</p><form onSubmit={event => { event.preventDefault(); void run(async () => { const at = boundary.at === localStamp(boundary.original, day.time_zone) ? boundary.original : instant(boundary.at, day.time_zone); if (!at) throw new Error('Enter a boundary time.'); await preview(payload('boundary', { entry: boundary.entry, edge: boundary.edge, at })); }); }}><label>Boundary time<input type="datetime-local" step="any" value={boundary.at} onChange={event => { setDirty(true); setBoundary({ ...boundary, at: event.target.value }); }} required /></label><button disabled={busy || stale}>Preview boundary change</button></form></>}
      <button type="button" className="secondary" disabled={busy} onClick={dismiss}>{boundary ? 'Cancel boundary' : 'Cancel recording'}</button>
      </div>
      {pending && <><h3>Review timesheet change</h3><p>{pending.preview.advice}</p><h4>Before</h4><DayTable day={pending.preview.before} /><h4>After</h4><DayTable day={pending.preview.after} />
        <button disabled={busy || stale} onClick={() => { void run(() => send({ ...pending.body, confirm: true, expected_domain_revision: pending.preview.domain_revision })); }}>{busy ? 'Applying…' : 'Confirm timesheet change'}</button><button className="secondary" disabled={busy} onClick={() => setPending(null)}>Cancel change</button>
      </>}
    </Modal>}
  </section>;
}
