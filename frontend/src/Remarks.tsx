import { useEffect, useRef, useState, type ReactNode } from "react";
import { allPages, api, ApiError, type Flags, type Project } from "./api";
import { ContentEditor, ContentText, contentPreview, editorImages, type ImageUpload, type OpenReference } from "./Content";

interface Remark {
  id: string; task: string; author: string; author_name: string; body: string;
  starred: boolean; created_at: string; edited_at: string | null; revision: number;
}
type Edit = { remark: Remark; body: string; images: ImageUpload[] };

export function Remarks({ task, project, version, onError, children, onOpen, targetRemark }: {
  task: string; project: string; version: number; onError: (error: unknown) => void; children?: ReactNode;
  onOpen: OpenReference; targetRemark?: string;
}) {
  const [rows, setRows] = useState<Remark[]>([]);
  const [permissions, setPermissions] = useState<Flags | null>(null);
  const [draft, setDraft] = useState("");
  const [draftImages, setDraftImages] = useState<ImageUpload[]>([]);
  const [edit, setEdit] = useState<Edit | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [blocked, setBlocked] = useState(true);
  const inFlight = useRef(false);
  const generation = useRef(0);
  const errorHandler = useRef(onError);
  const focused = useRef("");
  errorHandler.current = onError;

  async function load() {
    const request = ++generation.current;
    setLoading(true); setBlocked(true); setRows([]); setPermissions(null);
    try {
      const current = await api<Project>(`projects/${project}/`);
      const readable = current.permissions.task_read && current.permissions.remark_read;
      const records = readable ? await allPages<Remark>(`tasks/${task}/remarks/`) : [];
      if (request !== generation.current) return false;
      setRows(records); setPermissions(current.permissions); setBlocked(false);
      return true;
    } catch (error) {
      if (request === generation.current) {
        setMessage(error instanceof Error ? error.message : "Unable to load remarks.");
        if (error instanceof ApiError && error.code === "authentication_required") errorHandler.current(error);
      }
      return false;
    } finally { if (request === generation.current) setLoading(false); }
  }

  useEffect(() => {
    void load();
    return () => { generation.current += 1; };
  }, [task, project, version]);

  useEffect(() => {
    if (!loading && targetRemark && focused.current !== targetRemark) {
      const original = document.getElementById(`remark-${targetRemark}`);
      if (original) { original.scrollIntoView({ block: "center" }); original.focus(); focused.current = targetRemark; }
      else if (permissions) setMessage("The referenced remark is unavailable.");
    }
  }, [loading, rows, targetRemark, permissions]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (draft.trim() || (edit && edit.body !== edit.remark.body)) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [draft, edit]);

  async function change(path: string, method: string, body: unknown, success: string) {
    if (inFlight.current || blocked) return;
    inFlight.current = true; setBusy(true); setMessage("");
    try {
      await api(path, method, body);
      if (method === "POST" && path.endsWith("/remarks/")) { setDraft(""); setDraftImages([]); }
      setEdit(null);
      const loaded = await load();
      setMessage(loaded ? success : `${success} Reload failed; reload remarks before another change.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The request failed.");
      if (error instanceof ApiError) {
        if (["stale_revision", "not_found", "permission_denied"].includes(error.code)) setBlocked(true);
        if (["not_found", "permission_denied"].includes(error.code)) { setRows([]); setPermissions(null); }
        if (error.code === "authentication_required") errorHandler.current(error);
      }
    } finally { inFlight.current = false; setBusy(false); }
  }

  const readable = permissions?.task_read && permissions.remark_read;
  const writable = permissions?.task_read && permissions.remark_write;
  const stars = rows.filter(row => row.starred);
  const target = (id: string) => `remark-${id}`;
  const stamp = (value: string) => <time dateTime={value}>{new Date(value).toLocaleString()}</time>;

  return <section className="remarks" aria-label="Task remarks">
    {readable &&
      <section aria-label="Starred remarks"><h5>Starred remarks · shared with everyone who can read remarks</h5>
        {stars.length ? <ol className="starred-remarks">{stars.map(row => <li key={row.id}>
          <a href={`#${target(row.id)}`} onClick={event => {
            event.preventDefault(); const original = document.getElementById(target(row.id));
            original?.scrollIntoView({ block: "center" }); original?.focus();
          }}><span className="description">{contentPreview(row.body)}</span> — {row.author_name}</a>
        </li>)}</ol> : <p>No starred remarks.</p>}
      </section>
    }
    {children}
    <h4>Remarks</h4>
    {message && <p role="alert">{message}</p>}
    <button className="secondary compact" disabled={busy || loading} onClick={() => {
      if (edit && edit.body !== edit.remark.body && !window.confirm("Discard your remark edit and reload remarks?")) return;
      setEdit(null); setMessage(""); void load();
    }}>Reload remarks</button>
    {loading && <p role="status">Loading remarks…</p>}
    {blocked && !loading && <p>Reload remarks to review the latest content and access before changing it. Your unsaved text is retained.</p>}
    {readable && <>
      <ol className="remark-stream" aria-label="Chronological remarks">{rows.map(row => <li key={row.id}>
        <article id={target(row.id)} tabIndex={-1} aria-label={`Remark by ${row.author_name}`}>
          <p className="remark-meta">{row.author_name} · {stamp(row.created_at)}{row.edited_at && <> · Edited {stamp(row.edited_at)}</>}{row.starred && " · Starred"}</p>
          <p className="description"><ContentText text={row.body} onOpen={onOpen} /></p>
          {writable && <fieldset disabled={busy || blocked}>
            {edit?.remark.id === row.id ? <form aria-label="Edit remark" onSubmit={event => {
              event.preventDefault(); void change(`remarks/${row.id}/`, "PATCH", { body: edit.body, images: editorImages(new FormData(event.currentTarget)), expected_revision: edit.remark.revision }, "Remark saved.");
            }}>
              <ContentEditor label="Remark text" value={edit.body} onChange={body => setEdit(current => current ? { ...current, body } : null)} images={edit.images} onImagesChange={images => setEdit(current => current ? { ...current, images } : null)} required />
              <button disabled={!edit.body.trim()}>Save remark</button>
              <button type="button" className="secondary compact" onClick={() => setEdit(null)}>Cancel remark edit</button>
            </form> : <>
              <button className="secondary compact" disabled={edit !== null} onClick={() => setEdit({ remark: row, body: row.body, images: [] })}>Edit remark</button>
              <button className="secondary compact" disabled={edit !== null} aria-pressed={row.starred} onClick={() => {
                void change(`remarks/${row.id}/star/`, "POST", { starred: !row.starred, expected_revision: row.revision }, row.starred ? "Star removed." : "Remark starred.");
              }}>{row.starred ? "Unstar remark" : "Star remark"}</button>
              <button className="secondary compact" disabled={edit !== null} onClick={() => {
                if (window.confirm("Permanently delete this remark?")) void change(`remarks/${row.id}/`, "DELETE", { expected_revision: row.revision }, "Remark deleted.");
              }}>Delete remark</button>
            </>}
          </fieldset>}
        </article>
      </li>)}</ol>
      {!rows.length && <p>No remarks yet.</p>}
    </>}
    {permissions && !readable && <p>Remark reading is not permitted.</p>}
    {writable && <form aria-label="Post remark" onSubmit={event => {
      event.preventDefault(); void change(`tasks/${task}/remarks/`, "POST", { body: draft, images: editorImages(new FormData(event.currentTarget)) }, "Remark posted.");
    }}><fieldset disabled={busy || blocked}>
      <ContentEditor label="New remark" value={draft} onChange={setDraft} images={draftImages} onImagesChange={setDraftImages} required />
      <button disabled={!draft.trim() || edit !== null}>Post remark</button>
    </fieldset></form>}
    {blocked && !writable && (draft || (edit && edit.body !== edit.remark.body)) && <p className="description" aria-label="Unsaved remark text">{edit && edit.body !== edit.remark.body ? edit.body : draft}</p>}
    {blocked && !writable && !!(draftImages.length || edit?.images.length) && <p>Unsaved images are retained. Restore remark access and reload before saving.</p>}
  </section>;
}
