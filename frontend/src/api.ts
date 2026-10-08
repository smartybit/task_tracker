export interface Health {
  status: "ok";
  database: "postgresql";
  api_version: "v1";
}

export async function getHealth(signal: AbortSignal): Promise<Health> {
  const response = await fetch("/api/v1/health/", { signal });
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
