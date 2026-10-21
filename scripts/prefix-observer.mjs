import { writeFileSync } from 'node:fs';

let running = true;
let count = 0;
process.on('SIGTERM', () => { running = false; });
while (running) {
  const response = await fetch(process.env.PREFIX_OBSERVER_URL, { signal: AbortSignal.timeout(5000) });
  if (!response.ok || response.headers.get('X-Task-Tracker-Instance') !== 'prefix-b') {
    throw new Error('Sibling instance became unavailable during the other instance update.');
  }
  count++;
  writeFileSync('/tmp/observer-count', String(count));
  await new Promise(resolve => setTimeout(resolve, 500));
}
console.log(`Sibling instance remained healthy across ${count} observations.`);
