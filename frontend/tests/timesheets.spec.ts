import { expect, test, type APIRequestContext, type Browser, type Page, type Locator } from '@playwright/test';

const baseURL = process.env.BASE_URL ?? 'http://frontend:5173';
const password = 'browser-timesheet-long-password';
const friday = '2020-10-09';
async function authenticate(request: APIRequestContext, email: string, secret = password) {
  const csrf = await (await request.get(`${baseURL}/api/v1/auth/csrf/`)).json();
  const response = await request.post(`${baseURL}/api/v1/auth/login/`, { headers: { 'X-CSRFToken': csrf.csrf_token, Origin: baseURL }, data: { email, password: secret } });
  expect(response.status()).toBe(200);
  return (await response.json()).csrf_token as string;
}
async function login(page: Page, email: string) {
  await page.goto('/');
  const form = page.getByRole('form', { name: 'Sign in', exact: true });
  await form.getByLabel('Email', { exact: true }).fill(email);
  await form.getByLabel('Password', { exact: true }).fill(password);
  await form.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(sheet(page).getByRole('button', { name: 'Edit day…', exact: true })).toBeVisible({ timeout: 15000 });
}
const sheet = (page: Page) => page.getByRole('region', { name: 'Timesheet', exact: true });
const editor = (page: Page) => page.getByRole('dialog', { name: 'Edit day', exact: true });
async function setup(browser: Browser, key: string) {
  key = `${key}-${Date.now()}`;
  const admin = await browser.newContext();
  const token = await authenticate(admin.request, 'admin@example.test', 'synthetic-test-only-password');
  async function write(path: string, data: unknown, method = 'POST') {
    const response = await admin.request.fetch(`${baseURL}/api/v1/${path}`, { method, headers: { 'X-CSRFToken': token, Origin: baseURL }, data });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.status() === 204 ? null : response.json();
  }
  const person = await write('users/', { email: `time-${key}@example.test`, display_name: `Time user ${key}`, password });
  const colleague = await write('users/', { email: `time-colleague-${key}@example.test`, display_name: `Time colleague ${key}`, password });
  const org = await write('organizations/', { name: `Time org ${key}` });
  const project = await write('projects/', { name: `Time project ${key}`, organization: org.id });
  const other = await write('projects/', { name: `Other time project ${key}`, organization: org.id });
  for (const p of [project, other]) await write(`users/${person.id}/grants/projects/${p.id}/`, { task_read: true, task_write: true }, 'PUT');
  const actor = await browser.newContext();
  const actorToken = await authenticate(actor.request, person.email);
  async function actorWrite(path: string, data: unknown) {
    const response = await actor.request.post(`${baseURL}/api/v1/${path}`, { headers: { 'X-CSRFToken': actorToken, Origin: baseURL }, data });
    expect(response.ok(), await response.text()).toBeTruthy(); return response.json();
  }
  const statuses = (await (await actor.request.get(`${baseURL}/api/v1/statuses/`)).json()).results;
  async function task(title: string, p = project, status = 'In Progress') {
    const data = { title, description: `Protected description of ${title}`, project: p.id, status: statuses.find((s: { name: string }) => s.name === status).id, parent: null };
    const preview = await actorWrite('tasks/preview/', data);
    return actorWrite('tasks/', { ...data, confirm: true, expected_domain_revision: preview.domain_revision });
  }
  const meeting = await task('Time meeting');
  const email = await task('Time email', other);
  const final = await task('Historical completed work', project, 'Completed');
  async function day(date: string, owner = person.id) { return (await actor.request.get(`${baseURL}/api/v1/timesheets/${owner}/days/${date}/`)).json(); }
  const context = await (await actor.request.get(`${baseURL}/api/v1/timesheets/${person.id}/context/`)).json();
  async function command(date: string, kind: string, extra: Record<string, unknown>) {
    const revision = (await day(date)).revision;
    return actorWrite(`timesheets/${person.id}/commands/`, { command: kind, date, expected_revision: revision, ...extra });
  }
  async function start(date: string, time = '09:00:00', id = meeting.id) {
    await command(date, 'start', { at: `${date}T${time}Z`, task: id });
    return (await day(date)).sessions.at(-1).id as string;
  }
  async function closed(date = friday) {
    const session = await start(date);
    await command(date, 'end_day', { session, at: `${date}T12:00:00Z` });
    return session;
  }
  return { admin, actor, person, colleague, project, other, meeting, email, final, today: context.today as string, write, day, command, start, closed, close: async () => { await actor.close(); await admin.close(); } };
}
async function selectDay(page: Page, date: string) {
  await sheet(page).getByLabel('Day', { exact: true }).fill(date);
  await expect(sheet(page).getByRole('table').getByRole('caption')).toContainText(date);
}
async function manualTime(page: Page, value: string) {
  const now = sheet(page).getByRole('checkbox', { name: 'Use current time', exact: true });
  if (await now.count()) await now.uncheck();
  await sheet(page).getByLabel('Selected-day time', { exact: true }).fill(value);
}
async function tabOut(page: Page, input: Locator) {
  const element = await input.elementHandle();
  for (let i = 0; i < 12 && await element!.evaluate(node => node === document.activeElement); i++) await page.keyboard.press('Tab');
}
async function saved(page: Page) { await expect(sheet(page).getByRole('alert')).toHaveText('Timesheet saved.'); }
async function confirm(page: Page) {
  const dialog = page.getByRole('dialog', { name: 'Confirm timesheet change', exact: true });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: 'Confirm timesheet change', exact: true }).click();
  await expect(dialog).not.toBeVisible(); await saved(page);
}

