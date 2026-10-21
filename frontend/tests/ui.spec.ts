import { expect, test } from '@playwright/test';
import { baseURL, login, setup } from './helpers/content';

test('focused workspace protects task drafts, preselects subtask context and restores focus', async ({ page, browser }, info) => {
  const f = await setup(browser, 'ui-windows');
  try {
    await login(page, f.alice.email);
    const list = page.getByRole('list', { name: 'Task list', exact: true });
    await expect(list).toBeVisible();
    await expect(page.getByRole('form', { name: /Create task|Record work|Edit task/ })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Check connection' })).toHaveCount(0);
    await page.getByRole('combobox', { name: 'Filter project', exact: true }).selectOption(f.project.id);
    const opener = list.getByRole('button', { name: f.task.title, exact: true });
    await opener.click();
    await page.getByRole('button', { name: 'Close details', exact: true }).click();
    await expect(opener).toBeFocused();
    const unchanged = await (await f.content.request.get(`${baseURL}/api/v1/tasks/${f.task.id}/`)).json();
    expect(unchanged.status).toBe(f.task.status);
    await page.getByLabel(`Actions for ${f.task.title}`, { exact: true }).click();
    await page.getByRole('button', { name: 'Add subtask', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Create task', exact: true });
    await expect(dialog.getByRole('combobox', { name: 'Task project', exact: true })).toHaveValue(f.project.id);
    await expect(dialog.getByRole('combobox', { name: 'Parent task', exact: true })).toHaveValue(f.task.id);
    await dialog.getByLabel('Task title', { exact: true }).fill('Unsaved subtask');
    page.once('dialog', prompt => prompt.dismiss());
    await page.keyboard.press('Escape');
    await expect(dialog.getByLabel('Task title', { exact: true })).toHaveValue('Unsaved subtask');
    await expect(page.getByRole('dialog')).toHaveCount(1);
    page.once('dialog', prompt => prompt.accept());
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    await expect(page.getByLabel(`Actions for ${f.task.title}`, { exact: true })).toBeFocused();
    await expect(page.getByRole('combobox', { name: 'Filter project', exact: true })).toHaveValue(f.project.id);
    await page.screenshot({ path: info.outputPath('focused-workspace.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: info.outputPath('focused-workspace-narrow.png'), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  } finally { await f.content.close(); await f.admin.close(); }
});

test('remark composer leads the stream and ordering persists without changing shared stars', async ({ page, browser }) => {
  const f = await setup(browser, 'ui-order');
  try {
    const first = await f.contentWrite(`tasks/${f.task.id}/remarks/`, { body: 'Earlier remark' });
    await f.contentWrite(`remarks/${first.id}/star/`, { starred: true, expected_revision: first.revision });
    await f.contentWrite(`tasks/${f.task.id}/remarks/`, { body: 'Later remark' });
    await login(page, f.alice.email);
    const open = () => page.getByRole('list', { name: 'Task list', exact: true }).getByRole('button', { name: f.task.title, exact: true }).click();
    await open();
    const stream = page.getByRole('list', { name: 'Chronological remarks', exact: true });
    await expect(stream.getByRole('article').first()).toContainText('Later remark');
    const composer = page.getByRole('form', { name: 'Post remark', exact: true });
    expect(await composer.evaluate((node, id) => !!(node.compareDocumentPosition(document.getElementById(id)!) & Node.DOCUMENT_POSITION_FOLLOWING), `remark-${first.id}`)).toBe(true);
    await page.getByRole('region', { name: 'Starred remarks', exact: true }).getByRole('link').click();
    await expect(page.locator(`#remark-${first.id}`)).toBeFocused();
    await page.getByRole('combobox', { name: 'Remark order', exact: true }).selectOption('oldest');
    await expect(stream.getByRole('article').first()).toContainText('Earlier remark');
    await page.reload(); await open();
    await expect(page.getByRole('combobox', { name: 'Remark order', exact: true })).toHaveValue('oldest');
    await expect(stream.getByRole('article').first()).toContainText('Earlier remark');
  } finally { await f.content.close(); await f.admin.close(); }
});

test('a saved task with a failed reload is acknowledged and refreshed without replaying the write', async ({ page, browser }) => {
  const f = await setup(browser, 'ui-saved-reload');
  try {
    await login(page, f.alice.email);
    await page.getByRole('list', { name: 'Task list', exact: true }).getByRole('button', { name: f.task.title, exact: true }).click();
    await page.getByRole('button', { name: 'Edit task', exact: true }).click();
    await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Saved despite reload failure');
    await page.route('**/api/v1/tasks/?*', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ code: 'unavailable', message: 'Synthetic task reload failure.' }) }));
    await page.getByRole('button', { name: 'Save task', exact: true }).click();
    await expect(page.getByRole('dialog').getByRole('alert')).toContainText('Changes saved, but reload failed');
    await expect(page.getByRole('button', { name: 'Save task', exact: true })).toHaveCount(0);
    const saved = await (await f.content.request.get(`${baseURL}/api/v1/tasks/${f.task.id}/`)).json();
    expect(saved.description).toBe('Saved despite reload failure');
    expect(saved.revision).toBe(1);
    await page.unroute('**/api/v1/tasks/?*');
    await page.getByRole('dialog').getByRole('button', { name: 'Refresh tasks', exact: true }).click();
    await expect(page.getByRole('dialog')).toContainText('Saved despite reload failure');
    expect((await (await f.content.request.get(`${baseURL}/api/v1/tasks/${f.task.id}/`)).json()).revision).toBe(1);
  } finally { await f.content.close(); await f.admin.close(); }
});
