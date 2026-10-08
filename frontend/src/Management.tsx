import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api, type Flags, type Grants, type Organization, type Project, type User } from "./api";

type Run = (action: () => Promise<unknown>) => Promise<void>;
const emptyFlags = (): Flags => ({ task_read: false, task_write: false, remark_read: false, remark_write: false });
const flagNames: Record<keyof Flags, string> = { task_read: "Task read", task_write: "Task write", remark_read: "Remark read", remark_write: "Remark write" };

function ActionForm({ title, submit, children, action }: { title: string; submit: string; children: ReactNode; action: (form: HTMLFormElement) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true);
    try { await action(form); } finally { setBusy(false); }
  }
  return <form aria-label={title} onSubmit={save}><h3>{title}</h3><fieldset disabled={busy}>{children}<button type="submit">{busy ? "Saving…" : submit}</button></fieldset></form>;
}

function AccountFlags({ user }: { user?: User }) {
  const [flags, setFlags] = useState({ is_admin: user?.is_admin ?? false, is_active: user?.is_active ?? true, read_others_timesheets: user?.read_others_timesheets ?? false, write_others_timesheets: user?.write_others_timesheets ?? false });
  const labels = { is_admin: "Application administrator", is_active: "Active account", read_others_timesheets: "Read Others’ Timesheets", write_others_timesheets: "Write Others’ Timesheets" };
  return <div className="checks">{(Object.keys(flags) as (keyof typeof flags)[]).map(key => <label key={key}><input type="checkbox" name={key} checked={flags[key]} onChange={event => setFlags({ ...flags, [key]: event.target.checked, ...(key === "write_others_timesheets" && event.target.checked ? { read_others_timesheets: true } : {}) })} />{labels[key]}</label>)}</div>;
}
function accountValues(form: HTMLFormElement) {
  const data = new FormData(form);
  return { email: String(data.get("email")), display_name: String(data.get("display_name")), is_admin: data.has("is_admin"), is_active: data.has("is_active"), read_others_timesheets: data.has("read_others_timesheets"), write_others_timesheets: data.has("write_others_timesheets") };
}

export function Accounts({ users, run }: { users: User[]; run: Run }) {
  const [selected, setSelected] = useState("");
  const user = users.find(item => item.id === selected);
  return <section className="workspace" aria-label="Accounts">
    <h2>Accounts</h2><p>Create accounts, reset passwords, and manage application privileges. Administrator status grants no task or timesheet access.</p>
    <ActionForm title="Create account" submit="Create account" action={form => run(() => api("users/", "POST", { ...accountValues(form), password: new FormData(form).get("password") }))}>
      <label>Account email<input name="email" type="email" required autoComplete="off" /></label>
      <label>Display name<input name="display_name" maxLength={200} /></label>
      <label>Initial password<input name="password" type="password" required autoComplete="new-password" /></label>
      <AccountFlags />
    </ActionForm>
    <label>Manage account<select value={selected} onChange={event => setSelected(event.target.value)}><option value="">Choose an account</option>{users.map(item => <option key={item.id} value={item.id}>{item.email}</option>)}</select></label>
    {user && <div key={JSON.stringify(user)}>
      <ActionForm title="Edit account" submit="Save account" action={form => run(() => api(`users/${user.id}/`, "PATCH", accountValues(form)))}>
        <label>Account email<input name="email" type="email" required defaultValue={user.email} /></label>
        <label>Display name<input name="display_name" maxLength={200} defaultValue={user.display_name} /></label>
        <AccountFlags user={user} />
      </ActionForm>
      <ActionForm title="Reset password" submit="Reset password" action={form => run(async () => {
        await api(`users/${user.id}/password-reset/`, "POST", { password: new FormData(form).get("password") }); form.reset();
      })}>
        <p>Set a new password and share it with the person directly. Existing sessions will require sign-in.</p>
        <label>New password<input name="password" type="password" required autoComplete="new-password" /></label>
      </ActionForm>
    </div>}
    <table><caption>Account directory</caption><thead><tr><th>Email</th><th>Name</th><th>State</th><th>Administrator</th></tr></thead><tbody>{users.map(item => <tr key={item.id}><td>{item.email}</td><td>{item.display_name}</td><td>{item.is_active ? "Active" : "Inactive"}</td><td>{item.is_admin ? "Yes" : "No"}</td></tr>)}</tbody></table>
  </section>;
}

