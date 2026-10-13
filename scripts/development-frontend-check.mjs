import assert from 'node:assert/strict';

const base = `http://127.0.0.1:5173${process.env.APP_BASE_PATH}api/v1/`;
const origin = `http://127.0.0.1:${process.env.FRONTEND_PORT}`;
const response = await fetch(`${base}auth/csrf/`);
assert.equal(response.status, 200);
assert.equal(response.headers.get('X-Task-Tracker-Base-Path'), process.env.APP_BASE_PATH);
assert.equal(response.headers.get('X-Task-Tracker-Instance'), process.env.INSTANCE_ID);
const token = (await response.json()).csrf_token;
const cookies = response.headers.getSetCookie();
assert.equal(cookies.length, 1);
assert.ok(cookies[0].includes(`Path=${process.env.APP_BASE_PATH}`));
assert.ok(!cookies[0].includes('; Secure'));
const password = process.env.INSTANCE_CHECK_PHASE === 'after' && process.env.INSTANCE_ID.endsWith('-a')
  ? 'development-instance-synthetic-replacement' : 'development-instance-synthetic-password';
const signedIn = await fetch(`${base}auth/login/`, {
  method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token,
    Origin: origin, Cookie: cookies.map(cookie => cookie.split(';')[0]).join('; ') },
  body: JSON.stringify({ email: 'instance-check@example.test', password }),
});
assert.equal(signedIn.status, 200, await signedIn.text());
console.log(`${process.env.INSTANCE_ID}: prefixed frontend, scoped HTTP cookie and configured-origin CSRF login passed.`);