test('current work supports task actions, drag and drop, breaks, closing, and reload persistence', async ({ page, browser }, info) => {
  const f = await setup(browser, 'record');
  try {
    await page.clock.install({ time: new Date(`${f.today}T10:00:00Z`) });
    await login(page, f.person.email);
    await page.getByRole('button', { name: 'Record Time meeting', exact: true }).click();
    await expect(sheet(page).getByRole('combobox', { name: 'Recording picker task', exact: true })).toHaveValue(f.meeting.id);
    await manualTime(page, `${f.today}T09:00`);
    await sheet(page).getByRole('button', { name: 'Record task', exact: true }).click(); await saved(page);
    await page.getByRole('list', { name: 'Task list', exact: true }).getByRole('button', { name: 'Time email', exact: true }).dragTo(sheet(page)); await saved(page);
    await manualTime(page, `${f.today}T11:00`); await sheet(page).getByRole('button', { name: 'Break', exact: true }).click(); await saved(page);
    await manualTime(page, `${f.today}T12:00`); await sheet(page).getByRole('button', { name: 'End of Working Day', exact: true }).click(); await saved(page);
    const stored = await f.day(f.today);
    expect(stored.sessions[0].rows.map((r: { kind: string }) => r.kind)).toEqual(['task', 'task', 'break']);
    expect(stored.work_seconds).toBe(7200);
    await page.reload(); await expect(sheet(page)).toContainText('2 h', { timeout: 15000 }); await expect(sheet(page).getByRole('table')).toContainText('closed');
    await page.screenshot({ path: info.outputPath('timesheet-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({ path: info.outputPath('timesheet-narrow.png'), fullPage: true });
  } finally { await f.close(); }
});

test('historical Friday additions and final tasks preserve today recording and partial totals', async ({ page, browser }) => {
  const f = await setup(browser, 'friday');
  try {
    const session = await f.start(friday);
    await f.command(friday, 'break', { session, at: `${friday}T12:00:00Z` });
    await f.command(friday, 'append', { session, at: `${friday}T12:43:00Z`, task: f.email.id });
    await f.start(f.today);
    const current = (await f.day(f.today)).sessions;
    await login(page, f.person.email); await selectDay(page, friday);
    await expect(sheet(page).getByRole('status')).toContainText('Unfinished');
    await expect(sheet(page)).toContainText('3 h');
    await sheet(page).getByRole('searchbox', { name: 'Recording picker search', exact: true }).fill('Historical');
    await sheet(page).getByRole('combobox', { name: 'Recording picker project', exact: true }).selectOption(f.project.id);
    await sheet(page).getByRole('checkbox', { name: 'Completed', exact: true }).check();
    await sheet(page).getByRole('combobox', { name: 'Recording picker task', exact: true }).selectOption(f.final.id);
    await manualTime(page, `${friday}T14:00`); await sheet(page).getByRole('button', { name: 'Record task', exact: true }).click(); await saved(page);
    await manualTime(page, `${friday}T17:00`); await sheet(page).getByRole('button', { name: 'End of Working Day', exact: true }).click(); await saved(page);
    expect((await f.day(friday)).work_seconds).toBe(7 * 3600 + 17 * 60);
    expect((await f.day(f.today)).sessions).toEqual(current);
    const final = await (await f.actor.request.get(`${baseURL}/api/v1/tasks/${f.final.id}/`)).json();
    expect(final.status).toBe(f.final.status);
  } finally { await f.close(); }
});

test('Edit day preserves invalid and failed drafts, supports cancel, sorting, focus, and atomic insertion', async ({ page, browser }, info) => {
  const f = await setup(browser, 'draft');
  try {
    await f.closed(); const original = await f.day(friday);
    await login(page, f.person.email); await selectDay(page, friday);
    await sheet(page).getByRole('button', { name: 'Edit day…', exact: true }).click();
    await editor(page).getByLabel('Row 1 start', { exact: true }).fill(`${friday}T08:00`);
    page.once('dialog', dialog => dialog.dismiss()); await editor(page).getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(editor(page)).toBeVisible();
    page.once('dialog', dialog => dialog.accept()); await page.keyboard.press('Escape'); await expect(editor(page)).not.toBeVisible();
    expect(await f.day(friday)).toEqual(original);
    await sheet(page).getByRole('button', { name: 'Edit day…', exact: true }).click();
    await editor(page).getByLabel('Row 1 end', { exact: true }).fill(`${friday}T10:00`);
    await editor(page).getByRole('button', { name: 'Add row to session 1', exact: true }).click();
    const firstAdded = editor(page).getByLabel('Row 2 start', { exact: true });
    await firstAdded.fill(`${friday}T08:00`); await tabOut(page, firstAdded);
    await expect(editor(page).getByLabel('Row 1 end', { exact: true })).toBeFocused();
    await editor(page).getByLabel('Row 1 start', { exact: true }).fill(`${friday}T10:15`);
    await tabOut(page, editor(page).getByLabel('Row 1 start', { exact: true }));
    await editor(page).getByLabel('Row 2 end', { exact: true }).fill(`${friday}T11:00`);
    await editor(page).getByRole('button', { name: 'Add row to session 1', exact: true }).click();
    await editor(page).getByRole('combobox', { name: 'Row 3 type', exact: true }).selectOption('task');
    await editor(page).getByRole('button', { name: 'Choose task for row 3', exact: true }).click();
    const picker = page.getByRole('dialog', { name: 'Choose draft task', exact: true });
    await picker.getByRole('searchbox', { name: 'Draft picker search', exact: true }).fill('Historical');
    await picker.getByRole('checkbox', { name: 'Completed', exact: true }).check();
    await picker.getByRole('combobox', { name: 'Draft picker task', exact: true }).selectOption(f.final.id);
    await picker.getByRole('button', { name: 'Done choosing task', exact: true }).click();
    await editor(page).getByLabel('Row 3 start', { exact: true }).fill(`${friday}T11:00`);
    await editor(page).getByLabel('Row 3 end', { exact: true }).fill(`${friday}T12:00`);
    await expect(editor(page)).toContainText('Gap before the next row');
    await editor(page).getByRole('button', { name: 'Save changes', exact: true }).click();
    await expect(editor(page).getByRole('alert')).toContainText('Rows must join exactly');
    expect(await f.day(friday)).toEqual(original);
    await editor(page).getByLabel('Row 2 start', { exact: true }).fill(`${friday}T10:00`);
    await page.route('**/api/v1/timesheets/*/commands/', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ code: 'unavailable', message: 'Temporary save failure.' }) }));
    await editor(page).getByRole('button', { name: 'Save changes', exact: true }).click();
    await expect(editor(page).getByRole('alert')).toContainText('Temporary save failure');
    await expect(editor(page).getByLabel('Row 2 start', { exact: true })).toHaveValue(`${friday}T10:00`);
    await page.screenshot({ path: info.outputPath('edit-day-draft.png'), fullPage: true });
    await page.unroute('**/api/v1/timesheets/*/commands/');
    await editor(page).getByRole('button', { name: 'Save changes', exact: true }).dblclick();
    await expect(editor(page)).not.toBeVisible();
    const result = await f.day(friday); expect(result.work_seconds).toBe(7200); expect(result.sessions[0].rows[0].id).toBe(original.sessions[0].rows[0].id); expect(result.revision).toBe(original.revision + 1);
  } finally { await f.close(); }
});

