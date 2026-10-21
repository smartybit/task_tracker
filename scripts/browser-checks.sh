#!/bin/sh
set -eu

# Run inside the disposable Playwright container, with frontend as working dir.
# Only the temporary Vite process belongs to this script; API/database are external.
npm ci --cache /tmp/npm-cache
npm run build
npm run dev -- --host 127.0.0.1 --port 5180 &
task_tracker_vite_pid=$!
trap 'kill "$task_tracker_vite_pid" 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
node /checks/wait-ready.mjs
npm run test:e2e
