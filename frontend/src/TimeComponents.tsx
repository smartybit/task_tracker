import { useEffect, useRef, useState, type ReactNode } from 'react';
import { type Project } from './api';
import { type Day, type PickerTask, type PickerStatus, clock, hours } from './timesheet';

export function Modal({ name, onDismiss, children }: { name: string; onDismiss: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current!; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog ref={ref} aria-label={name} onCancel={event => { event.preventDefault(); onDismiss(); }}>{children}</dialog>;
}

export function TaskPicker({ tasks, projects, statuses, value, onChange, prefix = 'Picker' }: {
  tasks: PickerTask[]; projects: Project[]; statuses: PickerStatus[]; value: string;
  onChange: (id: string) => void; prefix?: string;
}) {
  const [query, setQuery] = useState('');
  const [project, setProject] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const visible = tasks.filter(task => task.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()) && (!project || task.project === project) && (!selected.length || selected.includes(task.status)));
  const chosen = tasks.find(task => task.id === value);
  return <fieldset className="time-picker"><legend>Choose a task</legend>
    <label>{prefix} search<input type="search" value={query} onChange={event => setQuery(event.target.value)} /></label>
    <label>{prefix} project<select value={project} onChange={event => setProject(event.target.value)}><option value="">All readable projects</option>{projects.filter(p => p.permissions.task_read).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    <fieldset className="checks"><legend>{prefix} statuses (all when empty)</legend>{statuses.map(s => <label key={s.id}><input type="checkbox" checked={selected.includes(s.id)} onChange={event => setSelected(current => event.target.checked ? [...current, s.id] : current.filter(id => id !== s.id))} />{s.name}</label>)}</fieldset>
    <label>{prefix} task<select value={value} onChange={event => onChange(event.target.value)}><option value="">Choose a task</option>{chosen && !visible.some(task => task.id === value) && <option value={chosen.id}>{chosen.title} (selected)</option>}{visible.map(task => <option key={task.id} value={task.id}>{task.title} · {statuses.find(s => s.id === task.status)?.name}</option>)}</select></label>
    <p>{visible.length} selectable tasks. Final tasks can be used for historical corrections. Reopen separately in Tasks before new current recording.</p>
  </fieldset>;
}

export function DayTable({ day, openTask, boundary, remove }: {
  day: Day; openTask?: (id: string) => void;
  boundary?: (entry: string, edge: 'start' | 'end', at: string) => void; remove?: (entry: string) => void;
}) {
  return <div className="time-table-wrap"><table className="time-table"><caption>{day.date} · {hours(day.work_seconds)} of task work</caption>
    <thead><tr><th>Task</th><th>Start Time</th><th>End Time</th></tr></thead>
    <tbody>{day.sessions.map(session => <TimeRows key={session.id} session={session} day={day} openTask={openTask} boundary={boundary} remove={remove} />)}</tbody>
  </table>{!day.sessions.length && <p>No work recorded on this day.</p>}</div>;
}
function TimeRows({ session, day, openTask, boundary, remove }: {
  session: Day['sessions'][number]; day: Day; openTask?: (id: string) => void;
  boundary?: (entry: string, edge: 'start' | 'end', at: string) => void; remove?: (entry: string) => void;
}) {
  return <><tr className="session-heading"><th colSpan={3}>{session.state}{session.continues_before && ' · continues from previous day'}{session.continues_after && ' · continues into next day'}</th></tr>
    {session.rows.map((row, index) => <tr key={row.id}>
      <td>{row.task && row.task_readable && openTask ? <button className="task-link" onClick={() => openTask(row.task!)}>{row.task_label}</button> : <span>{row.task_label}</span>}{row.task && !row.task_readable && <small> · details restricted</small>}
        {remove && index === session.rows.length - 1 && !session.continues_after && !(session.continues_before && session.rows.length === 1) && <button className="secondary compact" onClick={() => remove(row.id)}>Delete last record</button>}</td>
      {(['start', 'end'] as const).map(edge => {
        const at = edge === 'start' ? row.started_at : row.ended_at;
        const fixed = edge === 'start' ? index === 0 && session.continues_before : index === session.rows.length - 1 && session.continues_after;
        return <td key={edge}>{boundary && at && !fixed ? <button className="time-boundary" aria-label={`Edit ${edge} of ${row.task_label} at ${clock(at, day.time_zone)}`} onClick={() => boundary(row.id, edge, at)}>{clock(at, day.time_zone)}</button> : <span>{clock(at, day.time_zone)}{fixed && ' (fixed)'}</span>}</td>;
      })}
    </tr>)}
    {session.ended_at && <tr><td>End of Working Day</td><td>{clock(session.ended_at, day.time_zone)}</td><td>—</td></tr>}
  </>;
}
