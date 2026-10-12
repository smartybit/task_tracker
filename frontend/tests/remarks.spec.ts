import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";

const baseURL = process.env.BASE_URL ?? "http://frontend:5173";
const password = "browser-stage-eight-long-password";
const flags = { task_read: true, task_write: true, remark_read: true, remark_write: true };

async function login(page: Page, email: string) {
  await page.goto("/");
  const form = page.getByRole("form", { name: "Sign in", exact: true });
  await form.getByLabel("Email", { exact: true }).fill(email);
  await form.getByLabel("Password", { exact: true }).fill(password);
  await form.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}

async function apiLogin(request: APIRequestContext, email: string, secret: string) {
  const csrf = await (await request.get(`${baseURL}/api/v1/auth/csrf/`)).json();
  const response = await request.post(`${baseURL}/api/v1/auth/login/`, {
    headers: { "X-CSRFToken": csrf.csrf_token, Origin: baseURL }, data: { email, password: secret },
  });
  expect(response.status()).toBe(200);
  return (await response.json()).csrf_token as string;
}

async function setup(browser: Browser, name: string) {
  const key = `${name}-${Date.now()}`;
  const admin = await browser.newContext();
  const token = await apiLogin(admin.request, "admin@example.test", "synthetic-test-only-password");
  async function write(path: string, data: unknown, method = "POST") {
    const response = await admin.request.fetch(`${baseURL}/api/v1/${path}`, {
      method, headers: { "X-CSRFToken": token, Origin: baseURL }, data,
    });
    expect(response.ok()).toBeTruthy();
    return response.json();
  }
  const users = [];
  for (const person of ["Alice", "Bob"]) users.push(await write("users/", {
    email: `remarks-${person}-${key}@example.test`, display_name: `${person} ${key}`, password,
  }));
  const org = await write("organizations/", { name: `Remarks ${key}` });
  const project = await write("projects/", { name: `Discussion ${key}`, organization: org.id });
  const me = await (await admin.request.get(`${baseURL}/api/v1/auth/me/`)).json();
  for (const user of [...users, me]) await write(`users/${user.id}/grants/projects/${project.id}/`, flags, "PUT");
  const statuses = await (await admin.request.get(`${baseURL}/api/v1/statuses/`)).json();
  const payload = { title: `Discussion ${name}`, description: "Task with remarks", project: project.id,
    status: statuses.results.find((row: { name: string }) => row.name === "In Progress").id };
  const preview = await write("tasks/preview/", payload);
  const task = await write("tasks/", { ...payload, confirm: true, expected_domain_revision: preview.domain_revision });
  return { admin, write, alice: users[0], bob: users[1], project, task };
}

const discussion = (page: Page) => page.getByRole("region", { name: "Task remarks", exact: true });
const stream = (page: Page) => discussion(page).getByRole("list", { name: "Chronological remarks", exact: true });
const stars = (page: Page) => discussion(page).getByRole("region", { name: "Starred remarks", exact: true });

async function open(page: Page, title: string) {
  await page.getByRole("list", { name: "Task list", exact: true }).getByRole("button", { name: title, exact: true }).click();
  await expect(discussion(page).getByRole("textbox", { name: "New remark", exact: true })).toBeEnabled();
}

async function post(page: Page, text: string) {
  const composer = discussion(page).getByRole("form", { name: "Post remark", exact: true });
  await composer.getByRole("textbox", { name: "New remark", exact: true }).fill(text);
  await composer.getByRole("button", { name: "Post remark", exact: true }).click();
  await expect(discussion(page).getByRole("alert")).toHaveText("Remark posted.");
}

