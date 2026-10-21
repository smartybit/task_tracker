import { administration } from "./helpers/ui";
import { appURL } from "./helpers/urls";
import { expect, test } from "@playwright/test";

test("the development server accepts its internal Compose hostname", async ({ request }) => {
  const response = await request.get(appURL, { headers: { Host: "frontend:5173" } });
  expect(response.status()).toBe(200);
  expect(await response.text()).toContain("<title>Task Tracker</title>");
});

async function diagnostics(page: import('@playwright/test').Page) {
  const accountRequests: string[] = [];
  page.on('request', request => { if (/\/api\/v1\/users\/\?/.test(request.url())) accountRequests.push(request.url()); });
  await page.goto(appURL);
  await page.getByLabel('Email', { exact: true }).fill('admin@example.test');
  await page.getByLabel('Password', { exact: true }).fill('synthetic-test-only-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Tasks', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Check connection' })).toHaveCount(0);
  expect(accountRequests).toEqual([]);
  await administration(page, 'System status');
}

test("the real frontend reaches Django and PostgreSQL", async ({ page }) => {
  await diagnostics(page);
  await expect(page).toHaveTitle("Task Tracker");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("Django API and PostgreSQL are connected.", { timeout: 15000 });
  await page.getByRole("button", { name: "Check connection" }).click();
  await expect(page.getByRole("status")).toHaveText("Django API and PostgreSQL are connected.", { timeout: 15000 });
});

test("a failed connection can be retried", async ({ page }) => {
  await page.route("**/api/v1/health/", route => route.fulfill({ status: 503, body: "{}" }));
  await diagnostics(page);
  await expect(page.getByRole("status")).toContainText("Cannot connect");
  await page.unroute("**/api/v1/health/");
  await page.getByRole("button", { name: "Check connection" }).click();
  await expect(page.getByRole("status")).toHaveText("Django API and PostgreSQL are connected.", { timeout: 15000 });
});
