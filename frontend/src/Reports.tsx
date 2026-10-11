import { useEffect, useRef, useState } from 'react';
import { api, ApiError, type User } from './api';

interface Options {
  time_zone: string; today: string; read_others_timesheets: boolean;
  projects: { id: string; name: string }[];
  tasks: { id: string; title: string; project: string; parent: string | null }[];
  people: { id: string; name: string }[];
}
interface Row {
  project?: string; person?: string; task?: string; name?: string; title?: string; date?: string;
  depth?: number; hours?: string; direct_hours?: string; descendant_hours?: string; total_hours?: string;
}
interface Result { from: string; to: string; time_zone: string; total_hours: string; results: Row[] }
const views = { projects: 'Projects', 'people-days': 'People by day', tasks: 'Task hierarchy' };
type View = keyof typeof views;

export function Reports({ user, version, onError }: { user: User; version: number; onError: (error: unknown) => void }) {
  const [options, setOptions] = useState<Options | null>(null);
  const [view, setView] = useState<View>('projects');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [person, setPerson] = useState('');
  const [project, setProject] = useState('');
  const [task, setTask] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [message, setMessage] = useState('');
  const [retry, setRetry] = useState(0);
  const errorHandler = useRef(onError);
  errorHandler.current = onError;
  const downloadGeneration = useRef(0);
  const initialized = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setBusy(true); setResult(null); setMessage('');
    // Invalidate outstanding downloads on a filter/access change or unmount.
    downloadGeneration.current += 1;
    setDownloading(false);
    async function load() {
      const available = await api<Options>('reports/options/');
      if (cancelled) return;
      setOptions(available);
      if (!initialized.current) {
        initialized.current = true;
        setFrom(`${available.today.slice(0, 7)}-01`);
        setTo(available.today);
        return;
      }
      if ((project && !available.projects.some(p => p.id === project)) ||
          (person && !available.people.some(p => p.id === person)) ||
          (task && !available.tasks.some(t => t.id === task))) {
        setMessage('A selected project, person, or task is no longer available. Choose another selection.');
        return;
      }
      const params = new URLSearchParams({ from, to });
      if (person) params.set('person', person);
      if (project) params.set('project', project);
      if (task) params.set('task', task);
      const response = await api<Result>(`reports/${view}/?${params}`);
      if (!cancelled) setResult(response);
    }
    void load().catch(error => {
      if (cancelled) return;
      setMessage(error instanceof Error ? error.message : 'Reports could not be loaded.');
      setOptions(null);
      if (error instanceof ApiError && error.code === 'authentication_required') errorHandler.current(error);
    }).finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; downloadGeneration.current += 1; };
  }, [user.id, version, view, from, to, person, project, task, retry]);

  async function download() {
    const generation = ++downloadGeneration.current;
    setDownloading(true); setMessage('');
    try {
      const response = await fetch(`/api/v1/reports/records.csv?${new URLSearchParams({ from, to })}`, { credentials: 'same-origin' });
      if (!response.ok) {
        const error = await response.json();
        throw new ApiError(error.code ?? 'request_failed', error.message ?? 'CSV download failed.');
      }
      const blob = await response.blob();
      if (generation !== downloadGeneration.current) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = `task-records-${from}-to-${to}.csv`;
      document.body.append(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage('CSV downloaded. It includes all authorized task records in the selected period.');
    } catch (error) {
      if (generation !== downloadGeneration.current) return;
      setMessage(error instanceof Error ? error.message : 'CSV download failed.');
      if (error instanceof ApiError && error.code === 'authentication_required') errorHandler.current(error);
    } finally {
      if (generation === downloadGeneration.current) setDownloading(false);
    }
  }

  return <section className="workspace report-workspace" aria-label="Reports" aria-busy={busy}>
    <h2>Reports</h2>
    <p>Hours in readable projects, {options?.read_others_timesheets ? 'including other people’s work' : 'for your own work'}.
      {' '}Whole-timesheet totals can include work outside these projects.</p>
    {options && <p>Dates and times use {options.time_zone}. Unfinished entries contribute zero hours.</p>}
    <div className="report-filters">
      <label>Report view<select value={view} onChange={event => setView(event.target.value as View)}>
        {Object.entries(views).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select></label>
      <label>From date<input type="date" required value={from} onChange={event => setFrom(event.target.value)} /></label>
      <label>To date<input type="date" required value={to} onChange={event => setTo(event.target.value)} /></label>
      <label>Report person<select value={person} onChange={event => setPerson(event.target.value)}>
        <option value="">All permitted people</option>
        {person && !options?.people.some(p => p.id === person) && <option value={person}>Unavailable selection</option>}
        {options?.people.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select></label>
      <label>Report project<select value={project} onChange={event => { setProject(event.target.value); setTask(''); }}>
        <option value="">All readable projects</option>
        {project && !options?.projects.some(p => p.id === project) && <option value={project}>Unavailable selection</option>}
        {options?.projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select></label>
      <label>Task and descendants<select value={task} onChange={event => setTask(event.target.value)}>
        <option value="">All tasks</option>
        {task && !options?.tasks.some(t => t.id === task) && <option value={task}>Unavailable selection</option>}
        {options?.tasks.filter(t => !project || t.project === project).map(t => <option key={t.id} value={t.id}>
          {t.title} ({options.projects.find(p => p.id === t.project)?.name})
        </option>)}
      </select></label>
    </div>
    <div className="inline">
      <button className="secondary" disabled={busy} onClick={() => setRetry(value => value + 1)}>Refresh reports</button>
      <button disabled={busy || downloading || !from || !to || from > to} onClick={() => void download()}>
        {downloading ? 'Downloading…' : 'Download CSV'}
      </button>
    </div>
    <p>CSV includes all authorized task records for these dates. Person, project, and task filters apply to the reports only.</p>
    {message && <p role="alert">{message}</p>}
    {busy && <p role="status">Loading reports…</p>}
    {result && <>
      <p className="report-total">Total recorded work: <strong>{result.total_hours} hours</strong></p>
      <div className="time-table-wrap"><table className="report-table">
        <caption>{views[view]} · {result.from} to {result.to} · {result.time_zone}</caption>
        <thead><tr>{view === 'projects' ? <><th scope="col">Project</th><th scope="col">Hours</th></>
          : view === 'people-days' ? <><th scope="col">Person</th><th scope="col">Date</th><th scope="col">Hours</th></>
            : <><th scope="col">Task</th><th scope="col">Project</th><th scope="col">Direct hours</th><th scope="col">Descendant hours</th><th scope="col">Total hours</th></>}</tr></thead>
        <tbody>{result.results.map(row => <tr key={view === 'projects' ? row.project : view === 'tasks' ? row.task : `${row.person}-${row.date}`}>
          {view === 'projects' ? <><th scope="row">{row.name}</th><td>{row.hours}</td></>
            : view === 'people-days' ? <><th scope="row">{row.name}</th><td>{row.date}</td><td>{row.hours}</td></>
              : <><th scope="row" style={{ paddingInlineStart: `${10 + Math.min(row.depth ?? 0, 12) * 18}px` }}>
                {(row.depth ?? 0) > 0 && <span aria-hidden="true">↳ </span>}{row.title}
              </th><td>{options?.projects.find(p => p.id === row.project)?.name}</td>
                <td>{row.direct_hours}</td><td>{row.descendant_hours}</td><td>{row.total_hours}</td></>}
        </tr>)}</tbody>
      </table></div>
      {!result.results.length && <p>No recorded work matches this selection.</p>}
    </>}
  </section>;
}
