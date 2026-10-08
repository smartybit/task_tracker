import { expect, test, type APIRequestContext, type BrowserContext, type Page } from "@playwright/test";

const fixturePassword = "synthetic-test-only-password";
const password = "browser-stage-three-long-password";
const baseURL = process.env.BASE_URL ?? "http://frontend:5173";
async function login(page: Page, email = "admin@example.test", secret = fixturePassword) {
  await page.goto("/");
  const form = page.getByRole("form", { name: "Sign in", exact: true });
  await form.getByLabel("Email", { exact: true }).fill(email);
  await form.getByLabel("Password", { exact: true }).fill(secret);
  await form.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}
async function apiLogin(request: APIRequestContext) {
  const csrf = await (await request.get(`${baseURL}/api/v1/auth/csrf/`)).json();
  const response = await request.post(`${baseURL}/api/v1/auth/login/`, {
    headers: { "X-CSRFToken": csrf.csrf_token, Origin: baseURL },
    data: { email: "admin@example.test", password: fixturePassword },
  });
  expect(response.status()).toBe(200);
  return (await response.json()).csrf_token as string;
}
async function setupUser(context: BrowserContext, email: string, extra = {}) {
  const token = await apiLogin(context.request);
  const response = await context.request.post(`${baseURL}/api/v1/users/`, {
    headers: { "X-CSRFToken": token, Origin: baseURL }, data: { email, password, ...extra },
  });
  expect(response.status()).toBe(201);
  return { user: await response.json(), token };
}

test("browser login normalizes email, preserves sessions, and signs out", async ({ page }) => {
  await login(page, " ADMIN@EXAMPLE.TEST ");
  await page.reload();
  await expect(page.getByRole("navigation", { name: "Management" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("form", { name: "Sign in", exact: true })).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill("admin@example.test");
  await page.getByLabel("Password", { exact: true }).fill("wrong-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Email or password is incorrect.");
});

test("the Compose proxy enforces CSRF on login and authenticated mutations", async ({ context }) => {
  const request = context.request;
  let response = await request.post(`${baseURL}/api/v1/auth/login/`, { data: { email: "admin@example.test", password: fixturePassword } });
  expect(response.status()).toBe(403);
  expect((await response.json()).code).toBe("csrf_failed");
  const csrf = await (await request.get(`${baseURL}/api/v1/auth/csrf/`)).json();
  response = await request.post(`${baseURL}/api/v1/auth/login/`, { headers: { "X-CSRFToken": csrf.csrf_token, Origin: "http://evil.invalid" }, data: { email: "admin@example.test", password: fixturePassword } });
  expect(response.status()).toBe(403);
  const token = await apiLogin(request);
  const invalidHeaders: Record<string, string>[] = [{}, { "X-CSRFToken": "invalid" }, { "X-CSRFToken": token, Origin: "http://evil.invalid" }];
  for (const headers of invalidHeaders) {
    response = await request.post(`${baseURL}/api/v1/organizations/`, { headers, data: { name: "Must not exist" } });
    expect(response.status()).toBe(403);
    expect((await response.json()).code).toBe("csrf_failed");
  }
  expect((await (await request.get(`${baseURL}/api/v1/organizations/`)).json()).results.some((org: { name: string }) => org.name === "Must not exist")).toBe(false);
});

test("administrator creates, edits, deactivates, and resets an account through the UI", async ({ page, browser }) => {
  const email = "ui-account@example.test";
  await login(page);
  const create = page.getByRole("form", { name: "Create account", exact: true });
  await create.getByLabel("Account email").fill(email);
  await create.getByLabel("Display name").fill("Browser Person");
  await create.getByLabel("Initial password").fill(password);
  await create.getByLabel("Write Others’ Timesheets").check();
  await expect(create.getByLabel("Read Others’ Timesheets")).toBeChecked();
  await create.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Changes saved.");
  await page.getByLabel("Manage account").selectOption({ label: email });
  const edit = page.getByRole("form", { name: "Edit account", exact: true });
  await edit.getByLabel("Display name").fill("Updated Person");
  await edit.getByRole("button", { name: "Save account" }).click();
  await expect(page.getByRole("row").filter({ hasText: email })).toContainText("Updated Person");
  const other = await browser.newContext();
  try {
    const colleague = await other.newPage();
    await login(colleague, email, password);
    await expect(colleague.getByRole("navigation", { name: "Management" })).toHaveCount(0);
    await edit.getByLabel("Active account").uncheck();
    await edit.getByRole("button", { name: "Save account" }).click();
    await expect(page.getByRole("row").filter({ hasText: email })).toContainText("Inactive");
    await colleague.getByRole("button", { name: "Refresh access" }).click();
    await expect(colleague.getByRole("form", { name: "Sign in", exact: true })).toBeVisible();
    await edit.getByLabel("Active account").check();
    await edit.getByRole("button", { name: "Save account" }).click();
    await expect(page.getByRole("row").filter({ hasText: email })).toContainText("Active");
    await login(colleague, email, password);
    const reset = page.getByRole("form", { name: "Reset password", exact: true });
    await reset.getByLabel("New password").fill("new-browser-stage-three-password");
    await reset.getByRole("button", { name: "Reset password", exact: true }).click();
    await expect(page.getByRole("alert")).toHaveText("Changes saved.");
    await colleague.getByRole("button", { name: "Refresh access" }).click();
    await expect(colleague.getByRole("form", { name: "Sign in", exact: true })).toBeVisible();
    await login(colleague, email, "new-browser-stage-three-password");
  } finally { await other.close(); }
});

test("catalog administration protects references and supports rename/delete", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Catalogs", exact: true }).click();
  const org = page.getByRole("form", { name: "Create organization", exact: true });
  await org.getByLabel("Organization name").fill("Browser Organization");
  await org.getByRole("button", { name: "Create organization", exact: true }).click();
  await expect(page.getByRole("button", { name: "Delete organization Browser Organization", exact: true })).toBeVisible();
  const project = page.getByRole("form", { name: "Create project", exact: true });
  await project.getByRole("combobox", { name: "Organization", exact: true }).selectOption({ label: "Browser Organization" });
  await project.getByLabel("Project name").fill("Browser Project");
  await project.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("button", { name: "Rename project Browser Project", exact: true })).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Delete organization Browser Organization", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("conflicts with existing records");
  await page.getByLabel("project name Browser Project", { exact: true }).fill("Renamed Browser Project");
  await page.getByRole("button", { name: "Rename project Browser Project", exact: true }).click();
  await expect(page.getByRole("button", { name: "Delete project Renamed Browser Project", exact: true })).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Delete project Renamed Browser Project", exact: true }).click();
  await expect(page.getByRole("button", { name: "Delete project Renamed Browser Project", exact: true })).toHaveCount(0);
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Delete organization Browser Organization", exact: true }).click();
  await expect(page.getByRole("button", { name: "Delete organization Browser Organization", exact: true })).toHaveCount(0);
});

