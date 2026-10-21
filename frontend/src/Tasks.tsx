import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, allPages, ApiError, type Project, type User } from "./api";
import { Remarks } from "./Remarks";
import { ContentEditor, ContentText, editorImages } from "./Content";
import { ContentSearch } from "./ContentSearch";
import { Modal } from "./TimeComponents";

interface Status { id: string; name: string; final: boolean; used: boolean }
interface Task {
  id: string; title: string; description: string; project: string; parent: string | null;
  owner: string; owner_name: string; creator: string; status: string; revision: number;
}
interface History { id: number; previous_status: string | null; new_status: string; actor_name: string; changed_at: string }
interface Preview { domain_revision: number; affected: Task[]; confirmation_required: boolean; delete?: { remarks: number; images: number } | null }
interface Pending { preview: Preview; path: string; method: string; body: Record<string, unknown>; label: string }
type Props = { user: User; version: number; onError: (error: unknown) => void; onRecord?: (id: string) => void; openRequest?: { id: string; nonce: number } | null; onChanged?: () => void };

export function Tasks({ user, version, onError, onRecord, openRequest, onChanged }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState("");
  const [targetRemark, setTargetRemark] = useState<string | undefined>();
  const [detail, setDetail] = useState<Task | null>(null);
  const [history, setHistory] = useState<History[]>([]);
  const [owners, setOwners] = useState<{ id: string; display_name: string }[]>([]);
  const [projectFilter, setProjectFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [tree, setTree] = useState(false);
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const [createProject, setCreateProject] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [epoch, setEpoch] = useState(0);
  const [editBlocked, setEditBlocked] = useState(false);
  type View = "details" | "create" | "edit" | "owner" | "status" | "move" | "delete" | "history" | "search";
  const [view, setView] = useState<View | null>(null);
  const [dirty, setDirty] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [parent, setParent] = useState("");
  const inFlight = useRef(false);
  function changeView(next: View | null, id?: string) {
    if (busy || (dirty && !window.confirm("Discard unsaved changes?"))) return false;
    document.querySelectorAll<HTMLDetailsElement>(".task-actions[open]").forEach(menu => { menu.open = false; });
    setDirty(false); setPending(null); setMessage(""); setView(next); if (next === "search") setSearchOpen(true); if (next === null) setSearchOpen(false);
    if (id !== undefined) { setSelected(id); setTargetRemark(undefined); }
    return true;
  }
  function newTask(task?: Task) {
    if (changeView("create")) { setCreateProject(task?.project ?? projectFilter ?? ""); setParent(task?.id ?? ""); }
  }
  function reload() {
    if (busy || (dirty && !window.confirm("Discard unsaved changes and refresh tasks?"))) return;
    setDirty(false); setMessage(""); refresh();
  }
  const creation = useRef<HTMLFormElement>(null);
  const errorHandler = useRef(onError);
  errorHandler.current = onError;
  const acknowledged = useRef(false);
  const refresh = (saved = false) => { if (saved) acknowledged.current = true; setPending(null); setEpoch(value => value + 1); onChanged?.(); };

  useEffect(() => {
    let current = true;
    setLoaded(false); setDetail(null); setHistory([]); setPending(null); setEditBlocked(false);
    Promise.all([allPages<Project>("projects/"), allPages<Status>("statuses/"), allPages<Task>("tasks/")]).then(([p, s, t]) => {
      if (!current) return;
      setProjects(p.filter(item => item.permissions.task_read || item.permissions.task_write));
      setStatuses(s); setTasks(t); setLoaded(true);
      setSelected(value => t.some(item => item.id === value) ? value : "");
    }).catch(error => { if (current) { setTasks([]); setProjects([]); if (acknowledged.current) setEditBlocked(true); setMessage(acknowledged.current ? `Changes saved, but reload failed. Refresh tasks and review before another change. ${error.message}` : error.message); if (error instanceof ApiError && error.code === "authentication_required") errorHandler.current(error); } });
    return () => { current = false; };
  }, [version, epoch]);

  useEffect(() => {
    let current = true;
    setDetail(null); setHistory([]); setOwners([]); setPending(null);
    if (selected && loaded) {
      Promise.all([api<Task>(`tasks/${selected}/`), allPages<History>(`tasks/${selected}/history/`)]).then(async ([task, records]) => {
        if (!current) return;
        setDetail(task); setHistory(records); acknowledged.current = false;
        if (projects.find(item => item.id === task.project)?.permissions.task_write) {
          const directory = await api<{ results: { id: string; display_name: string }[] }>(`projects/${task.project}/eligible-owners/`);
          if (current) setOwners(directory.results);
        }
      }).catch(error => { if (current) { if (acknowledged.current) setEditBlocked(true); setMessage(acknowledged.current ? `Changes saved, but task reload failed. Refresh tasks and review. ${error.message}` : error.message); setSelected(""); if (error instanceof ApiError && error.code === "authentication_required") errorHandler.current(error); } });
    }
    return () => { current = false; };
  }, [selected, loaded, projects]);

  useEffect(() => { if (openRequest && changeView("details", openRequest.id)) { setSelected(openRequest.id); setTargetRemark(undefined); setEpoch(value => value + 1); } }, [openRequest]);
  function openReference(id: string, remark?: string) {
    if (!changeView("details", id)) return;
    setTargetRemark(remark); setEpoch(value => value + 1);
  }

  async function action(operation: () => Promise<void>) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setMessage("");
    try { await operation(); }
    catch (error) {
      setMessage(error instanceof Error ? error.message : "The request failed.");
      if (error instanceof ApiError && ["stale_revision", "stale_preview", "permission_denied", "not_found"].includes(error.code)) {
        setEditBlocked(true); setPending(null);
      }
      if (error instanceof ApiError && error.code === "authentication_required") errorHandler.current(error);
    } finally { inFlight.current = false; setBusy(false); }
  }
  async function preview(path: string, body: Record<string, unknown>, label: string, method = "POST") {
    await action(async () => {
      const previewPath = method === "DELETE" ? `${path}delete/preview/` : `${path}preview/`;
      const result = await api<Preview>(previewPath, "POST", body);
      setPending({ preview: result, path, method, body, label });
    });
  }
  async function save(path: string, body: Record<string, unknown>) {
    await action(async () => { await api(path, "PATCH", body); setDirty(false); setView("details"); refresh(true); setMessage("Changes saved."); });
  }
  const nonFinal = statuses.filter(item => !item.final);
  const statusName = (id: string) => statuses.find(item => item.id === id)?.name ?? "Unknown status";
  const projectName = (id: string) => projects.find(item => item.id === id)?.name ?? "Unavailable project";
  const writable = projects.filter(item => item.permissions.task_write);
  const editable = detail && projects.find(item => item.id === detail.project)?.permissions.task_write;
  const filtered = tasks.filter(task => (!projectFilter || task.project === projectFilter) && (!statusFilter.length || statusFilter.includes(task.status)));
  const filteredIds = new Set(filtered.map(task => task.id));
  const children = (id: string | null) => filtered.filter(task => id === null ? !task.parent || !filteredIds.has(task.parent) : task.parent === id);
  function taskRows(rows: Task[], depth = 0): React.ReactNode {
    return rows.map(task => <li key={task.id}>
      <div className="task-row" style={{ paddingInlineStart: `${depth * 20}px` }}>
        {tree && children(task.id).length > 0 && <button className="secondary disclosure" aria-label={`${collapsed.includes(task.id) ? "Expand" : "Collapse"} ${task.title}`} aria-expanded={!collapsed.includes(task.id)} onClick={() => setCollapsed(value => value.includes(task.id) ? value.filter(id => id !== task.id) : [...value, task.id])}>{collapsed.includes(task.id) ? "+" : "−"}</button>}
        <button className="task-link" draggable onDragStart={event => { event.dataTransfer.setData("application/x-task-tracker-task", task.id); event.dataTransfer.effectAllowed = "copy"; }} aria-pressed={selected === task.id} onClick={() => { changeView("details", task.id); }}>{task.title}</button>
        <details className="task-actions"><summary aria-label={`Actions for ${task.title}`}>Actions</summary><div className="action-menu">
          {projects.find(p => p.id === task.project)?.permissions.task_write && <>
            <button onClick={() => { newTask(task); }}>Add subtask</button>
            {([['edit', 'Edit task'], ['status', 'Change status'], ['owner', 'Transfer ownership'], ['move', 'Move task'], ['delete', 'Delete task']] as const).map(([command, label]) => <button key={command} onClick={() => { changeView(command, task.id); }}>{label}</button>)}
          </>}
          {onRecord && <button aria-label={`Record ${task.title}`} onClick={() => { if (changeView(null)) onRecord(task.id); }}>Record time</button>}
        </div></details>
        <span>{statusName(task.status)}</span><small>{projectName(task.project)}</small>
      </div>
      {tree && !collapsed.includes(task.id) && <ul>{taskRows(children(task.id), depth + 1)}</ul>}
    </li>);
  }
  function reopenSelect() {
    return <label>Reopen final ancestors into<select name="reopen_status" defaultValue={nonFinal.find(item => item.name === "In Progress")?.id ?? nonFinal[0]?.id ?? ""}><option value="">Choose if ancestors must reopen</option>{nonFinal.map(status => <option key={status.id} value={status.id}>{status.name}</option>)}</select></label>;
  }
  const reopenValue = (data: FormData) => data.get("reopen_status") ? { reopen_status: data.get("reopen_status") } : {};
  const fieldValues = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); return new FormData(event.currentTarget); };

  return <section className="workspace" aria-label="Tasks"><h2>Tasks</h2>

    {!view && message && <p role="alert">{message}</p>}
    {!view && editBlocked && <p>Refresh tasks and review the latest record before saving again. Copy any unsaved text first; refreshing tasks discards unsaved task drafts and images.</p>}

    <div className="task-toolbar">
      {writable.length > 0 && loaded && <button onClick={() => newTask()}>New task</button>}
      <button className="secondary" onClick={() => changeView("search")}>Search tasks and remarks</button>
      <label>Filter project<select value={projectFilter} onChange={event => setProjectFilter(event.target.value)}><option value="">All readable projects</option>{projects.filter(item => item.permissions.task_read).map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
      <button className="secondary" aria-pressed={tree} onClick={() => setTree(value => !value)}>{tree ? "Tree view" : "Flat view"}</button>
      <button className="secondary" disabled={busy} onClick={reload}>Refresh tasks</button>
    </div>
    <details className="status-filters"><summary>Statuses: {statusFilter.length ? statusFilter.map(statusName).join(", ") : "All"}</summary><fieldset className="checks"><legend>Include statuses (none selected means all)</legend>{statuses.map(status => <label key={status.id}><input type="checkbox" checked={statusFilter.includes(status.id)} onChange={event => setStatusFilter(value => event.target.checked ? [...value, status.id] : value.filter(id => id !== status.id))} />{status.name}</label>)}</fieldset></details>
    {!loaded ? <p>Loading tasks…</p> : <div className="task-workspace">
      <div><p>{filtered.length} matching tasks</p><ul className="task-list" aria-label={tree ? "Task tree" : "Task list"}>{taskRows(tree ? children(null) : filtered)}</ul>{!filtered.length && <p>No tasks match these filters.</p>}</div>
    </div>}
    {view && <Modal name={pending ? "Confirm task change" : ({ details: "Task description", create: "Create task", edit: "Edit task", owner: "Transfer ownership", status: "Change status", move: "Move task", delete: "Delete task", history: "Status history", search: "Search tasks and remarks" })[view]} dirty={dirty} onDismiss={() => { if (busy) return; if (pending) setPending(null); else changeView(null); }}>
      {message && <p role="alert">{message}</p>}
      {editBlocked && <><p>Refresh tasks and review the latest record before saving again. Copy any unsaved text first; refreshing tasks discards unsaved task drafts and images.</p><button disabled={busy} onClick={reload}>Refresh tasks</button></>}
      <div hidden={pending !== null}>
      <button className="secondary" disabled={busy} onClick={() => changeView(null)}>{view === "details" ? "Close details" : "Close window"}</button>
      {view !== "details" && view !== "create" && view !== "search" && <button className="secondary" disabled={busy} onClick={() => changeView("details")}>Back to details</button>}
      {searchOpen && <><button hidden={view === "search"} className="secondary" onClick={() => changeView("search")}>Back to search</button><div hidden={view !== "search"}><ContentSearch version={version} onOpen={openReference} onError={onError} /></div></>}
      {selected && !detail && view !== "create" && view !== "search" && <p>Loading task…</p>}
      {detail && view !== "create" && view !== "search" && <section className="task-detail" key={`${detail.id}:${detail.revision}`}>
        <h3>{detail.title}</h3>
        {view === "details" && <>
          <div className="inline">
            {editable && <>{([['edit', 'Edit task'], ['status', 'Change status'], ['owner', 'Transfer ownership'], ['move', 'Move task'], ['delete', 'Delete task']] as const).map(([command, label]) => <button className="secondary compact" key={command} onClick={() => changeView(command)}>{label}</button>)}<button className="secondary compact" onClick={() => newTask(detail)}>Add subtask</button></>}
            <button className="secondary compact" onClick={() => changeView("history")}>History</button>
            {onRecord && <button className="secondary compact" onClick={() => { if (changeView(null)) onRecord(detail.id); }}>Record time</button>}
          </div>
          <Remarks task={detail.id} project={detail.project} userId={user.id} onDirtyChange={setDirty} version={version} onError={onError} onOpen={openReference} targetRemark={targetRemark}>
            <p className="description"><ContentText text={detail.description || "No description."} onOpen={openReference} /></p>
            <p>{projectName(detail.project)} · {statusName(detail.status)} · Owner: {detail.owner_name}</p>
          </Remarks>
        </>}
        {view === "history" && <><h4>Status history</h4><ol>{history.map(row => <li key={row.id}>{row.previous_status ? `${statusName(row.previous_status)} → ` : "Created as "}{statusName(row.new_status)} — {row.actor_name} <time dateTime={row.changed_at}>{new Date(row.changed_at).toLocaleString()}</time></li>)}</ol></>}
        {editable && <fieldset disabled={busy || pending !== null || editBlocked}>
          {view === "edit" && <form onChange={() => setDirty(true)} aria-label="Edit task" onSubmit={event => { const data = fieldValues(event); void save(`tasks/${detail.id}/`, { title: data.get("title"), description: data.get("description"), images: editorImages(data), expected_revision: detail.revision }); }}>
            <label>Task title<input name="title" defaultValue={detail.title} maxLength={200} required /></label>
            <ContentEditor label="Description" name="description" initialValue={detail.description} onChange={() => setDirty(true)} rows={5} /><button>Save task</button>
          </form>}
          {view === "owner" && <form onChange={() => setDirty(true)} aria-label="Transfer ownership" onSubmit={event => { const data = fieldValues(event); void action(async () => { await api(`tasks/${detail.id}/owner/`, "POST", { owner: data.get("owner"), expected_revision: detail.revision }); setDirty(false); setView("details"); refresh(true); setMessage("Owner saved."); }); }}>
            <label>New owner<select name="owner" required defaultValue=""><option value="" disabled>Choose an eligible owner</option>{owners.map(owner => <option key={owner.id} value={owner.id}>{owner.display_name}{owner.id === user.id ? " (you)" : ""}</option>)}</select></label><button>Transfer ownership</button>
          </form>}
          {view === "status" && <form onChange={() => setDirty(true)} aria-label="Change status" onSubmit={event => { const data = fieldValues(event); void preview(`tasks/${detail.id}/status/`, { status: data.get("status"), ...reopenValue(data), expected_revision: detail.revision }, "Change status"); }}>
            <label>New status<select name="status" defaultValue={detail.status}>{statuses.map(status => <option key={status.id} value={status.id}>{status.name}</option>)}</select></label>{reopenSelect()}<button>Preview status change</button>
          </form>}
          {view === "move" && <form onChange={() => setDirty(true)} aria-label="Move task" onSubmit={event => { const data = fieldValues(event); void preview(`tasks/${detail.id}/move/`, { parent: data.get("parent") || null, project: data.get("project"), ...reopenValue(data), expected_revision: detail.revision }, "Move task and subtree"); }}>
            <label>Destination project<select name="project" defaultValue={detail.project}>{writable.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
            <label>New parent<select name="parent" defaultValue={detail.parent ?? ""}><option value="">Top level</option>{tasks.filter(task => task.id !== detail.id).map(task => <option key={task.id} value={task.id}>{task.title} ({projectName(task.project)})</option>)}</select></label>{reopenSelect()}<button>Preview move</button>
          </form>}
          {view === "delete" && <button className="danger" onClick={() => { void preview(`tasks/${detail.id}/`, { expected_revision: detail.revision }, "Delete task permanently", "DELETE"); }}>Preview deletion</button>}
        </fieldset>}
      </section>}
    {view === "create" && writable.length > 0 && loaded && <form ref={creation} onChange={() => setDirty(true)} aria-label="Create task" onSubmit={event => {
      const data = fieldValues(event);
      void preview("tasks/", { title: data.get("title"), description: data.get("description"), images: editorImages(data), project: data.get("project"), parent: data.get("parent") || null, status: data.get("status"), ...reopenValue(data) }, "Create task");
    }}><h3>Create task</h3><fieldset disabled={busy || pending !== null || editBlocked}>
      <label>Task title<input name="title" maxLength={200} required /></label><ContentEditor label="Description" name="description" onChange={() => setDirty(true)} />
      <label>Task project<select name="project" required value={createProject} onChange={event => setCreateProject(event.target.value)}><option value="" disabled>Choose a project</option>{writable.map(project => <option key={project.id} value={project.id}>{project.name}{!project.permissions.task_read ? " (write only)" : ""}</option>)}</select></label>
      <label>Parent task<select name="parent" key={createProject} defaultValue={parent}><option value="">Top level</option>{tasks.filter(task => task.project === createProject).map(task => <option key={task.id} value={task.id}>{task.title}</option>)}</select></label>
      <label>Initial status<select name="status" defaultValue={nonFinal.find(item => item.name === "In Progress")?.id}>{statuses.map(status => <option key={status.id} value={status.id}>{status.name}</option>)}</select></label>
      {reopenSelect()}<button>Preview new task</button>
    </fieldset></form>}
    </div>
    {pending && <section className="task-preview">
      <h3>{pending.label}</h3><p>Review the affected tasks before applying this change.</p>
      {pending.preview.affected.length > 0 ? <ul>{pending.preview.affected.map(task => <li key={task.id}>{task.title} — {statusName(task.status)}, {projectName(task.project)}{task.parent ? `, parent: ${tasks.find(item => item.id === task.parent)?.title ?? "selected parent"}` : ", top level"}</li>)}</ul> : <p>The action can be confirmed. Task details require read access.</p>}
      {pending.method === "DELETE" && <p>This permanently deletes the task and its status history.</p>}
      {pending.method === "DELETE" && !!pending.preview.delete?.remarks && <p>This also permanently deletes {pending.preview.delete.remarks} remark(s).</p>}
      {pending.method === "DELETE" && !!pending.preview.delete?.images && <p>This also permanently deletes {pending.preview.delete.images} image(s).</p>}
      <button disabled={busy} onClick={() => { void action(async () => { const result = await api<{ id: string }>(pending.path, pending.method, { ...pending.body, confirm: true, expected_domain_revision: pending.preview.domain_revision }); if (pending.path === "tasks/") creation.current?.reset(); setDirty(false); setView(pending.method === "DELETE" || !projects.find(p => p.id === (pending.body.project ?? detail?.project))?.permissions.task_read ? null : "details"); refresh(true); if (pending.method === "DELETE") setSelected(""); else setSelected(result.id); setMessage("Changes saved."); }); }}>{busy ? "Applying…" : "Confirm change"}</button>
      <button className="secondary" disabled={busy} onClick={() => setPending(null)}>Cancel change</button>
    </section>}
    </Modal>}
    {loaded && !projects.length && <p>No task access is configured.</p>}
    {loaded && projects.some(project => project.permissions.task_write && !project.permissions.task_read) && <p>Write-only projects support creating tasks here. Their task lists and descriptions require read access.</p>}
  </section>;
}

export function StatusManagement({ version, onError }: { version: number; onError: (error: unknown) => void }) {
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [epoch, setEpoch] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => { let current = true; allPages<Status>("statuses/").then(result => { if (current) setStatuses(result); }).catch(onError); return () => { current = false; }; }, [version, epoch]);
  async function run(path: string, method: string, body?: unknown) {
    setBusy(true); setMessage("");
    try { await api(path, method, body); setEpoch(value => value + 1); setMessage("Status catalog saved."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "The request failed."); if (error instanceof ApiError && ["permission_denied", "authentication_required"].includes(error.code)) onError(error); }
    finally { setBusy(false); }
  }
  return <section className="workspace" aria-label="Task statuses"><h2>Task statuses</h2><p>Once a status is used, its name and final property are permanently protected.</p>{message && <p role="alert">{message}</p>}
    <form aria-label="Create status" onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); void run("statuses/", "POST", { name: data.get("name"), final: data.has("final") }); }}><fieldset disabled={busy}><label>Status name<input name="name" maxLength={200} required /></label><label className="check"><input type="checkbox" name="final" />Final status</label><button>Create status</button></fieldset></form>
    <ul className="catalog">{statuses.map(status => <li key={`${status.id}:${status.name}:${status.final}`}><form aria-label={`Status ${status.name}`} onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); void run(`statuses/${status.id}/`, "PATCH", { name: data.get("name"), final: data.has("final") }); }}><fieldset disabled={busy || status.used}>
      <label>Status name<input name="name" defaultValue={status.name} maxLength={200} required /></label><label className="check"><input type="checkbox" name="final" defaultChecked={status.final} />Final status</label><button>Save status</button><button className="secondary" type="button" onClick={() => { if (window.confirm(`Delete unused status “${status.name}”?`)) void run(`statuses/${status.id}/`, "DELETE"); }}>Delete status</button>
    </fieldset>{status.used && <p>Used — permanently protected.</p>}</form></li>)}</ul>
  </section>;
}