function Rename({ name, kind, id, run }: { name: string; kind: "organizations" | "projects"; id: string; run: Run }) {
  const singular = kind === "organizations" ? "organization" : "project";
  return <form className="inline" onSubmit={event => { event.preventDefault(); const form = event.currentTarget; void run(() => api(`${kind}/${id}/`, "PATCH", { name: new FormData(form).get("name") })); }}>
    <input aria-label={`${singular} name ${name}`} name="name" defaultValue={name} required maxLength={200} />
    <button type="submit" aria-label={`Rename ${singular} ${name}`}>Rename</button>
    <button type="button" className="secondary" aria-label={`Delete ${singular} ${name}`} onClick={() => { if (window.confirm(`Delete ${singular} “${name}”?`)) void run(() => api(`${kind}/${id}/`, "DELETE")); }}>Delete</button>
  </form>;
}
export function Catalogs({ organizations, projects, run }: { organizations: Organization[]; projects: Project[]; run: Run }) {
  return <section className="workspace" aria-label="Catalogs"><h2>Organizations and projects</h2>
    <ActionForm title="Create organization" submit="Create organization" action={form => run(async () => { await api("organizations/", "POST", { name: new FormData(form).get("name") }); form.reset(); })}>
      <label>Organization name<input name="name" required maxLength={200} /></label>
    </ActionForm>
    <ul className="catalog">{organizations.map(org => <li key={org.id}><Rename name={org.name} kind="organizations" id={org.id} run={run} /></li>)}</ul>
    <ActionForm title="Create project" submit="Create project" action={form => run(async () => { const data = new FormData(form); await api("projects/", "POST", { name: data.get("name"), organization: data.get("organization") }); form.reset(); })}>
      <label>Organization<select name="organization" required defaultValue=""><option value="" disabled>Choose an organization</option>{organizations.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}</select></label>
      <label>Project name<input name="name" required maxLength={200} /></label>
    </ActionForm>
    <table><caption>Project directory</caption><thead><tr><th>Organization</th><th>Project</th></tr></thead><tbody>{projects.map(project => <tr key={project.id}><td>{organizations.find(org => org.id === project.organization)?.name}</td><td><Rename name={project.name} kind="projects" id={project.id} run={run} /></td></tr>)}</tbody></table>
  </section>;
}

export function GrantManagement({ users, organizations, projects, run, version, onError }: { users: User[]; organizations: Organization[]; projects: Project[]; run: Run; version: number; onError: (error: unknown) => void }) {
  const [selected, setSelected] = useState("");
  const [scope, setScope] = useState("organizations");
  const [target, setTarget] = useState("");
  const [grants, setGrants] = useState<Grants | null>(null);
  const [local, setLocal] = useState<Flags>(emptyFlags);
  useEffect(() => {
    let current = true;
    setGrants(null);
    if (selected) api<Grants>(`users/${selected}/grants/`).then(data => { if (current) setGrants(data); }, error => { if (current) onError(error); });
    return () => { current = false; };
  }, [selected, version]); // onError does not change the requested data.
  useEffect(() => {
    const existing = scope === "organizations" ? grants?.organizations.find(g => g.organization === target) : grants?.projects.find(g => g.project === target);
    setLocal(existing ? { task_read: existing.task_read, task_write: existing.task_write, remark_read: existing.remark_read, remark_write: existing.remark_write } : emptyFlags());
  }, [grants, scope, target]);
  const targets = scope === "organizations" ? organizations : projects;
  const project = projects.find(item => item.id === target);
  const inherited = grants?.organizations.find(item => item.organization === project?.organization);
  return <section className="workspace" aria-label="Grants"><h2>Project access</h2><p>Organization grants apply to every project in that organization. Local flags add access; clearing one cannot remove inherited access.</p>
    <label>Grant account<select value={selected} onChange={event => setSelected(event.target.value)}><option value="">Choose an account</option>{users.map(user => <option key={user.id} value={user.id}>{user.email}</option>)}</select></label>
    <label>Grant scope<select value={scope} onChange={event => { setScope(event.target.value); setTarget(""); }}><option value="organizations">Organization</option><option value="projects">Project</option></select></label>
    <label>Grant target<select value={target} onChange={event => setTarget(event.target.value)}><option value="">Choose a target</option>{targets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    {selected && target && grants && <ActionForm title="Local grant" submit="Save grant" action={() => run(() => api(`users/${selected}/grants/${scope}/${target}/`, "PUT", local))}>
      <div className="checks">{(Object.keys(local) as (keyof Flags)[]).map(key => <label key={key}><input type="checkbox" checked={local[key]} onChange={event => setLocal({ ...local, [key]: event.target.checked, ...(event.target.checked && key === "task_write" ? { task_read: true } : {}), ...(event.target.checked && key === "remark_write" ? { remark_read: true } : {}) })} />{flagNames[key]}</label>)}</div>
      {scope === "projects" && <p>Inherited flags: {(Object.keys(flagNames) as (keyof Flags)[]).filter(key => inherited?.[key]).map(key => flagNames[key]).join(", ") || "None"}</p>}
    </ActionForm>}
    {grants && <table><caption>Effective project grants</caption><thead><tr><th>Project</th>{Object.values(flagNames).map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{grants.effective_projects.map(grant => <tr key={grant.project}><td>{projects.find(p => p.id === grant.project)?.name}</td>{(Object.keys(flagNames) as (keyof Flags)[]).map(flag => <td key={flag}>{grant[flag] ? "Yes" : "No"}</td>)}</tr>)}</tbody></table>}
  </section>;
}
