import { useEffect, useState } from "react";
import { getHealth } from "./api";

export function App() {
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

  return (
    <main>
      <header><span className="brand">Task Tracker</span><span>Foundation build</span></header>
      <section aria-labelledby="welcome">
        <p className="eyebrow">Your work, in perspective</p>
        <h1 id="welcome">A place for tasks<br />and the time behind them.</h1>
        <p className="intro">The application foundation is taking shape. Task management,
          timesheets, and reports will arrive in the next implementation stages.</p>
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
      <footer>Personal work and small-team coordination.</footer>
    </main>
  );
}
