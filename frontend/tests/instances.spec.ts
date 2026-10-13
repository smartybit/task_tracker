import { randomUUID } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { expect, test, type APIRequestContext, type BrowserContext } from '@playwright/test';
import { appURL } from './helpers/urls';

const urls = [appURL, process.env.PREFIX_OTHER_URL!];
const password = 'prefix-instance-long-password';
const replacement = 'prefix-server-recovery-long-password';
const screenshot = readFileSync('tests/fixtures/screenshot.png');
const stateFile = `.artifacts/${process.env.PREFIX_LABEL ?? 'prefix-test'}-sessions.json`;
const identityFile = `.artifacts/${process.env.PREFIX_LABEL ?? 'prefix-test'}-identities.json`;
const endpoint = (url: string, path: string) => `${url}api/v1/${path}`;
async function login(request: APIRequestContext, url: string, email = 'admin@example.test', secret = 'synthetic-test-only-password') {
  const token = (await (await request.get(endpoint(url, 'auth/csrf/'))).json()).csrf_token;
  const response = await request.post(endpoint(url, 'auth/login/'), {
    headers: { 'X-CSRFToken': token, Origin: new URL(url).origin }, data: { email, password: secret },
  });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()).csrf_token as string;
}
async function write(request: APIRequestContext, url: string, token: string, path: string, data: unknown, method = 'POST') {
  const response = await request.fetch(endpoint(url, path), {
    method, headers: { 'X-CSRFToken': token, Origin: new URL(url).origin }, data,
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

if (process.env.PREFIX_PHASE === 'after') {
  test('instances: targeted server reset and replacement preserve the other live session and both datasets', async ({ browser }) => {
    const context = await browser.newContext({ ignoreHTTPSErrors: true, storageState: stateFile });
    try {
      const identities = JSON.parse(readFileSync(identityFile, 'utf8'));
      expect((await context.request.get(endpoint(urls[0], 'auth/me/'))).status()).toBe(403);
      expect((await context.request.get(endpoint(urls[1], 'auth/me/'))).status()).toBe(200);
      await login(context.request, urls[0], identities[0].email, replacement);
      for (const [index, url] of urls.entries()) {
        const task = await context.request.get(endpoint(url, `tasks/${identities[index].task}/`));
        expect(task.status()).toBe(200);
        expect((await task.json()).title).toBe(identities[index].title);
        expect(await (await context.request.get(endpoint(url, `images/${identities[index].image}/`))).body()).toEqual(screenshot);
        const page = await context.newPage();
        await page.goto(url);
        await expect(page.getByText('Signed in as', { exact: false })).toBeVisible();
      }
    } finally { await context.close(); }
  });
} else {
  test('instances: mounted assets, boundary errors, CSRF and redirects retain their own prefix', async ({ request }) => {
    for (const [index, url] of urls.entries()) {
      const html = await (await request.get(url)).text();
      expect(html).toContain('<title>Task Tracker</title>');
      for (const match of html.matchAll(/(?:src|href)="([^\"]+)"/g)) {
        if (match[1].startsWith('/')) expect(match[1]).toMatch(new RegExp(`^${new URL(url).pathname}`));
      }
      const health = await request.get(endpoint(url, 'health/'));
      expect(health.status()).toBe(200);
      expect(health.headers()['x-task-tracker-instance']).toBe(index === 0 ? 'prefix-a' : 'prefix-b');
      expect(health.headers()['x-task-tracker-base-path']).toBe(new URL(url).pathname);
      const redirect = await request.get(`${url.slice(0, -1)}?kept=yes`, { maxRedirects: 0 });
      expect(redirect.status()).toBe(308);
      expect(redirect.headers().location).toBe(`${new URL(url).pathname}?kept=yes`);
      const apiRedirect = await request.get(endpoint(url, 'health?kept=yes'), { maxRedirects: 0 });
      expect(apiRedirect.status()).toBe(301);
      expect(apiRedirect.headers().location).toBe(`${new URL(url).pathname}api/v1/health/?kept=yes`);
      expect((await request.get(endpoint(url, 'missing/'))).status()).toBe(404);
      expect((await request.get(`${url}assets/missing.js`)).status()).toBe(404);
      expect((await request.get(`${url.slice(0, -1)}-other/`)).status()).toBe(404);
      const token = (await (await request.get(endpoint(url, 'auth/csrf/'))).json()).csrf_token;
      const denied = await request.post(endpoint(url, 'auth/login/'), {
        headers: { 'X-CSRFToken': token, Origin: 'https://evil.invalid' },
        data: { email: 'admin@example.test', password: 'synthetic-test-only-password' },
      });
      expect(denied.status()).toBe(403);
      expect((await denied.json()).code).toBe('csrf_failed');
    }
    expect((await request.get(new URL('/api/v1/health/', urls[0]).href)).status()).toBe(404);
  });

  test('instances: same-browser accounts, data, images, CSV and session changes remain independent', async ({ browser }, info) => {
    test.setTimeout(180_000);
    const admin = await browser.newContext({ ignoreHTTPSErrors: true });
    const context = await browser.newContext({ ignoreHTTPSErrors: true });
    const identities: { email: string; id: string; task: string; title: string; image: string; token: string; adminToken: string }[] = [];
    try {
      const email = `prefix-same-${Date.now()}@example.test`;
      for (const [index, url] of urls.entries()) {
        const adminToken = await login(admin.request, url);
        const user = await write(admin.request, url, adminToken, 'users/', { email, password, is_admin: true });
        const organization = await write(admin.request, url, adminToken, 'organizations/', { name: `Prefix organization ${index}` });
        const project = await write(admin.request, url, adminToken, 'projects/', { name: `Prefix project ${index}`, organization: organization.id });
        await write(admin.request, url, adminToken, `users/${user.id}/grants/projects/${project.id}/`,
          { task_read: true, task_write: true, remark_read: true, remark_write: true }, 'PUT');
        const token = await login(context.request, url, email, password);
        const statuses = (await (await context.request.get(endpoint(url, 'statuses/'))).json()).results;
        const image = randomUUID();
        const title = `Prefix private work ${index}`;
        const payload = { title, project: project.id, status: statuses.find((s: { name: string }) => s.name === 'In Progress').id,
          description: `Prefix content ${index} [image:${image}]`, images: [{ id: image, data: screenshot.toString('base64') }] };
        const preview = await write(context.request, url, token, 'tasks/preview/', payload);
        const task = await write(context.request, url, token, 'tasks/', { ...payload, confirm: true, expected_domain_revision: preview.domain_revision });
        await write(context.request, url, token, `tasks/${task.id}/remarks/`, { body: `Prefix remark ${index} [task:${task.id}]` });
        const dayPath = `timesheets/${user.id}/days/2020-10-09/`;
        let day = await (await context.request.get(endpoint(url, dayPath))).json();
        await write(context.request, url, token, `timesheets/${user.id}/commands/`, {
          command: 'start', date: '2020-10-09', at: '2020-10-09T09:00:00Z', task: task.id, expected_revision: day.revision,
        });
        day = await (await context.request.get(endpoint(url, dayPath))).json();
        await write(context.request, url, token, `timesheets/${user.id}/commands/`, {
          command: 'end_day', date: '2020-10-09', at: `2020-10-09T${index === 0 ? '10' : '11'}:00:00Z`,
          session: day.sessions.at(-1).id, expected_revision: day.revision,
        });
        identities.push({ email, id: user.id, task: task.id, title, image, token, adminToken });
      }
      expect(identities[0].id).not.toBe(identities[1].id);
      const cookies = await context.cookies();
      for (const [index, url] of urls.entries()) {
        for (const suffix of ['session', 'csrf']) {
          const cookie = cookies.find(c => c.name === `task_tracker_prefix-${index === 0 ? 'a' : 'b'}_${suffix}`)!;
          expect(cookie.path).toBe(new URL(url).pathname);
          expect(cookie.secure).toBe(true);
          expect(cookie.sameSite).toBe('Lax');
          if (suffix === 'session') expect(cookie.httpOnly).toBe(true);
        }
        const local = identities[index], other = identities[1 - index];
        expect(await (await context.request.get(endpoint(url, `images/${local.image}/`))).body()).toEqual(screenshot);
        expect((await context.request.get(endpoint(url, `images/${other.image}/`))).status()).toBe(404);
        expect((await context.request.get(endpoint(url, `tasks/${other.task}/`))).status()).toBe(404);
        const resolved = await write(context.request, url, local.token, 'references/resolve/', {
          targets: [{ kind: 'task', id: local.task }, { kind: 'task', id: other.task }],
        });
        expect(resolved.results.map((r: { available: boolean }) => r.available)).toEqual([true, false]);
        const search = await (await context.request.get(endpoint(url, `search/?q=${encodeURIComponent(local.title)}`))).json();
        expect(search.results.some((r: { id: string }) => r.id === other.task)).toBe(false);
        const report = await (await context.request.get(endpoint(url, 'reports/projects/?from=2020-10-09&to=2020-10-09'))).json();
        expect(report.total_hours).toBe(index === 0 ? '1.00' : '2.00');
        const page = await context.newPage();
        const escaped: string[] = [];
        page.on('request', request => { const path = new URL(request.url()).pathname;
          if (path.includes('/api/v1/') && !path.startsWith(new URL(url).pathname)) escaped.push(path); });
        await page.goto(url);
        await expect(page.getByText('Signed in as', { exact: false })).toBeVisible();
        await page.getByRole('button', { name: 'Tasks', exact: true }).click();
        await page.getByRole('list', { name: 'Task list', exact: true }).getByRole('button', { name: local.title, exact: true }).click();
        const img = page.getByRole('dialog', { name: 'Task description', exact: true }).getByRole('img', { name: 'Attached image', exact: true });
        await expect.poll(() => img.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBe(128);
        expect(await img.getAttribute('src')).toContain(`${new URL(url).pathname}api/v1/images/`);
        await page.reload();
        await page.getByRole('button', { name: 'Reports', exact: true }).click();
        const region = page.getByRole('region', { name: 'Reports', exact: true });
        await expect(region.getByRole('table')).toBeVisible({ timeout: 15000 });
        await region.getByLabel('From date', { exact: true }).fill('2020-10-09');
        await region.getByLabel('To date', { exact: true }).fill('2020-10-09');
        await expect(region.getByText('Total recorded work:', { exact: false })).toContainText(index === 0 ? '1.00' : '2.00');
        const downloaded = page.waitForEvent('download');
        await region.getByRole('button', { name: 'Download CSV', exact: true }).click();
        const csv = readFileSync((await (await downloaded).path())!, 'utf8');
        expect(csv).toContain(local.title); expect(csv).not.toContain(other.title);
        expect(escaped).toEqual([]);
        await page.screenshot({ path: info.outputPath(`instance-${index}.png`), fullPage: true });
      }
      // Actual logout deletion must not remove the sibling's session cookie.
      const logout = await context.request.post(endpoint(urls[0], 'auth/logout/'), {
        headers: { 'X-CSRFToken': identities[0].token, Origin: new URL(urls[0]).origin }, data: {},
      });
      expect(logout.status()).toBe(200);
      expect(logout.headers()['set-cookie']).toContain(`Path=${new URL(urls[0]).pathname}`);
      expect((await context.request.get(endpoint(urls[0], 'auth/me/'))).status()).toBe(403);
      expect((await context.request.get(endpoint(urls[1], 'auth/me/'))).status()).toBe(200);
      identities[0].token = await login(context.request, urls[0], email, password);
      await write(admin.request, urls[0], identities[0].adminToken, `users/${identities[0].id}/password-reset/`, { password: replacement });
      expect((await context.request.get(endpoint(urls[0], 'auth/me/'))).status()).toBe(403);
      expect((await context.request.get(endpoint(urls[1], 'auth/me/'))).status()).toBe(200);
      identities[0].token = await login(context.request, urls[0], email, replacement);
      await write(admin.request, urls[0], identities[0].adminToken, `users/${identities[0].id}/`, { is_active: false }, 'PATCH');
      expect((await context.request.get(endpoint(urls[0], 'auth/me/'))).status()).toBe(403);
      expect((await context.request.get(endpoint(urls[1], 'auth/me/'))).status()).toBe(200);
      await write(admin.request, urls[0], identities[0].adminToken, `users/${identities[0].id}/`, { is_active: true }, 'PATCH');
      // Restore the original password so the later server command performs a real change.
      await write(admin.request, urls[0], identities[0].adminToken, `users/${identities[0].id}/password-reset/`, { password });
      await login(context.request, urls[0], email, password);
      mkdirSync('.artifacts', { recursive: true });
      await context.storageState({ path: stateFile });
      writeFileSync(identityFile, JSON.stringify(identities.map(({ email, task, title, image }) => ({ email, task, title, image }))));
    } finally { await admin.close(); await context.close(); }
  });
}
