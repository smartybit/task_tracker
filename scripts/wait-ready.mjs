import { setTimeout } from "node:timers/promises";

const url = process.env.BASE_URL;
if (!url) throw new Error("BASE_URL is required for browser readiness checks.");
const deadline = Date.now() + 30_000;
let ready = false;
while (Date.now() < deadline) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(2_000) });
    if (response.ok) { ready = true; break; }
  } catch { /* Retry only until the readiness deadline. */ }
  await setTimeout(250);
}
if (!ready) throw new Error("Frontend did not become ready within 30 seconds.");