test("grant inheritance and live revocation work across separate browser sessions", async ({ page, context, browser }) => {
  const email = "ui-grants@example.test";
  const { user, token } = await setupUser(context, email);
  await page.goto("/");
  await page.getByRole("button", { name: "Grants", exact: true }).click();
  await page.getByLabel("Grant account").selectOption(user.id);
  await page.getByLabel("Grant target").selectOption({ label: "Example Studio" });
  const grant = page.getByRole("form", { name: "Local grant", exact: true });
  await grant.getByLabel("Task write", { exact: true }).check();
  await expect(grant.getByLabel("Task read", { exact: true })).toBeChecked();
  await grant.getByRole("button", { name: "Save grant" }).click();
  await expect(page.getByRole("alert")).toHaveText("Changes saved.");
  const other = await browser.newContext();
  try {
    const colleague = await other.newPage();
    await login(colleague, email, password);
    await expect(colleague.getByRole("region", { name: "Available projects" })).toContainText("Internal");
    await page.getByLabel("Grant scope").selectOption("projects");
    await page.getByLabel("Grant target").selectOption({ label: "Internal" });
    await expect(grant.getByText("Inherited flags:")).toContainText("Task read, Task write");
    await grant.getByRole("button", { name: "Save grant" }).click();
    await expect(page.getByRole("alert")).toHaveText("Changes saved.");
    await colleague.getByRole("button", { name: "Refresh access" }).click();
    await expect(colleague.getByRole("region", { name: "Available projects" })).toContainText("Internal");
    await page.getByLabel("Grant scope").selectOption("organizations");
    await page.getByLabel("Grant target").selectOption({ label: "Example Studio" });
    await grant.getByLabel("Task read", { exact: true }).uncheck();
    await grant.getByLabel("Task write", { exact: true }).uncheck();
    await grant.getByRole("button", { name: "Save grant" }).click();
    await expect(page.getByRole("alert")).toHaveText("Changes saved.");
    await colleague.getByRole("button", { name: "Refresh access" }).click();
    await expect(colleague.getByText("No project access is configured.")).toBeVisible();
    // Direct API configuration retains the supported write-without-read state.
    const projects = (await (await context.request.get(`${baseURL}/api/v1/projects/`)).json()).results;
    const internal = projects.find((item: { name: string }) => item.name === "Internal");
    expect((await context.request.put(`${baseURL}/api/v1/users/${user.id}/grants/projects/${internal.id}/`, { headers: { "X-CSRFToken": token, Origin: baseURL }, data: { task_write: true } })).status()).toBe(200);
    await colleague.getByRole("button", { name: "Refresh access" }).click();
    await expect(colleague.getByRole("region", { name: "Available projects" })).toContainText("No task read, Task write");
    expect((await other.request.get(`${baseURL}/api/v1/users/`)).status()).toBe(403);
  } finally { await other.close(); }
});

test("revoking administrator status removes management access without another login", async ({ page, context, browser }) => {
  const { user, token } = await setupUser(context, "ui-admin-revocation@example.test", { is_admin: true });
  const other = await browser.newContext();
  try {
    const administrator = await other.newPage();
    await login(administrator, user.email, password);
    await expect(administrator.getByRole("navigation", { name: "Management" })).toBeVisible();
    expect((await context.request.patch(`${baseURL}/api/v1/users/${user.id}/`, { headers: { "X-CSRFToken": token, Origin: baseURL }, data: { is_admin: false } })).status()).toBe(200);
    await administrator.getByRole("button", { name: "Refresh access" }).click();
    await expect(administrator.getByRole("navigation", { name: "Management" })).toHaveCount(0);
    await expect(administrator.getByRole("heading", { name: "Your projects", exact: true })).toBeVisible();
  } finally { await other.close(); }
});
