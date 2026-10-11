import { readFile } from 'node:fs/promises';
import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

const baseURL = process.env.BASE_URL ?? 'http://frontend:5173';
const password = 'browser-report-long-password';
const from = '2020-10-09', to = '2020-10-10';
const rootTitle = 'Report root, "quoted"\nЗадача';
async function authenticate(request: APIRequestContext, email: string, secret = password) {
  const csrf = await (await request.get(`${baseURL}/api/v1/auth/csrf/`)).json();
  const response = await request.post(`${baseURL}/api/v1/auth/login/`, {
    headers: { 'X-CSRFToken': csrf.csrf_token, Origin: baseURL }, data: { email, password: secret },
  });
  expect(response.status()).toBe(200);
  return (await response.json()).csrf_token as string;
}
async function setup(browser: Browser, key: string, readOthers = false) {
  key = `${key}-${Date.now()}`;
  const admin = await browser.newContext();
  const token = await authenticate(admin.request, 'admin@example.test', 'synthetic-test-only-password');
  async function write(path: string, data: unknown, method = 'POST') {
    const response = await admin.request.fetch(`${baseURL}/api/v1/${path}`, {
      method, headers: { 'X-CSRFToken': token, Origin: baseURL }, data,
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.status() === 204 ? null : response.json();
  }
  const person = await write('users/', { email: `report-${key}@example.test`, display_name: 'Алиса, "A"',
    password, read_others_timesheets: true, write_others_timesheets: true });
  const colleague = await write('users/', { email: `report-colleague-${key}@example.test`, display_name: `Report colleague ${key}`, password });
  const org = await write('organizations/', { name: `Report org ${key}` });
  const project = await write('projects/', { name: `Readable ${key}`, organization: org.id });
  const other = await write('projects/', { name: `Other ${key}`, organization: org.id });
  for (const p of [project, other]) for (const u of [person, colleague]) {
    await write(`users/${u.id}/grants/projects/${p.id}/`, { task_read: true, task_write: true }, 'PUT');
  }
  const actor = await browser.newContext();
  const actorToken = await authenticate(actor.request, person.email);
  async function actorWrite(path: string, data: unknown, method = 'POST') {
    const response = await actor.request.fetch(`${baseURL}/api/v1/${path}`, {
      method, headers: { 'X-CSRFToken': actorToken, Origin: baseURL }, data,
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  }
  const statuses = (await (await actor.request.get(`${baseURL}/api/v1/statuses/`)).json()).results;
  async function task(title: string, p = project, parent: string | null = null) {
    const data = { title, project: p.id, parent, status: statuses.find((s: { name: string }) => s.name === 'In Progress').id };
    const preview = await actorWrite('tasks/preview/', data);
    return actorWrite('tasks/', { ...data, confirm: true, expected_domain_revision: preview.domain_revision });
  }
  const root = await task(rootTitle);
  const child = await task('Report child', project, root.id);
  const leaf = await task('Report leaf', project, child.id);
  const hidden = await task('Other project work', other);
  async function day(date: string, owner = person.id) {
    return (await actor.request.get(`${baseURL}/api/v1/timesheets/${owner}/days/${date}/`)).json();
  }
  async function command(date: string, kind: string, extra: Record<string, unknown>, owner = person.id) {
    return actorWrite(`timesheets/${owner}/commands/`, {
      command: kind, date, expected_revision: (await day(date, owner)).revision, ...extra,
    });
  }
  async function start(date: string, owner = person.id) {
    await command(date, 'start', { at: `${date}T09:00:00Z`, task: root.id }, owner);
    return (await day(date, owner)).sessions.at(-1).id as string;
  }
  const session = await start(from);
  await command(from, 'append', { session, at: `${from}T10:00:00Z`, task: child.id });
  await command(from, 'append', { session, at: `${from}T12:00:00Z`, task: leaf.id });
  await command(from, 'break', { session, at: `${from}T12:30:00Z` });
  await command(from, 'end_day', { session, at: `${from}T13:00:00Z` });
  await start(to);
  const bobSession = await start(from, colleague.id);
  await command(from, 'append', { session: bobSession, at: `${from}T10:00:00Z`, task: hidden.id }, colleague.id);
  await command(from, 'end_day', { session: bobSession, at: `${from}T12:00:00Z` }, colleague.id);
  if (!readOthers) await write(`users/${person.id}/`, { read_others_timesheets: false }, 'PATCH');
  return { person, colleague, project, other, root, child, leaf, day, write, actorWrite, command,
    close: async () => { await actor.close(); await admin.close(); } };
}
const reports = (page: Page) => page.getByRole('region', { name: 'Reports', exact: true });
async function login(page: Page, email: string, secret = password) {
  await page.goto('/');
  const form = page.getByRole('form', { name: 'Sign in', exact: true });
  await form.getByLabel('Email', { exact: true }).fill(email);
  await form.getByLabel('Password', { exact: true }).fill(secret);
  await form.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByText('Signed in as', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Reports', exact: true }).click();
  await expect(reports(page).getByRole('table')).toBeVisible({ timeout: 15000 });
  await reports(page).getByLabel('From date', { exact: true }).fill(from);
  await reports(page).getByLabel('To date', { exact: true }).fill(to);
  await expect(reports(page).getByRole('table').getByRole('caption')).toContainText(`${from} to ${to}`);
}
async function total(page: Page, hours: string) {
  await expect(reports(page).getByText(`Total recorded work: ${hours} hours`, { exact: true })).toBeVisible();
}
async function view(page: Page, value: string) {
  await reports(page).getByRole('combobox', { name: 'Report view', exact: true }).selectOption(value);
  await expect(reports(page).getByRole('table')).toBeVisible();
}
// Parse actual downloaded CSV, including quoted commas, quotes, and newlines.
function parseCSV(text: string): string[][] {
  const rows: string[][] = []; let row: string[] = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') {
      if (quoted && text[i + 1] === '"') { field += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && (char === ',' || char === '\n')) {
      row.push(field); field = '';
      if (char === '\n') { rows.push(row); row = []; }
    } else if (char !== '\r' || quoted) field += char;
  }
  if (field || row.length) rows.push([...row, field]);
  return rows;
}
async function download(page: Page) {
  const pending = page.waitForEvent('download');
  await reports(page).getByRole('button', { name: 'Download CSV', exact: true }).click();
  const file = await pending;
  expect(file.suggestedFilename()).toBe(`task-records-${from}-to-${to}.csv`);
  return parseCSV(await readFile((await file.path())!, 'utf8'));
}

test('reports reconcile projects, people, and hierarchy with recorded work and subtree filters', async ({ page, browser }, info) => {
  const f = await setup(browser, 'views');
  try {
    await login(page, f.person.email); await total(page, '3.50');
    await expect(reports(page).getByRole('row').filter({ hasText: f.project.name })).toContainText('3.50');
    await view(page, 'people-days');
    await expect(reports(page).getByRole('row').filter({ hasText: from })).toContainText('3.50');
    await expect(reports(page).getByRole('row').filter({ hasText: to })).toContainText('0.00');
    await view(page, 'tasks');
    const root = reports(page).getByRole('row').filter({ hasText: 'Задача' });
    await expect(root.getByRole('cell')).toHaveText([f.project.name, '1.00', '2.50', '3.50']);
    await page.screenshot({ path: info.outputPath('reports-desktop.png'), fullPage: true });
    await reports(page).getByRole('combobox', { name: 'Task and descendants', exact: true }).selectOption(f.child.id);
    await total(page, '2.50');
    await expect(reports(page).getByRole('row')).toHaveCount(3);
    await expect(reports(page).getByRole('table')).not.toContainText(rootTitle);
    await reports(page).getByRole('combobox', { name: 'Task and descendants', exact: true }).focus();
    await page.keyboard.press('Tab');
    await expect(reports(page).getByRole('button', { name: 'Refresh reports', exact: true })).toBeFocused();
    await page.keyboard.press('Enter'); await total(page, '2.50');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: info.outputPath('reports-narrow.png'), fullPage: true });
    await expect(reports(page).getByRole('button', { name: 'Download CSV', exact: true })).toBeVisible();
    // A reload restores the default period; selecting the known period reconciles again.
    await page.reload();
    await page.getByRole('button', { name: 'Reports', exact: true }).click();
    await expect(reports(page).getByRole('table')).toBeVisible({ timeout: 15000 });
    await reports(page).getByLabel('From date', { exact: true }).fill(from);
    await reports(page).getByLabel('To date', { exact: true }).fill(to);
    await total(page, '3.50');
  } finally { await f.close(); }
});

test('actual CSV downloads preserve quoted Unicode records and ignore report filters', async ({ page, browser }) => {
  const f = await setup(browser, 'csv', true);
  try {
    await login(page, f.person.email); await total(page, '6.50');
    await reports(page).getByRole('combobox', { name: 'Report project', exact: true }).selectOption(f.project.id);
    await reports(page).getByRole('combobox', { name: 'Report person', exact: true }).selectOption(f.person.id);
    await reports(page).getByRole('combobox', { name: 'Task and descendants', exact: true }).selectOption(f.child.id);
    await total(page, '2.50');
    const rows = await download(page);
    expect(rows[0]).toEqual(['Person', 'Project', 'Task', 'Date', 'Start Time', 'End Time', 'Duration']);
    expect(rows).toHaveLength(7);
    expect(rows.some(r => r[0] === 'Алиса, "A"' && r[2] === rootTitle && r[6] === '1.00')).toBeTruthy();
    expect(rows.some(r => r[0] === f.colleague.display_name && r[1] === f.other.name && r[6] === '2.00')).toBeTruthy();
    expect(rows.at(-1)!.slice(3)).toEqual([to, '09:00:00', '', '0.00']);
    expect(rows.some(r => r.includes('Break') || r.includes('End of Working Day'))).toBeFalsy();
    await f.write(`users/${f.person.id}/`, { read_others_timesheets: false }, 'PATCH');
    const own = await download(page); // Backend rechecks even without Refresh access.
    expect(own).toHaveLength(5);
    expect(own.slice(1).every(r => r[0] === 'Алиса, "A"')).toBeTruthy();
  } finally { await f.close(); }
});

test('reports separate whole sheets from readable projects and refresh revoked access safely', async ({ page, browser }) => {
  const f = await setup(browser, 'access', true);
  try {
    await f.write(`users/${f.person.id}/grants/projects/${f.other.id}/`, { task_write: true }, 'PUT');
    await login(page, f.person.email); await total(page, '4.50');
    await expect(reports(page).getByRole('combobox', { name: 'Report project', exact: true }).getByRole('option', { name: f.other.name, exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Tasks', exact: true }).click();
    const sheet = page.getByRole('region', { name: 'Timesheet', exact: true });
    await sheet.getByRole('combobox', { name: 'Timesheet person', exact: true }).selectOption(f.colleague.id);
    await sheet.getByLabel('Day', { exact: true }).fill(from);
    await expect(sheet.getByRole('table').getByRole('caption')).toContainText('3 h');
    await page.getByRole('button', { name: 'Reports', exact: true }).click();
    await expect(reports(page).getByRole('table')).toBeVisible();
    await reports(page).getByLabel('From date', { exact: true }).fill(from);
    await reports(page).getByLabel('To date', { exact: true }).fill(to);
    await total(page, '4.50');
    await reports(page).getByRole('combobox', { name: 'Report project', exact: true }).selectOption(f.project.id);
    await total(page, '4.50');
    await f.write(`users/${f.person.id}/grants/projects/${f.project.id}/`, { task_write: true }, 'PUT');
    await reports(page).getByRole('button', { name: 'Refresh reports', exact: true }).click();
    await expect(reports(page).getByRole('alert')).toContainText('no longer available');
    await expect(reports(page).getByRole('table')).toHaveCount(0);
    await reports(page).getByRole('combobox', { name: 'Report project', exact: true }).selectOption('');
    await total(page, '0.00');
    await expect(reports(page)).toContainText('No recorded work matches this selection.');
    expect(await download(page)).toHaveLength(1);
    // Administrators have no report bypass either.
    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await login(page, 'admin@example.test', 'synthetic-test-only-password'); await total(page, '0.00');
    expect(await download(page)).toHaveLength(1);
  } finally { await f.close(); }
});

test('report requests recover from failures and discard stale responses after filter changes', async ({ page, browser }) => {
  const f = await setup(browser, 'failures');
  try {
    await login(page, f.person.email); await total(page, '3.50');
    await page.route('**/api/v1/reports/projects/**', route => route.fulfill({ status: 503,
      contentType: 'application/json', body: JSON.stringify({ message: 'Temporary report failure.' }) }), { times: 1 });
    await reports(page).getByRole('button', { name: 'Refresh reports', exact: true }).click();
    await expect(reports(page).getByRole('alert')).toContainText('Temporary report failure.');
    await expect(reports(page).getByRole('table')).toHaveCount(0);
    await reports(page).getByRole('button', { name: 'Refresh reports', exact: true }).click(); await total(page, '3.50');
    await page.route('**/api/v1/reports/records.csv?**', route => route.fulfill({ status: 503,
      contentType: 'application/json', body: JSON.stringify({ message: 'Temporary CSV failure.' }) }), { times: 1 });
    await reports(page).getByRole('button', { name: 'Download CSV', exact: true }).click();
    await expect(reports(page).getByRole('alert')).toContainText('Temporary CSV failure.');
    expect(await download(page)).toHaveLength(5);
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    let arrived!: () => void;
    const waiting = new Promise<void>(resolve => { arrived = resolve; });
    await page.route('**/api/v1/reports/projects/**', async route => {
      const response = await route.fetch(); arrived(); await gate; await route.fulfill({ response });
    }, { times: 1 });
    await reports(page).getByRole('button', { name: 'Refresh reports', exact: true }).click();
    await waiting;
    await reports(page).getByRole('combobox', { name: 'Report project', exact: true }).selectOption(f.other.id);
    await total(page, '0.00');
    const staleResponse = page.waitForResponse(response => response.url().includes('/reports/projects/') && !response.url().includes('project='));
    release();
    await (await staleResponse).finished();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect(reports(page).getByText('Total recorded work: 3.50 hours', { exact: true })).toHaveCount(0);
    await reports(page).getByLabel('From date').fill('2020-10-11');
    await expect(reports(page).getByRole('alert')).toContainText('Supply an inclusive');
    await expect(reports(page).getByRole('table')).toHaveCount(0);
    await reports(page).getByLabel('From date').fill(from); await total(page, '0.00');
  } finally { await f.close(); }
});

test('historical day corrections and project moves refresh reports and CSV through the workspace', async ({ page, browser }) => {
  const f = await setup(browser, 'correction');
  try {
    await login(page, f.person.email); await total(page, '3.50');
    await page.getByRole('button', { name: 'Tasks', exact: true }).click();
    const sheet = page.getByRole('region', { name: 'Timesheet', exact: true });
    await sheet.getByLabel('Day', { exact: true }).fill(from);
    await expect(sheet.getByRole('table').getByRole('caption')).toContainText(from);
    await sheet.getByRole('button', { name: 'Edit day…', exact: true }).click();
    const editor = page.getByRole('dialog', { name: 'Edit day', exact: true });
    // Reattribute the leaf half hour through Edit day, preserving the timeline.
    await editor.getByRole('row').filter({ hasText: 'Report leaf' }).getByRole('button', { name: 'Choose task for row 3', exact: true }).click();
    const picker = page.getByRole('dialog', { name: 'Choose draft task', exact: true });
    await picker.getByRole('combobox', { name: 'Draft picker task', exact: true }).selectOption(f.root.id);
    await picker.getByRole('button', { name: 'Done choosing task', exact: true }).click();
    await editor.getByRole('button', { name: 'Save changes', exact: true }).click();
    await expect(editor).not.toBeVisible();
    await page.getByRole('button', { name: 'Reports', exact: true }).click();
    await expect(reports(page).getByRole('table')).toBeVisible();
    await reports(page).getByLabel('From date').fill(from); await reports(page).getByLabel('To date').fill(to);
    await view(page, 'tasks');
    await expect(reports(page).getByRole('row').filter({ hasText: 'Задача' }).getByRole('cell')).toHaveText([f.project.name, '1.50', '2.00', '3.50']);
    const current = await (await page.request.get(`${baseURL}/api/v1/tasks/${f.root.id}/`)).json();
    const move = { parent: null, project: f.other.id, expected_revision: current.revision };
    const preview = await f.actorWrite(`tasks/${f.root.id}/move/preview/`, move);
    await f.actorWrite(`tasks/${f.root.id}/move/`, { ...move, confirm: true, expected_domain_revision: preview.domain_revision });
    await reports(page).getByRole('button', { name: 'Refresh reports', exact: true }).click();
    await total(page, '3.50'); await view(page, 'projects');
    await expect(reports(page).getByRole('row').filter({ hasText: f.other.name })).toContainText('3.50');
    await expect(reports(page).getByRole('row').filter({ hasText: f.project.name })).toContainText('0.00');
    const csv = await download(page);
    expect(csv.slice(1).every(r => r[1] === f.other.name)).toBeTruthy();
    expect(csv.filter(r => r[2] === rootTitle)).toHaveLength(3);
  } finally { await f.close(); }
});