test("remarks retain chronology and authors, share stars, and navigate to originals", async ({ page, browser }, testInfo) => {
  const f = await setup(browser, "collaboration");
  const other = await browser.newContext();
  try {
    await login(page, f.alice.email); await open(page, f.task.title);
    const text = "First remark\nРусский текст <script>alert('unsafe')</script>";
    await post(page, text);
    await post(page, "Second chronological remark");
    await expect(stream(page).getByRole("article")).toHaveCount(2);
    await expect(stream(page).getByRole("article").first()).toContainText(text);
    await expect(stream(page).locator("script")).toHaveCount(0);
    await stream(page).getByRole("article").first().getByRole("button", { name: "Star remark", exact: true }).click();
    await expect(stars(page).getByRole("link")).toHaveCount(1);
    await stars(page).getByRole("link").click();
    await expect(stream(page).getByRole("article").first()).toBeFocused();
    await f.write(`users/${f.bob.id}/grants/projects/${f.project.id}/`, { ...flags, task_write: false }, "PUT");
    const colleague = await other.newPage();
    await login(colleague, f.bob.email); await open(colleague, f.task.title);
    await expect(colleague.getByRole("form", { name: "Edit task", exact: true })).not.toBeVisible();
    await expect(stars(colleague).getByRole("link")).toContainText("First remark");
    await stream(colleague).getByRole("article").first().getByRole("button", { name: "Edit remark", exact: true }).click();
    const edit = discussion(colleague).getByRole("form", { name: "Edit remark", exact: true });
    await edit.getByRole("textbox", { name: "Remark text", exact: true }).fill("Edited by Bob");
    await edit.getByRole("button", { name: "Save remark", exact: true }).click();
    await expect(discussion(colleague).getByRole("alert")).toHaveText("Remark saved.");
    await expect(stream(colleague).getByRole("article").first()).toContainText(f.alice.display_name);
    await expect(stream(colleague).getByRole("article").first()).toContainText("Edited");
    await discussion(page).getByRole("button", { name: "Reload remarks", exact: true }).click();
    await expect(stars(page).getByRole("link")).toContainText("Edited by Bob");
    await expect(stream(page).getByRole("article").last()).toContainText("Second chronological remark");
    await page.screenshot({ path: testInfo.outputPath("remarks-desktop.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(stars(page).getByRole("link")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath("remarks-narrow.png"), fullPage: true });
    await stream(colleague).getByRole("article").first().getByRole("button", { name: "Unstar remark", exact: true }).click();
    await expect(stars(colleague).getByRole("link")).toHaveCount(0);
    colleague.once("dialog", dialog => dialog.accept());
    await stream(colleague).getByRole("article").first().getByRole("button", { name: "Delete remark", exact: true }).click();
    await expect(stream(colleague).getByRole("article")).toHaveCount(1);
    await colleague.reload(); await open(colleague, f.task.title);
    await expect(stream(colleague).getByRole("article")).toHaveCount(1);
  } finally { await other.close(); await f.admin.close(); }
});

test("write-only remarks use safe acknowledgements and revocation preserves unsaved text", async ({ page, browser }) => {
  const f = await setup(browser, "access");
  try {
    await f.write(`tasks/${f.task.id}/remarks/`, { body: "Protected existing discussion" });
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, { task_read: true, remark_write: true }, "PUT");
    await login(page, f.alice.email); await open(page, f.task.title);
    await expect(discussion(page)).not.toContainText("Protected existing discussion");
    await post(page, "Write-only contribution");
    await expect(discussion(page)).not.toContainText("Write-only contribution");
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, { task_read: true, remark_read: true }, "PUT");
    await discussion(page).getByRole("button", { name: "Reload remarks", exact: true }).click();
    await expect(stream(page)).toContainText("Write-only contribution");
    await expect(discussion(page).getByRole("form", { name: "Post remark", exact: true })).not.toBeVisible();
    await expect(discussion(page).getByRole("button", { name: "Edit remark", exact: true })).toHaveCount(0);
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, flags, "PUT");
    await discussion(page).getByRole("button", { name: "Reload remarks", exact: true }).click();
    await stream(page).getByRole("article").first().getByRole("button", { name: "Edit remark", exact: true }).click();
    await discussion(page).getByRole("textbox", { name: "Remark text", exact: true }).fill("Unsaved private draft");
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, { task_read: true }, "PUT");
    await discussion(page).getByRole("button", { name: "Save remark", exact: true }).click();
    await expect(discussion(page).getByRole("alert")).toContainText("remark write access");
    await expect(discussion(page)).not.toContainText("Protected existing discussion");
    await expect(discussion(page).getByLabel("Unsaved remark text", { exact: true })).toHaveText("Unsaved private draft");
    const stored = await (await f.admin.request.get(`${baseURL}/api/v1/tasks/${f.task.id}/remarks/`)).json();
    expect(stored.results[0].body).toBe("Protected existing discussion");
  } finally { await f.admin.close(); }
});

