export function canonicalBasePath(value: string): string {
  if (value !== value.trim() || !/^\/(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]*$/.test(value)) {
    throw new Error("APP_BASE_PATH must be / or an absolute path of plain URL segments.");
  }
  return value.endsWith("/") ? value : `${value}/`;
}

export function instanceConfig(env: Record<string, string | undefined>) {
  const basePath = canonicalBasePath(env.APP_BASE_PATH ?? "/");
  const instanceId = env.INSTANCE_ID ?? "task-tracker-dev";
  if (instanceId !== instanceId.trim() || !/^[a-z0-9][a-z0-9-]{0,62}$/.test(instanceId)) {
    throw new Error("INSTANCE_ID must be a lowercase alphanumeric/hyphen slug, at most 63 characters.");
  }
  return { basePath, instanceId };
}

export function buildApiUrl(basePath: string, endpoint: string): string {
  const path = endpoint.split("?", 1)[0];
  if (!path || path.startsWith("/") || !/^[A-Za-z0-9_./-]+$/.test(path)
      || path.includes("//") || path.split("/").some(segment => segment === "." || segment === "..")
      || /[#\r\n]/.test(endpoint)) throw new Error("API endpoints must be relative paths without traversal or fragments.");
  return `${canonicalBasePath(basePath)}api/v1/${endpoint}`;
}