test('competing tabs preserve stale drafts and require explicit reload and review', async ({ page, browser }) => {
  const f = await setup(browser, 'stale'); const second = await browser.newContext();
  try {
    await f.closed(); await f.start(f.today);
    await login(page, f.person.email); await selectDay(page, friday);
    await sheet(page).getByRole('button', { name: 'Edit day…', exact: true }).click();
    await editor(page).getByLabel('Row 1 start', { exact: true }).fill(`${friday}T08:00`);
    const other = await second.newPage(); await login(other, f.person.email);
    await sheet(other).getByRole('checkbox', { name: 'Use current time', exact: true }).uncheck();
    await manualTime(other, `${f.today}T10:00`);
    await sheet(other).getByRole('combobox', { name: 'Recording picker task', exact: true }).selectOption(f.email.id);
    await sheet(other).getByRole('button', { name: 'Record task', exact: true }).click(); await saved(other);
    const current = (await f.day(f.today)).sessions;
    await editor(page).getByRole('button', { name: 'Save changes', exact: true }).click();
    await expect(editor(page).getByRole('alert')).toContainText('timesheet changed');
    await expect(editor(page).getByLabel('Row 1 start', { exact: true })).toHaveValue(`${friday}T08:00`);
    await expect(editor(page).getByRole('button', { name: 'Save changes', exact: true })).toBeDisabled();
    expect((await f.day(friday)).work_seconds).toBe(10800); expect((await f.day(f.today)).sessions).toEqual(current);
    page.once('dialog', dialog => dialog.accept()); await editor(page).getByRole('button', { name: 'Reload day and discard draft', exact: true }).click();
    await expect(editor(page).getByLabel('Row 1 start', { exact: true })).toHaveValue(`${friday}T09:00`);
    await expect(editor(page).getByRole('button', { name: 'Save changes', exact: true })).toBeEnabled();
    await editor(page).getByRole('button', { name: 'Cancel', exact: true }).click();
  } finally { await second.close(); await f.close(); }
});

