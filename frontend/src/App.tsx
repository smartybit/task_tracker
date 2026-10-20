import { useEffect, useState } from "react";
import { api, allPages, ApiError, getHealth, type User, type Organization, type Project } from "./api";
import { StatusManagement } from "./Tasks";
import { WorkArea } from "./WorkArea";
import { Reports } from "./Reports";
import { Accounts, Catalogs, GrantManagement } from "./Management";

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tab, setTab] = useState("Tasks");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);

  function onError(error: unknown) {
    setMessage(error instanceof Error ? error.message : "The request failed.");
    if (error instanceof ApiError && error.code === "authentication_required") setUser(null);
  }
  async function refresh() {
    const me = await api<User>("auth/me/");
    const [orgs, available, accounts] = await Promise.all([allPages<Organization>("organizations/"), allPages<Project>("projects/"), me.is_admin ? allPages<User>("users/") : Promise.resolve([])]);
    setUser(me); setTab(current => !me.is_admin && ["Accounts", "Catalogs", "Grants", "Statuses", "System status"].includes(current) ? "Tasks" : current); setOrganizations(orgs); setProjects(available); setUsers(accounts); setVersion(value => value + 1);
  }
  useEffect(() => { void refresh().catch(error => {
    if (!(error instanceof ApiError && error.code === "authentication_required")) onError(error);
  }); }, []);
  async function run(action: () => Promise<unknown>) {
    setMessage("");
    try { await action(); await refresh(); setMessage("Changes saved."); }
    catch (error) { onError(error); if (error instanceof ApiError && error.code === "permission_denied") void refresh().catch(onError); }
  }

  const administration = ["Accounts", "Catalogs", "Grants", "Statuses", "System status"];
  function navigate(name: string) { setTab(name); setMessage(""); }

  return (
    <main>
      <header><h1 className="brand">Task Tracker</h1><span>Tasks and time</span></header>
      {message && <p role="alert">{message}</p>}
      {!user ? <section className="workspace" aria-label="Sign in"><h2>Sign in</h2>
        <form aria-label="Sign in" onSubmit={event => {
          event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setMessage("");
          void api("auth/login/", "POST", { email: data.get("email"), password: data.get("password") }).then(async () => { await refresh(); setTab("Tasks"); }).catch(onError).finally(() => setBusy(false));
        }}><label>Email<input name="email" type="email" autoComplete="username" required /></label>
          <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
          <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button></form>
      </section> : <>
        <div className="session"><strong>Signed in as {user.display_name || user.email}</strong><button className="secondary" onClick={() => { void api("auth/logout/", "POST", {}).then(() => { setUser(null); setUsers([]); setProjects([]); setMessage(""); }).catch(onError); }}>Sign out</button><button className="secondary" onClick={() => { void refresh().catch(onError); }}>Refresh access</button></div>
        <nav aria-label={user.is_admin ? "Management" : "Workspace"}>
          {["Tasks", "Reports", ...(user.is_admin ? ["Administration"] : ["My access"])].map(name =>
            <button key={name} aria-pressed={name === "Administration" ? administration.includes(tab) : tab === name} onClick={() => navigate(name === "Administration" ? "Accounts" : name)}>{name}</button>)}
        </nav>
        {user.is_admin && administration.includes(tab) && <nav aria-label="Administration">
          {administration.map(name => <button key={name} aria-pressed={tab === name} onClick={() => navigate(name)}>{name}</button>)}
        </nav>}
        {tab === "Tasks" && <WorkArea key={user.id} user={user} version={version} onError={onError} />}
        {tab === "Reports" && <Reports key={user.id} user={user} version={version} onError={onError} />}
        {user.is_admin && <>
          {tab === "Statuses" && <StatusManagement version={version} onError={onError} />}
          {tab === "Accounts" && <Accounts users={users} currentUserId={user.id} run={run} />}
          {tab === "Catalogs" && <Catalogs organizations={organizations} projects={projects} run={run} />}
          {tab === "Grants" && <GrantManagement users={users} organizations={organizations} projects={projects} run={run} version={version} onError={onError} />}
          {tab === "System status" && <SystemStatus />}
        </>}
        {!user.is_admin && tab === "My access" && <section className="workspace" aria-label="Available projects"><h2>My access</h2><p>You can always read and edit your own timesheet.</p>
          {projects.length ? <ul>{projects.map(project => <li key={project.id}>{project.name} — {project.permissions.task_read ? "Task read" : "No task read"}, {project.permissions.task_write ? "Task write" : "No task write"}</li>)}</ul> : <p>No project access is configured.</p>}
        </section>}
      </>}
      <footer>Personal work and small-team coordination.</footer>
    </main>
  );
}

function SystemStatus() {
  const [state, setState] = useState<"loading" | "connected" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    getHealth(controller.signal).then(
      () => { if (!controller.signal.aborted) setState("connected"); },
      () => { if (!controller.signal.aborted) setState("error"); },
    );
    return () => controller.abort();
  }, [attempt]);
  return <section className="workspace" aria-label="System status"><h2>System status</h2>
    <div className="connection" role="status" aria-live="polite"><span className={`dot ${state}`} aria-hidden="true" />
      {state === "loading" && "Checking backend connection…"}
      {state === "connected" && "Django API and PostgreSQL are connected."}
      {state === "error" && "Cannot connect to the backend. Check that the services are running."}
    </div><button onClick={() => setAttempt(value => value + 1)} disabled={state === "loading"}>Check connection</button>
  </section>;
}
