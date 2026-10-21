import { taskCommand, closeTaskWindow } from "./helpers/ui";
import { expect, test } from '@playwright/test';
import { flags, login, setup } from './helpers/content';

test('English and Russian word forms find authorized tasks and remarks and navigate to originals', async ({ page, browser }, testInfo) => {
  const f = await setup(browser, 'multilingual-search');
  try {
    await f.contentWrite(`tasks/${f.task.id}/`, { title: 'Running releases', description: 'We are running задачи <script>alert(1)</script>', expected_revision: 0 }, 'PATCH');
    const remark = await f.contentWrite(`tasks/${f.task.id}/remarks/`, { body: 'We discussed running задачу' });
    const org = await f.write('organizations/', { name: `Hidden search ${f.task.id}` });
    const project = await f.write('projects/', { name: 'Hidden search project', organization: org.id });
    await f.write(`users/${f.bob.id}/grants/projects/${project.id}/`, flags, 'PUT');
    const hidden = { title: 'HIDDEN running задачи', description: 'HIDDEN protected description', project: project.id, status: f.task.status };
    const preview = await f.contentWrite('tasks/preview/', hidden);
    const target = await f.contentWrite('tasks/', { ...hidden, confirm: true, expected_domain_revision: preview.domain_revision });
    await f.contentWrite(`tasks/${target.id}/remarks/`, { body: 'HIDDEN running задачи discussion' });
    await login(page, f.alice.email);
    await page.getByRole('button', { name: 'Search tasks and remarks', exact: true }).click();
    const search = page.getByRole('region', { name: 'Content search', exact: true });
    const input = search.getByRole('searchbox', { name: 'Search tasks and remarks', exact: true });
    for (const query of ['runs', 'задачами', 'runs задачами']) {
      await input.fill(query);
      await search.getByRole('button', { name: 'Search content', exact: true }).click();
      await expect(search.getByRole('status')).toContainText('2 results');
      await expect(search).not.toContainText('HIDDEN');
      await expect(search.locator('script')).toHaveCount(0);
    }
    const results = search.getByRole('list', { name: 'Search results', exact: true });
    await results.getByRole('button', { name: 'Task: Running releases', exact: true }).click();
    await expect(page.getByRole('dialog', { name: 'Task description', exact: true }).getByRole('heading', { name: 'Running releases', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Back to search', exact: true }).click();
    await results.getByRole('button', { name: 'Remark in Running releases', exact: true }).click();
    await expect(page.locator(`#remark-${remark.id}`)).toBeFocused();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.getByRole('button', { name: 'Back to search', exact: true }).click();
    await search.screenshot({ path: testInfo.outputPath('search-narrow.png') });
  } finally { await f.content.close(); await f.admin.close(); }
});

test('failed searches clear stale snippets and current grants govern repeated queries', async ({ page, browser }) => {
  const f = await setup(browser, 'search-recovery');
  try {
    await f.contentWrite(`tasks/${f.task.id}/remarks/`, { body: 'Needle protected discussion' });
    await login(page, f.alice.email);
    await page.getByRole('button', { name: 'Search tasks and remarks', exact: true }).click();
    const search = page.getByRole('region', { name: 'Content search', exact: true });
    const input = search.getByRole('searchbox', { name: 'Search tasks and remarks', exact: true });
    const submit = search.getByRole('button', { name: 'Search content', exact: true });
    await input.fill('needle'); await submit.click();
    await expect(search.getByRole('status')).toContainText('1 results');
    await expect(search).toContainText('protected discussion');
    await page.route('**/api/v1/search/**', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ code: 'unavailable', message: 'Synthetic search failure.' }) }));
    await submit.click();
    await expect(search.getByRole('alert')).toContainText('Synthetic search failure');
    await expect(search).not.toContainText('protected discussion');
    await expect(input).toHaveValue('needle');
    await page.unroute('**/api/v1/search/**');
    await submit.click(); await expect(search.getByRole('status')).toContainText('1 results');
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, { task_read: true, remark_write: true }, 'PUT');
    await submit.click();
    await expect(search.getByRole('status')).toContainText('0 results');
    await expect(search).not.toContainText('protected discussion');
    await expect(search.getByRole('list', { name: 'Search results', exact: true }).getByRole('listitem')).toHaveCount(0);
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, flags, 'PUT');
    await submit.click(); await expect(search.getByRole('status')).toContainText('1 results');
    await page.getByRole('button', { name: 'Close window', exact: true }).click();
    await page.getByRole('button', { name: 'Refresh access', exact: true }).click();
    await page.getByRole('button', { name: 'Search tasks and remarks', exact: true }).click();
    await expect(search.getByRole('list', { name: 'Search results', exact: true })).toHaveCount(0);
  } finally { await f.content.close(); await f.admin.close(); }
});
