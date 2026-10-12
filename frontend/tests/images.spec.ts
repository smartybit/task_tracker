import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { baseURL, flags, login, setup } from './helpers/content';

const screenshot = readFileSync('tests/fixtures/screenshot.png');
const file = { name: 'screenshot.png', mimeType: 'image/png', buffer: screenshot };

test('description images save inline, survive reload, and require current task read', async ({ page, browser }, testInfo) => {
  const f = await setup(browser, 'description-image');
  try {
    await login(page, f.alice.email);
    const list = page.getByRole('list', { name: 'Task list', exact: true });
    const title = 'Illustrated task';
    const create = page.getByRole('form', { name: 'Create task', exact: true });
    await create.getByRole('textbox', { name: 'Task title', exact: true }).fill(title);
    await create.getByRole('combobox', { name: 'Task project', exact: true }).selectOption(f.project.id);
    await create.getByLabel('Add images', { exact: true }).setInputFiles(file);
    await expect(create.getByRole('status')).toContainText('1 new image');
    await create.getByRole('button', { name: 'Preview new task', exact: true }).click();
    await page.getByRole('dialog', { name: 'Confirm task change', exact: true }).getByRole('button', { name: 'Confirm change', exact: true }).click();
    const detail = page.getByRole('dialog', { name: 'Task description', exact: true });
    const image = detail.getByRole('img', { name: 'Attached image', exact: true });
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBe(128);
    const url = await image.getAttribute('src');
    const edit = page.getByRole('form', { name: 'Edit task', exact: true });
    const body = edit.getByRole('textbox', { name: 'Description', exact: true });
    await body.fill(`${await body.inputValue()}\nCaption after an ordinary text edit`);
    await edit.getByRole('button', { name: 'Save task', exact: true }).click();
    await expect(detail).toContainText('Caption after an ordinary text edit');
    await page.reload(); await list.getByRole('button', { name: title, exact: true }).click();
    await expect(image).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath('inline-image-narrow.png'), fullPage: true });
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, { task_write: true }, 'PUT');
    expect((await page.request.get(`${baseURL}${url}`)).status()).toBe(404);
    await detail.getByRole('button', { name: 'Refresh images', exact: true }).click();
    await expect(detail.getByText('Unavailable image', { exact: true })).toBeVisible();
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, flags, 'PUT');
    await detail.getByRole('button', { name: 'Refresh images', exact: true }).click();
    await expect(image).toBeVisible();
    await detail.getByRole('button', { name: 'Preview deletion', exact: true }).click();
    const preview = page.getByRole('dialog', { name: 'Confirm task change', exact: true });
    await expect(preview).toContainText('deletes 1 image(s)');
    await preview.getByRole('button', { name: 'Confirm change', exact: true }).click();
    expect((await page.request.get(`${baseURL}${url}`)).status()).toBe(404);
  } finally { await f.content.close(); await f.admin.close(); }
});

test('clipboard screenshots save in remarks and downloads require remark read', async ({ page, browser }) => {
  const f = await setup(browser, 'pasted-image');
  try {
    await login(page, f.alice.email);
    await page.getByRole('list', { name: 'Task list', exact: true }).getByRole('button', { name: f.task.title, exact: true }).click();
    const composer = page.getByRole('form', { name: 'Post remark', exact: true });
    await composer.getByRole('textbox', { name: 'New remark', exact: true }).evaluate((element, encoded) => {
      const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
      const data = new DataTransfer(); data.items.add(new File([bytes], 'clipboard.png', { type: 'image/png' }));
      element.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
    }, screenshot.toString('base64'));
    await expect(composer.getByRole('status')).toContainText('1 new image');
    await composer.getByRole('button', { name: 'Post remark', exact: true }).click();
    const stream = page.getByRole('list', { name: 'Chronological remarks', exact: true });
    const image = stream.getByRole('img', { name: 'Attached image', exact: true });
    await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBe(128);
    const url = await image.getAttribute('src');
    await expect(composer.getByRole('status')).toHaveCount(0);
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, { task_read: true, remark_write: true }, 'PUT');
    expect((await page.request.get(`${baseURL}${url}`)).status()).toBe(404);
    await page.getByRole('button', { name: 'Reload remarks', exact: true }).click();
    await expect(stream).toHaveCount(0);
  } finally { await f.content.close(); await f.admin.close(); }
});

test('invalid images and failed saves preserve the draft and pending image', async ({ page, browser }) => {
  const f = await setup(browser, 'image-recovery');
  try {
    await login(page, f.alice.email);
    await page.getByRole('list', { name: 'Task list', exact: true }).getByRole('button', { name: f.task.title, exact: true }).click();
    const composer = page.getByRole('form', { name: 'Post remark', exact: true });
    const input = composer.getByRole('textbox', { name: 'New remark', exact: true });
    await input.fill('Image draft ');
    await composer.getByLabel('Add images', { exact: true }).setInputFiles({ ...file, buffer: Buffer.from('Pretend PNG') });
    await expect(composer.getByRole('status')).toContainText('1 new image');
    await composer.getByRole('button', { name: 'Post remark', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Task remarks', exact: true }).getByRole('alert')).toContainText('valid static PNG');
    await expect(input).toHaveValue(/Image draft.*\[image:/);
    await input.fill('Recovered image draft ');
    await composer.getByLabel('Add images', { exact: true }).setInputFiles(file);
    await expect(composer.getByRole('status')).toContainText('1 new image');
    await page.route('**/api/v1/tasks/*/remarks/', route => route.request().method() === 'POST'
      ? route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ code: 'unavailable', message: 'Synthetic image save failure.' }) }) : route.continue());
    await composer.getByRole('button', { name: 'Post remark', exact: true }).click();
    await expect(input).toHaveValue(/Recovered image draft.*\[image:/);
    await expect(composer.getByRole('status')).toContainText('1 new image');
    await page.unroute('**/api/v1/tasks/*/remarks/');
    await composer.getByRole('button', { name: 'Post remark', exact: true }).click();
    const stream = page.getByRole('list', { name: 'Chronological remarks', exact: true });
    await expect(stream.getByRole('article')).toHaveCount(1);
    await expect(stream.getByRole('img')).toBeVisible();
  } finally { await f.content.close(); await f.admin.close(); }
});
