import { useEffect, useId, useRef, useState } from "react";
import { allPages, api } from "./api";

const referencePattern = /\[(task|remark|image):([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\]/g;
type Target = { kind: string; id: string; available: boolean; label: string; task?: string };
export type OpenReference = (task: string, remark?: string) => void;
export const contentPreview = (text: string) => text.replace(referencePattern, (_, kind) => kind === "image" ? "Image" : "Reference");
export type ImageUpload = { id: string; data: string };
export const editorImages = (data: FormData): ImageUpload[] => JSON.parse(String(data.get("images") || "[]"));
function imageId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function ContentImage({ id, reload }: { id: string; reload: number }) {
  const [failed, setFailed] = useState(false);
  const url = `/api/v1/images/${id}/?v=${reload}`;
  return failed ? <span className="unavailable-reference">Unavailable image</span>
    : <a href={url} target="_blank" rel="noreferrer"><img className="content-image" src={url} alt="Attached image" onError={() => setFailed(true)} loading="lazy" /></a>;
}

export function ContentText({ text, onOpen }: { text: string; onOpen: OpenReference }) {
  const [targets, setTargets] = useState<Target[]>([]);
  const [reload, setReload] = useState(0);
  const [failed, setFailed] = useState(false);
  const matches = [...text.matchAll(referencePattern)];
  const keys = [...new Set(matches.filter(match => match[1] !== "image").map(match => `${match[1]}:${match[2].toLowerCase()}`))];
  const signature = keys.join(",");
  const hasImages = matches.some(match => match[1] === "image");
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
    if (match[1] === "image") {
      parts.push(<ContentImage key={`${match.index}:${reload}`} id={match[2].toLowerCase()} reload={reload} />);
      previous = match.index! + match[0].length;
      continue;
    }
    const target = targets.find(item => item.kind === match[1] && item.id === match[2].toLowerCase());
    parts.push(target?.available ? <a key={match.index} href={`#${target.kind}-${target.id}`} onClick={event => {
      event.preventDefault(); onOpen(target.task!, target.kind === "remark" ? target.id : undefined);
    }}>{target.label}</a> : <span key={match.index} className="unavailable-reference">Unavailable reference</span>);
    previous = match.index! + match[0].length;
  }
  parts.push(text.slice(previous));
  return <><span className="description">{parts}</span>{(signature || hasImages) && <button type="button" className="secondary compact" onClick={() => setReload(value => value + 1)}>{failed ? "Retry references" : signature ? "Refresh references" : "Refresh images"}</button>}</>;
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

export function ContentEditor({ label, name, initialValue = "", value, onChange, images, onImagesChange, rows = 4, required = false }: {
  label: string; name?: string; initialValue?: string; value?: string; onChange?: (value: string) => void;
  images?: ImageUpload[]; onImagesChange?: (images: ImageUpload[]) => void; rows?: number; required?: boolean;
}) {
  const [local, setLocal] = useState(initialValue);
  const [localImages, setLocalImages] = useState<ImageUpload[]>([]);
  const uploads = images ?? localImages;
  const currentUploads = useRef(uploads);
  currentUploads.current = uploads;
  function setUploads(update: (items: ImageUpload[]) => ImageUpload[]) {
    const next = update(currentUploads.current);
    currentUploads.current = next; setLocalImages(next); onImagesChange?.(next);
  }
  const [message, setMessage] = useState("");
  const adding = useRef(false);
  const id = useId();
  const textarea = useRef<HTMLTextAreaElement>(null);
  const text = value ?? local;
  const change = (value: string) => { setLocal(value); onChange?.(value); };
  const currentText = useRef(text);
  currentText.current = text;
  const pending = uploads.filter(item => text.includes(`[image:${item.id}]`));
  useEffect(() => { setUploads(items => items.filter(item => text.includes(`[image:${item.id}]`))); }, [text]);
  function insert(token: string) {
      const body = currentText.current;
      const start = textarea.current?.selectionStart ?? text.length;
      const end = textarea.current?.selectionEnd ?? start;
      change(body.slice(0, start) + token + body.slice(end));
      requestAnimationFrame(() => { textarea.current?.focus(); textarea.current?.setSelectionRange(start + token.length, start + token.length); });
  }
  async function addImages(files: File[]) {
    if (adding.current || !files.length) return;
    setMessage("");
    if (pending.length + files.length > 5) { setMessage("Save at most five new images at a time."); return; }
    if (files.some(file => file.size > 2_097_152 || !["image/png", "image/jpeg", "image/webp"].includes(file.type))) {
      setMessage("Choose PNG, JPEG, or WebP images, at most 2 MiB each."); return;
    }
    adding.current = true; textarea.current?.setCustomValidity("Wait for images to finish loading.");
    try {
      const images = await Promise.all(files.map(file => new Promise<ImageUpload>((resolve, reject) => {
        const id = imageId();
        const reader = new FileReader(); reader.onerror = () => reject(new Error("Unable to read the selected image."));
        reader.onabort = () => reject(new Error("Image reading was canceled."));
        reader.onload = () => resolve({ id, data: String(reader.result).split(",")[1] });
        reader.readAsDataURL(file);
      })));
      setUploads(items => [...items, ...images]);
      insert(images.map(item => `[image:${item.id}]`).join("\n"));
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to read images."); }
    finally { adding.current = false; textarea.current?.setCustomValidity(""); }
  }
  return <><label htmlFor={id}>{label}</label><textarea id={id} ref={textarea} name={name} value={text} onChange={event => change(event.target.value)} rows={rows} required={required} onPaste={event => {
    const files = Array.from(event.clipboardData.files);
    if (files.length) { event.preventDefault(); void addImages(files); }
  }} />
    <ReferencePicker onInsert={insert} />
    <label>Add images<input type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={event => {
      void addImages(Array.from(event.target.files ?? [])); event.target.value = "";
    }} /></label>
    <p className="content-help">PNG, JPEG or WebP, up to 2 MiB each. You can paste a screenshot into the text. Images upload when you save.</p>
    <input type="hidden" name="images" value={JSON.stringify(pending)} />
    {!!pending.length && <p role="status">{pending.length} new image(s) ready to save. Remove their image tokens to discard them.</p>}
    {message && <p role="alert">{message}</p>}
  </>;
}