test('ordinary boundaries, last deletion, resumption advice and stale previews require review', async ({ page, browser }) => {
  const f = await setup(browser, 'ordinary');
  try {
    const session = await f.start(friday);
    await f.command(friday, 'append', { session, at: `${friday}T10:00:00Z`, task: f.email.id });
    await f.command(friday, 'end_day', { session, at: `${friday}T12:00:00Z` });
    await login(page, f.person.email); await selectDay(page, friday);
    await sheet(page).getByRole('button', { name: `Edit end of Time meeting at ${friday} 10:00:00`, exact: true }).click();
    const boundary = page.getByRole('dialog', { name: 'Edit time boundary', exact: true });
    await boundary.getByLabel('Boundary time', { exact: true }).fill(`${friday}T10:30`);
    await boundary.getByRole('button', { name: 'Preview boundary change', exact: true }).click();
    await f.write('organizations/', { name: `Invalidate timesheet preview ${Date.now()}` });
    await page.getByRole('dialog', { name: 'Confirm timesheet change', exact: true }).getByRole('button', { name: 'Confirm timesheet change', exact: true }).click();
    await expect(sheet(page).getByRole('alert')).toContainText('Preview the changes again');
    expect((await f.day(friday)).sessions[0].rows[0].ended_at).toContain('10:00:00');
    await sheet(page).getByRole('button', { name: 'Reload timesheet', exact: true }).click();
    await sheet(page).getByRole('button', { name: `Edit end of Time meeting at ${friday} 10:00:00`, exact: true }).click();
    await boundary.getByLabel('Boundary time', { exact: true }).fill(`${friday}T10:30`);
    await boundary.getByRole('button', { name: 'Preview boundary change', exact: true }).click(); await confirm(page);
    const rows = (await f.day(friday)).sessions[0].rows; expect(rows[0].ended_at).toBe(rows[1].started_at);
    await sheet(page).getByRole('button', { name: 'Delete last record', exact: true }).click(); await confirm(page);
    expect((await f.day(friday)).sessions[0].rows).toHaveLength(1);
    await sheet(page).getByRole('combobox', { name: 'Recording picker task', exact: true }).selectOption(f.email.id);
    await manualTime(page, `${friday}T13:00`); await sheet(page).getByRole('button', { name: 'Record task', exact: true }).click();
    await expect(page.getByRole('dialog', { name: 'Confirm timesheet change', exact: true })).toContainText('Convert the closing marker to a break'); await confirm(page);
    const resumed = await f.day(friday); expect(resumed.work_seconds).toBe(10800); expect(resumed.sessions[0].rows[1].kind).toBe('break'); expect(resumed.sessions[0].rows[2].ended_at).toBeNull();
  } finally { await f.close(); }
});

