import { expect, test } from "@playwright/test";

test("the development server accepts its internal Compose hostname", async ({ request }) => {
  const response = await request.get("/", { headers: { Host: "frontend:5173" } });
  expect(response.status()).toBe(200);
  expect(await response.text()).toContain("<title>Task Tracker</title>");
});

test("the real frontend reaches Django and PostgreSQL", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("Task Tracker");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("Django API and PostgreSQL are connected.");
  await page.getByRole("button", { name: "Check connection" }).click();
  await expect(page.getByRole("status")).toHaveText("Django API and PostgreSQL are connected.");
});

test("a failed connection can be retried", async ({ page }) => {
  await page.route("**/api/v1/health/", route => route.fulfill({ status: 503, body: "{}" }));
  await page.goto("/");
  await expect(page.getByRole("status")).toContainText("Cannot connect");
  await page.unroute("**/api/v1/health/");
  await page.getByRole("button", { name: "Check connection" }).click();
  await expect(page.getByRole("status")).toHaveText("Django API and PostgreSQL are connected.");
});
