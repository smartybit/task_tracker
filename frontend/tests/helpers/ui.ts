import { expect, type Page } from '@playwright/test';

export async function closeTaskWindow(page: Page) {
  const dialog = page.getByRole('dialog');
  if (!await dialog.count()) return;
  const close = dialog.getByRole('button', { name: /^(Close details|Close window)$/ });
  if (!await close.count()) return;
  const discard = (prompt: import('@playwright/test').Dialog) => { void prompt.accept(); };
  page.on('dialog', discard);
  try { await close.click(); await expect(dialog).not.toBeVisible(); }
  finally { page.off('dialog', discard); }
}

export async function taskCommand(page: Page, label: string) {
  const dialog = page.getByRole('dialog');
  if (await dialog.getAttribute('aria-label') === label) return;
  if (await dialog.getByRole('button', { name: 'Back to details', exact: true }).count()) {
    const discard = (prompt: import('@playwright/test').Dialog) => { void prompt.accept(); };
    page.on('dialog', discard);
    try { await dialog.getByRole('button', { name: 'Back to details', exact: true }).click(); }
    finally { page.off('dialog', discard); }
  }
  await dialog.getByRole('button', { name: label, exact: true }).click();
}

export async function administration(page: Page, name: string) {
  if (!await page.getByRole('navigation', { name: 'Administration', exact: true }).count())
    await page.getByRole('button', { name: 'Administration', exact: true }).click();
  await page.getByRole('navigation', { name: 'Administration', exact: true }).getByRole('button', { name, exact: true }).click();
}