test('whole colleague sheets preserve restricted references and recheck write permission at save', async ({ page, browser }) => {
  const f = await setup(browser, 'colleague');
  try {
    const session = await f.start(friday);
    await f.command(friday, 'append', { session, at: `${friday}T10:00:00Z`, task: f.email.id });
    await f.command(friday, 'end_day', { session, at: `${friday}T12:00:00Z` });
    await f.write(`users/${f.colleague.id}/`, { read_others_timesheets: true }, 'PATCH');
    await login(page, f.colleague.email);
    await sheet(page).getByRole('combobox', { name: 'Timesheet person', exact: true }).selectOption(f.person.id);
    await selectDay(page, friday);
    await expect(sheet(page).getByRole('table')).toContainText('Time meeting');
    await expect(sheet(page).getByRole('table')).toContainText('Time email');
    await expect(sheet(page).getByRole('table')).toContainText('details restricted');
    await expect(sheet(page).getByRole('button', { name: 'Time meeting', exact: true })).not.toBeVisible();
    await expect(sheet(page).getByRole('button', { name: 'Edit day…', exact: true })).not.toBeVisible();
    await f.write(`users/${f.colleague.id}/`, { write_others_timesheets: true }, 'PATCH');
    await page.getByRole('button', { name: 'Refresh access', exact: true }).click();
    await sheet(page).getByRole('button', { name: 'Edit day…', exact: true }).click();
    await editor(page).getByLabel('Row 1 start', { exact: true }).fill(`${friday}T08:00`);
    await editor(page).getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(editor(page)).not.toBeVisible();
    expect((await f.day(friday)).work_seconds).toBe(14400);
    await sheet(page).getByRole('button', { name: 'Edit day…', exact: true }).click();
    await editor(page).getByLabel('Row 1 start', { exact: true }).fill(`${friday}T07:00`);
    await f.write(`users/${f.colleague.id}/`, { write_others_timesheets: false }, 'PATCH');
    await editor(page).getByRole('button', { name: 'Save changes', exact: true }).click();
    await expect(editor(page).getByRole('alert')).toContainText('Timesheet access is required');
    await expect(editor(page).getByLabel('Row 1 start', { exact: true })).toHaveValue(`${friday}T07:00`);
    expect((await f.day(friday)).work_seconds).toBe(14400);
    page.once('dialog', dialog => dialog.accept()); await editor(page).getByRole('button', { name: 'Cancel', exact: true }).click();
    await f.write(`users/${f.colleague.id}/`, { read_others_timesheets: false, write_others_timesheets: true }, 'PATCH');
    await page.getByRole('button', { name: 'Refresh access', exact: true }).click();
    await expect(sheet(page)).toContainText('Reading this timesheet requires Read Others');
    await expect(sheet(page).getByRole('table')).not.toBeVisible();
  } finally { await f.close(); }
});

test('explicit overnight continuation splits work and fixes midnight connections in Edit day', async ({ page, browser }) => {
  const f = await setup(browser, 'overnight');
  try {
    const previous = new Date(Date.parse(`${f.today}T00:00:00Z`) - 86400000).toISOString().slice(0, 10);
    const session = await f.start(previous, '23:00:00');
    await login(page, f.person.email);
    await sheet(page).getByRole('combobox', { name: 'Recording picker task', exact: true }).selectOption(f.email.id);
    await sheet(page).getByRole('combobox', { name: 'Previous session', exact: true }).selectOption(session);
    await manualTime(page, `${f.today}T01:00`);
    await sheet(page).getByRole('button', { name: 'Continue previous session', exact: true }).click(); await saved(page);
    expect((await f.day(previous)).work_seconds).toBe(3600);
    expect((await f.day(f.today)).work_seconds).toBe(3600);
    await manualTime(page, `${f.today}T02:00`); await sheet(page).getByRole('button', { name: 'End of Working Day', exact: true }).click(); await saved(page);
    expect((await f.day(f.today)).work_seconds).toBe(7200);
    await sheet(page).getByRole('button', { name: 'Edit day…', exact: true }).click();
    await expect(editor(page).getByLabel('Row 1 start', { exact: true })).toBeDisabled();
    await editor(page).getByRole('button', { name: 'Cancel', exact: true }).click();
    await selectDay(page, previous);
    await sheet(page).getByRole('button', { name: 'Edit day…', exact: true }).click();
    await expect(editor(page).getByLabel('Row 1 end', { exact: true })).toBeDisabled();
    await expect(editor(page).getByRole('button', { name: 'Remove session 1', exact: true })).not.toBeVisible();
    await editor(page).getByRole('combobox', { name: 'Row 1 type', exact: true }).selectOption('break');
    await editor(page).getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(editor(page)).not.toBeVisible();
    expect((await f.day(previous)).work_seconds).toBe(0); expect((await f.day(f.today)).work_seconds).toBe(7200);
  } finally { await f.close(); }
});

