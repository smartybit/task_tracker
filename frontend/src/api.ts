import { apiUrl } from "./urls";
export { apiUrl } from "./urls";

export interface Health {
  status: "ok";
  database: "postgresql";
  api_version: "v1";
}

export async function getHealth(signal: AbortSignal): Promise<Health> {
  const response = await fetch(apiUrl("health/"), { signal });
  if (!response.ok) throw new Error("The backend is unavailable.");
  const health: unknown = await response.json();
  if (
    typeof health !== "object" || health === null ||
    !("status" in health) || health.status !== "ok" ||
    !("database" in health) || health.database !== "postgresql" ||
    !("api_version" in health) || health.api_version !== "v1"
  ) throw new Error("Unexpected backend response.");
  return health as Health;
}

export interface User {
  id: string; email: string; display_name: string; is_admin: boolean; is_active: boolean;
  read_others_timesheets: boolean; write_others_timesheets: boolean;
}
export interface Flags { task_read: boolean; task_write: boolean; remark_read: boolean; remark_write: boolean }
export interface Organization { id: string; name: string }
export interface Project extends Organization { organization: string; permissions: Flags }
export interface Grants {
  organizations: (Flags & { organization: string })[];
  projects: (Flags & { project: string })[];
  effective_projects: (Flags & { project: string })[];
}

export class ApiError extends Error {
  constructor(public code: string, message: string, public fields: Record<string, unknown> = {}) { super(message); }
}
let csrfToken = "";
const errorDetails = (value: unknown): string[] => typeof value === "string" ? [value]
  : value && typeof value === "object" ? Object.values(value).flatMap(errorDetails) : [];
export async function api<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  if (method !== "GET" && !csrfToken) {
    const csrf = await api<{ csrf_token: string }>("auth/csrf/");
    csrfToken = csrf.csrf_token;
  }
  const response = await fetch(apiUrl(path), {
    method, credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(method !== "GET" ? { "X-CSRFToken": csrfToken } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  if (!response.ok) {
    if (data.code === "csrf_failed") csrfToken = "";
    const details = errorDetails(data.fields).join(" ");
    throw new ApiError(data.code ?? "request_failed", [data.message ?? "The request failed.", details].filter(Boolean).join(" "), data.fields ?? {});
  }
  if (typeof data.csrf_token === "string") csrfToken = data.csrf_token;
  return data as T;
}

export async function allPages<T>(path: string): Promise<T[]> {
  const result: T[] = [];
  let next: number | null = 1;
  while (next !== null) {
    const page: { results: T[]; next: number | null } = await api(`${path}${path.includes("?") ? "&" : "?"}page=${next}`);
    result.push(...page.results);
    next = page.next;
  }
  return result;
}
