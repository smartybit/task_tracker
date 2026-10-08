import { useEffect, useState } from "react";
import { api, allPages, ApiError, getHealth, type User, type Organization, type Project } from "./api";
import { Accounts, Catalogs, GrantManagement } from "./Management";

export function App() {
  const [state, setState] = useState<"loading" | "connected" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const [user, setUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tab, setTab] = useState("Accounts");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);

  function onError(error: unknown) {
    setMessage(error instanceof Error ? error.message : "The request failed.");
    if (error instanceof ApiError && error.code === "authentication_required") setUser(null);
  }
  async function refresh() {
    const me = await api<User>("auth/me/");
    setUser(me);
    const [orgs, available, accounts] = await Promise.all([allPages<Organization>("organizations/"), allPages<Project>("projects/"), me.is_admin ? allPages<User>("users/") : Promise.resolve([])]);
    setOrganizations(orgs); setProjects(available); setUsers(accounts); setVersion(value => value + 1);
  }
  useEffect(() => { void refresh().catch(error => {
    if (!(error instanceof ApiError && error.code === "authentication_required")) onError(error);
  }); }, []);
  async function run(action: () => Promise<unknown>) {
    setMessage("");
    try { await action(); await refresh(); setMessage("Changes saved."); }
    catch (error) { onError(error); if (error instanceof ApiError && error.code === "permission_denied") void refresh().catch(onError); }
  }

  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    getHealth(controller.signal).then(
      () => { if (!controller.signal.aborted) setState("connected"); },
      () => { if (!controller.signal.aborted) setState("error"); },
    );
    return () => controller.abort();
  }, [attempt]);

  return (
    <main>
      <header><span className="brand">Task Tracker</span><span>Accounts and project access</span></header>
      <section className="welcome" aria-labelledby="welcome">
        <p className="eyebrow">Your work, in perspective</p>
        <h1 id="welcome">A place for tasks<br />and the time behind them.</h1>
        <p className="intro">Accounts and project access are available. Task management,
          time recording, and reports will arrive in later implementation stages.</p>
        <div className="connection" role="status" aria-live="polite">
          <span className={`dot ${state}`} aria-hidden="true" />
          {state === "loading" && "Checking backend connection…"}
          {state === "connected" && "Django API and PostgreSQL are connected."}
          {state === "error" && "Cannot connect to the backend. Check that the services are running."}
        </div>
        <button onClick={() => setAttempt(value => value + 1)} disabled={state === "loading"}>
          Check connection
        </button>
      </section>
      {message && <p role="alert">{message}</p>}
      {!user ? <section className="workspace" aria-label="Sign in"><h2>Sign in</h2>
        <form aria-label="Sign in" onSubmit={event => {
          event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setMessage("");
          void api("auth/login/", "POST", { email: data.get("email"), password: data.get("password") }).then(refresh).catch(onError).finally(() => setBusy(false));
        }}><label>Email<input name="email" type="email" autoComplete="username" required /></label>
          <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
          <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button></form>
      </section> : <>
        <div className="session"><strong>Signed in as {user.display_name || user.email}</strong><button className="secondary" onClick={() => { void api("auth/logout/", "POST", {}).then(() => { setUser(null); setUsers([]); setProjects([]); setMessage(""); }).catch(onError); }}>Sign out</button><button className="secondary" onClick={() => { void refresh().catch(onError); }}>Refresh access</button></div>
        {user.is_admin ? <>
          <nav aria-label="Management">{["Accounts", "Catalogs", "Grants"].map(name => <button key={name} aria-pressed={tab === name} onClick={() => { setTab(name); setMessage(""); }}>{name}</button>)}</nav>
          {tab === "Accounts" && <Accounts users={users} run={run} />}
          {tab === "Catalogs" && <Catalogs organizations={organizations} projects={projects} run={run} />}
          {tab === "Grants" && <GrantManagement users={users} organizations={organizations} projects={projects} run={run} version={version} onError={onError} />}
        </> : <section className="workspace" aria-label="Available projects"><h2>Your projects</h2><p>You can always read and edit your own timesheet once time recording is available.</p>
          {projects.length ? <ul>{projects.map(project => <li key={project.id}>{project.name} — {project.permissions.task_read ? "Task read" : "No task read"}, {project.permissions.task_write ? "Task write" : "No task write"}</li>)}</ul> : <p>No project access is configured.</p>}
        </section>}
      </>}
      <footer>Personal work and small-team coordination.</footer>
    </main>
  );
}
