import { origin } from "./helpers/urls";
import { expect, test } from "@playwright/test";
import { baseURL, flags, login, setup } from "./helpers/content";

test("description references survive renames and mask revoked or deleted targets", async ({ page, browser }) => {
  const f = await setup(browser, "reference-lifecycle");
  try {
    const statuses = await (await f.content.request.get(`${baseURL}/api/v1/statuses/`)).json();
    const payload = { title: 'Reference destination', description: 'Destination text', project: f.project.id, status: statuses.results[0].id };
    const preview = await f.contentWrite('tasks/preview/', payload);
    const target = await f.contentWrite('tasks/', { ...payload, confirm: true, expected_domain_revision: preview.domain_revision });
    await login(page, f.alice.email);
    const taskList = page.getByRole('list', { name: 'Task list', exact: true });
    await taskList.getByRole('button', { name: f.task.title, exact: true }).click();
    const edit = page.getByRole('form', { name: 'Edit task', exact: true });
    await edit.getByRole('textbox', { name: 'Description', exact: true }).fill('See ');
    await edit.getByRole('button', { name: 'Insert reference', exact: true }).click();
    await edit.getByRole('combobox', { name: 'Reference task', exact: true }).selectOption(target.id);
    await edit.getByRole('button', { name: 'Insert selected reference', exact: true }).click();
    await expect(edit.getByRole('textbox', { name: 'Description', exact: true })).toBeFocused();
    await edit.getByRole('button', { name: 'Save task', exact: true }).click();
    const detail = page.getByRole('dialog', { name: 'Task description', exact: true });
    await expect(detail.getByRole('link', { name: target.title, exact: true })).toBeVisible();
    await detail.getByRole('link', { name: target.title, exact: true }).click();
    await expect(detail.getByRole('heading', { name: target.title, exact: true })).toBeVisible();
    const targetEdit = page.getByRole('form', { name: 'Edit task', exact: true });
    await targetEdit.getByRole('textbox', { name: 'Task title', exact: true }).fill('Renamed destination');
    await targetEdit.getByRole('button', { name: 'Save task', exact: true }).click();
    await taskList.getByRole('button', { name: f.task.title, exact: true }).click();
    await expect(detail.getByRole('link', { name: 'Renamed destination', exact: true })).toBeVisible();
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, {}, 'PUT');
    await detail.getByRole('button', { name: 'Refresh references', exact: true }).click();
    await expect(detail.getByRole('link')).toHaveCount(0);
    await expect(detail.locator('.unavailable-reference')).toHaveText('Unavailable reference');
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, flags, 'PUT');
    const deleted = await f.contentWrite(`tasks/${target.id}/delete/preview/`, { expected_revision: 1 });
    const token = await (await f.content.request.get(`${baseURL}/api/v1/auth/csrf/`)).json();
    const response = await f.content.request.delete(`${baseURL}/api/v1/tasks/${target.id}/`, {
      headers: { 'X-CSRFToken': token.csrf_token, Origin: origin },
      data: { expected_revision: 1, expected_domain_revision: deleted.domain_revision, confirm: true },
    });
    expect(response.ok()).toBeTruthy();
    await detail.getByRole('button', { name: 'Refresh references', exact: true }).click();
    await expect(detail.locator('.unavailable-reference')).toHaveText('Unavailable reference');
  } finally { await f.content.close(); await f.admin.close(); }
});

test("remark picker inserts a stable link and navigation focuses the original", async ({ page, browser }) => {
  const f = await setup(browser, 'remark-reference');
  try {
    const remark = await f.contentWrite(`tasks/${f.task.id}/remarks/`, { body: 'Original referenced remark' });
    await login(page, f.alice.email);
    await page.getByRole('list', { name: 'Task list', exact: true }).getByRole('button', { name: f.task.title, exact: true }).click();
    const form = page.getByRole('form', { name: 'Post remark', exact: true });
    await form.getByRole('textbox', { name: 'New remark', exact: true }).fill('Read ');
    await form.getByRole('button', { name: 'Insert reference', exact: true }).click();
    await form.getByRole('combobox', { name: 'Reference kind', exact: true }).selectOption('remark');
    await form.getByRole('combobox', { name: 'Reference task', exact: true }).selectOption(f.task.id);
    await form.getByRole('combobox', { name: 'Reference remark', exact: true }).selectOption(remark.id);
    await form.getByRole('button', { name: 'Insert selected reference', exact: true }).click();
    await form.getByRole('button', { name: 'Post remark', exact: true }).click();
    const stream = page.getByRole('list', { name: 'Chronological remarks', exact: true });
    await stream.getByRole('link', { name: 'Remark: Original referenced remark', exact: true }).click();
    await expect(page.locator(`#remark-${remark.id}`)).toBeFocused();
    await expect(stream.getByRole('article')).toHaveCount(2);
  } finally { await f.content.close(); await f.admin.close(); }
});