test('historical task drops ask for selected-day time and current final tasks require separate reopening', async ({ page, browser }) => {
  const f = await setup(browser, 'drop-past');
  try {
    await login(page, f.person.email);
    await sheet(page).getByRole('combobox', { name: 'Recording picker task', exact: true }).selectOption(f.final.id);
    await sheet(page).getByRole('button', { name: 'Record task', exact: true }).click();
    await expect(sheet(page).getByRole('alert')).toContainText('Reopen the task separately');
    expect((await f.day(f.today)).sessions).toHaveLength(0);
    await selectDay(page, friday);
    await page.getByRole('list', { name: 'Task list', exact: true }).getByRole('button', { name: 'Time meeting', exact: true }).dragTo(sheet(page));
    await expect(sheet(page).getByRole('alert')).toContainText('Enter a start time on the selected day');
    expect((await f.day(friday)).sessions).toHaveLength(0);
    await manualTime(page, `${friday}T09:30`); await sheet(page).getByRole('button', { name: 'Record task', exact: true }).click(); await saved(page);
    await expect(sheet(page).getByRole('table')).toContainText(`${friday} 09:30`);
    await sheet(page).getByRole('table').getByRole('button', { name: 'Time meeting', exact: true }).click();
    await expect(page.getByRole('dialog', { name: 'Task description', exact: true })).toContainText('Protected description of Time meeting');
  } finally { await f.close(); }
});

test('running day drafts retain unknown ends and precision while independent historical days can be cleared', async ({ page, browser }) => {
  const f = await setup(browser, 'active-editor');
  try {
    await f.closed();
    const session = await f.start(f.today, '09:00:00.000123');
    await f.command(f.today, 'append', { session, at: `${f.today}T10:00:00.000456Z`, task: f.email.id });
    await login(page, f.person.email);
    await sheet(page).getByRole('button', { name: 'Edit day…', exact: true }).click();
    await editor(page).getByRole('button', { name: 'Save changes', exact: true }).click();
    await expect(editor(page)).not.toBeVisible();
    const unchanged = (await f.day(f.today)).sessions[0];
    expect(unchanged.rows[0].started_at).toContain('09:00:00.000123');
    expect(unchanged.rows[1].started_at).toContain('10:00:00.000456');
    expect(unchanged.rows[1].ended_at).toBeNull(); expect(unchanged.state).toBe('active');
    await sheet(page).getByRole('button', { name: 'Edit day…', exact: true }).click();
    await editor(page).getByRole('button', { name: 'Remove row 1', exact: true }).click();
    await editor(page).getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(editor(page)).not.toBeVisible();
    const running = (await f.day(f.today)).sessions;
    expect(running[0].rows).toHaveLength(1); expect(running[0].rows[0].ended_at).toBeNull(); expect(running[0].state).toBe('active');
    await selectDay(page, friday); await sheet(page).getByRole('button', { name: 'Edit day…', exact: true }).click();
    await editor(page).getByRole('button', { name: 'Remove session 1', exact: true }).click();
    await editor(page).getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(editor(page)).not.toBeVisible();
    expect((await f.day(friday)).sessions).toHaveLength(0); expect((await f.day(f.today)).sessions).toEqual(running);
    const converted = await page.evaluate(async () => {
      const modulePath = '/src/timesheet.ts';
      const { instant, localStamp } = await import(modulePath);
      return { absolute: instant('2026-10-09T23:00', 'Europe/Berlin'), local: localStamp('2026-10-09T22:30:00Z', 'Europe/Berlin') };
    });
    expect(converted).toEqual({ absolute: '2026-10-09T21:00:00.000Z', local: '2026-10-10T00:30:00' });
  } finally { await f.close(); }
});