test("stale and failed saves keep edits, and acknowledged saves with failed reloads are explicit", async ({ page, browser }) => {
  const f = await setup(browser, "recovery");
  const other = await browser.newContext();
  try {
    await login(page, f.alice.email); await open(page, f.task.title); await post(page, "Original discussion");
    const colleague = await other.newPage(); await login(colleague, f.bob.email); await open(colleague, f.task.title);
    await stream(colleague).getByRole("button", { name: "Edit remark", exact: true }).click();
    const input = discussion(colleague).getByRole("textbox", { name: "Remark text", exact: true });
    await input.fill("Stale unsaved correction");
    await stream(page).getByRole("button", { name: "Star remark", exact: true }).click();
    await expect(discussion(page).getByRole("alert")).toHaveText("Remark starred.");
    await discussion(colleague).getByRole("button", { name: "Save remark", exact: true }).click();
    await expect(discussion(colleague).getByRole("alert")).toContainText("remark changed");
    await expect(input).toHaveValue("Stale unsaved correction");
    await expect(discussion(colleague).getByRole("button", { name: "Save remark", exact: true })).toBeDisabled();
    colleague.once("dialog", dialog => dialog.accept());
    await discussion(colleague).getByRole("button", { name: "Reload remarks", exact: true }).click();
    await stream(colleague).getByRole("button", { name: "Edit remark", exact: true }).click();
    await input.fill("Recovered correction");
    await colleague.route("**/api/v1/remarks/*/", route => route.request().method() === "PATCH"
      ? route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "unavailable", message: "Synthetic save failure." }) }) : route.continue());
    await discussion(colleague).getByRole("button", { name: "Save remark", exact: true }).click();
    await expect(discussion(colleague).getByRole("alert")).toContainText("Synthetic save failure");
    await expect(input).toHaveValue("Recovered correction");
    await colleague.unroute("**/api/v1/remarks/*/");
    await colleague.route("**/api/v1/tasks/*/remarks/**", route => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "unavailable", message: "Synthetic reload failure." }) }));
    await discussion(colleague).getByRole("button", { name: "Save remark", exact: true }).click();
    await expect(discussion(colleague).getByRole("alert")).toHaveText("Remark saved. Reload failed; reload remarks before another change.");
    await colleague.unroute("**/api/v1/tasks/*/remarks/**");
    await discussion(colleague).getByRole("button", { name: "Reload remarks", exact: true }).click();
    await expect(stream(colleague)).toContainText("Recovered correction");
    const newText = discussion(colleague).getByRole("textbox", { name: "New remark", exact: true });
    await newText.focus(); await colleague.keyboard.type("Keyboard contribution"); await colleague.keyboard.press("Tab");
    await expect(discussion(colleague).getByRole("button", { name: "Post remark", exact: true })).toBeFocused();
    await discussion(colleague).getByRole("button", { name: "Post remark", exact: true }).dblclick();
    await expect(discussion(colleague).getByRole("alert")).toHaveText("Remark posted.");
    await expect(stream(colleague).getByText("Keyboard contribution", { exact: true })).toHaveCount(1);
  } finally { await other.close(); await f.admin.close(); }
});

test("task deletion requires remark write and confirms the current remark count", async ({ page, browser }) => {
  const f = await setup(browser, "deletion");
  try {
    await login(page, f.alice.email); await open(page, f.task.title); await post(page, "Deletion discussion");
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, { ...flags, remark_write: false }, "PUT");
    await page.getByRole("button", { name: "Preview deletion", exact: true }).click();
    await expect(page.getByRole("region", { name: "Tasks", exact: true }).getByRole("alert").first()).toContainText("remark write access");
    await f.write(`users/${f.alice.id}/grants/projects/${f.project.id}/`, flags, "PUT");
    await page.getByRole("button", { name: "Preview deletion", exact: true }).click();
    const confirmation = page.getByRole("dialog", { name: "Confirm task change", exact: true });
    await expect(confirmation).toContainText("deletes 1 remark(s)");
    await f.write(`tasks/${f.task.id}/remarks/`, { body: "Arrived after preview" });
    await confirmation.getByRole("button", { name: "Confirm change", exact: true }).click();
    await expect(page.getByRole("region", { name: "Tasks", exact: true }).getByRole("alert").first()).toContainText("preview is out of date");
    await page.getByRole("button", { name: "Preview deletion", exact: true }).click();
    await expect(confirmation).toContainText("deletes 2 remark(s)");
    await confirmation.getByRole("button", { name: "Confirm change", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Task description", exact: true })).not.toBeVisible();
    await expect(page.getByRole("list", { name: "Task list", exact: true })).not.toContainText(f.task.title);
  } finally { await f.admin.close(); }
});
