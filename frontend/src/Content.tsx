import { useEffect, useId, useRef, useState } from "react";
import { allPages, api } from "./api";

const referencePattern = /\[(task|remark):([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\]/g;
type Target = { kind: string; id: string; available: boolean; label: string; task?: string };
export type OpenReference = (task: string, remark?: string) => void;
export const contentPreview = (text: string) => text.replace(referencePattern, "Reference");

export function ContentText({ text, onOpen }: { text: string; onOpen: OpenReference }) {
  const [targets, setTargets] = useState<Target[]>([]);
  const [reload, setReload] = useState(0);
  const [failed, setFailed] = useState(false);
  const matches = [...text.matchAll(referencePattern)];
  const keys = [...new Set(matches.map(match => `${match[1]}:${match[2].toLowerCase()}`))];
  const signature = keys.join(",");
  useEffect(() => {
    let current = true;
    setTargets([]); setFailed(false);
    if (signature) void (async () => {
      const values: Target[] = [];
      const keys = signature.split(",");
      for (let start = 0; start < keys.length; start += 100) {
        const targets = keys.slice(start, start + 100).map(key => { const [kind, id] = key.split(":"); return { kind, id }; });
        const result = await api<{ results: Target[] }>("references/resolve/", "POST", { targets });
        values.push(...result.results);
      }
      if (current) setTargets(values);
    })().catch(() => { if (current) setFailed(true); });
    return () => { current = false; };
  }, [signature, reload]);
  let previous = 0;
  const parts: React.ReactNode[] = [];
  for (const match of matches) {
    parts.push(text.slice(previous, match.index));
    const target = targets.find(item => item.kind === match[1] && item.id === match[2].toLowerCase());
    parts.push(target?.available ? <a key={match.index} href={`#${target.kind}-${target.id}`} onClick={event => {
      event.preventDefault(); onOpen(target.task!, target.kind === "remark" ? target.id : undefined);
    }}>{target.label}</a> : <span key={match.index} className="unavailable-reference">Unavailable reference</span>);
    previous = match.index! + match[0].length;
  }
  parts.push(text.slice(previous));
  return <><span className="description">{parts}</span>{signature && <button type="button" className="secondary compact" onClick={() => setReload(value => value + 1)}>{failed ? "Retry references" : "Refresh references"}</button>}</>;
}

function ReferencePicker({ onInsert }: { onInsert: (token: string) => void }) {
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<{ id: string; title: string }[]>([]);
  const [remarks, setRemarks] = useState<{ id: string; body: string; author_name: string }[]>([]);
  const [task, setTask] = useState("");
  const [remark, setRemark] = useState("");
  const [kind, setKind] = useState("task");
  const [message, setMessage] = useState("");
  const [tasksLoading, setTasksLoading] = useState(false);
  const [remarksLoading, setRemarksLoading] = useState(false);
  useEffect(() => {
    let current = true;
    if (open) {
      setTasksLoading(true); setMessage(""); setTasks([]);
      allPages<{ id: string; title: string }>("tasks/").then(rows => { if (current) setTasks(rows); })
        .catch(() => { if (current) setMessage("Unable to load reference targets. Close and try again."); })
        .finally(() => { if (current) setTasksLoading(false); });
    }
    return () => { current = false; };
  }, [open]);
  useEffect(() => {
    let current = true;
    setRemarks([]); setRemark(""); setMessage(""); setRemarksLoading(false);
    if (open && task && kind === "remark") {
      setRemarksLoading(true);
      allPages<{ id: string; body: string; author_name: string }>(`tasks/${task}/remarks/`).then(rows => { if (current) setRemarks(rows); })
        .catch(() => { if (current) setMessage("Remarks are unavailable for this task."); })
        .finally(() => { if (current) setRemarksLoading(false); });
    }
    return () => { current = false; };
  }, [open, task, kind]);
  return <div className="reference-picker">
    <button type="button" className="secondary compact" onClick={() => { setOpen(value => !value); setTask(""); }}>{open ? "Close reference picker" : "Insert reference"}</button>
    {open && <fieldset aria-label="Reference picker">
      <label>Reference kind<select value={kind} onChange={event => setKind(event.target.value)}><option value="task">Task</option><option value="remark">Remark</option></select></label>
      <label>Reference task<select value={task} onChange={event => setTask(event.target.value)}><option value="">Choose a readable task</option>{tasks.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></label>
      {kind === "remark" && <label>Reference remark<select value={remark} onChange={event => setRemark(event.target.value)}><option value="">Choose a readable remark</option>{remarks.map(row => <option key={row.id} value={row.id}>{row.author_name}: {row.body.slice(0, 100)}</option>)}</select></label>}
      {(tasksLoading || remarksLoading) && <p>Loading reference targets…</p>}{message && <p role="alert">{message}</p>}
      <button type="button" disabled={tasksLoading || remarksLoading || !(kind === "task" ? task : remark)} onClick={() => { onInsert(`[${kind}:${kind === "task" ? task : remark}]`); setOpen(false); }}>Insert selected reference</button>
    </fieldset>}
  </div>;
}

export function ContentEditor({ label, name, initialValue = "", value, onChange, rows = 4, required = false }: {
  label: string; name?: string; initialValue?: string; value?: string; onChange?: (value: string) => void; rows?: number; required?: boolean;
}) {
  const [local, setLocal] = useState(initialValue);
  const id = useId();
  const textarea = useRef<HTMLTextAreaElement>(null);
  const text = value ?? local;
  const change = (value: string) => { setLocal(value); onChange?.(value); };
  return <><label htmlFor={id}>{label}</label><textarea id={id} ref={textarea} name={name} value={text} onChange={event => change(event.target.value)} rows={rows} required={required} />
    <ReferencePicker onInsert={token => {
      const start = textarea.current?.selectionStart ?? text.length;
      const end = textarea.current?.selectionEnd ?? start;
      change(text.slice(0, start) + token + text.slice(end));
      requestAnimationFrame(() => { textarea.current?.focus(); textarea.current?.setSelectionRange(start + token.length, start + token.length); });
    }} />
  </>;
}
