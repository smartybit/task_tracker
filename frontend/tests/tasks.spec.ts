import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";

const baseURL = process.env.BASE_URL ?? "http://frontend:5173";
const fixturePassword = "synthetic-test-only-password";
const password = "browser-stage-four-long-password";
async function login(page: Page, email: string, secret = password) {
  await page.goto("/");
  const form = page.getByRole("form", { name: "Sign in", exact: true });
  await form.getByLabel("Email", { exact: true }).fill(email);
  await form.getByLabel("Password", { exact: true }).fill(secret);
  await form.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}
async function loginAPI(request: APIRequestContext, email = "admin@example.test", secret = fixturePassword) {
  const csrf = await (await request.get(`${baseURL}/api/v1/auth/csrf/`)).json();
  const response = await request.post(`${baseURL}/api/v1/auth/login/`, { headers: { "X-CSRFToken": csrf.csrf_token, Origin: baseURL }, data: { email, password: secret } });
  expect(response.status()).toBe(200);
  return (await response.json()).csrf_token as string;
}
async function setup(browser: Browser, key: string, flags = { task_read: true, task_write: true }) {
  key = `${key}-${Date.now()}`;
  const admin = await browser.newContext();
  const token = await loginAPI(admin.request);
  async function write(path: string, data: unknown, method = "POST") {
    const result = await admin.request.fetch(`${baseURL}/api/v1/${path}`, { method, headers: { "X-CSRFToken": token, Origin: baseURL }, data });
    expect(result.ok()).toBeTruthy();
    return result.status() === 204 ? null : result.json();
  }
  const user = await write("users/", { email: `tasks-${key}@example.test`, display_name: `Task user ${key}`, password });
  const colleague = await write("users/", { email: `task-owner-${key}@example.test`, display_name: `Task owner ${key}`, password });
  const org = await write("organizations/", { name: `Task org ${key}` });
  const project = await write("projects/", { name: `Task project ${key}`, organization: org.id });
  const other = await write("projects/", { name: `Destination ${key}`, organization: org.id });
  for (const person of [user, colleague]) {
    for (const p of [project, other]) await write(`users/${person.id}/grants/projects/${p.id}/`, flags, "PUT");
  }
  return { admin, write, user, colleague, project, other };
}
async function confirm(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Confirm task change", exact: true });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Confirm change", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByRole("region", { name: "Tasks", exact: true }).getByRole("alert")).toHaveText("Changes saved.");
}
async function create(page: Page, title: string, project: string, parent?: string, status = "In Progress") {
  const form = page.getByRole("form", { name: "Create task", exact: true });
  await expect(form).toBeVisible();
  await form.getByLabel("Task title", { exact: true }).fill(title);
  await form.getByRole("textbox", { name: "Description", exact: true }).fill(`Description of ${title}\nSecond line.`);
  await form.getByRole("combobox", { name: "Task project", exact: true }).selectOption(project);
  if (parent) await form.getByRole("combobox", { name: "Parent task", exact: true }).selectOption({ label: parent });
  else await form.getByRole("combobox", { name: "Parent task", exact: true }).selectOption("");
  await form.getByRole("combobox", { name: "Initial status", exact: true }).selectOption({ label: status });
  await form.getByRole("button", { name: "Preview new task" }).click();
  await confirm(page);
}
const description = (page: Page) => page.getByRole("dialog", { name: "Task description", exact: true });
async function select(page: Page, title: string) {
  await page.getByRole("list", { name: /Task (list|tree)/ }).getByRole("button", { name: title, exact: true }).click();
  await expect(description(page).getByRole("heading", { name: title, exact: true })).toBeVisible();
}
async function status(page: Page, name: string) {
  const form = page.getByRole("form", { name: "Change status", exact: true });
  await form.getByRole("combobox", { name: "New status", exact: true }).selectOption({ label: name });
  await form.getByRole("button", { name: "Preview status change" }).click();
}

test("tasks can be created, edited, assigned, filtered, and browsed as a tree", async ({ page, browser }, testInfo) => {
  const f = await setup(browser, "workflow");
  try {
    await login(page, f.user.email);
    await create(page, "Root workflow", f.project.id);
    await create(page, "Child workflow", f.project.id, "Root workflow");
    await create(page, "Leaf workflow", f.project.id, "Child workflow", "Completed");
    await page.getByRole("button", { name: "Flat view", exact: true }).click();
    await expect(page.getByRole("list", { name: "Task tree", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Collapse Root workflow", exact: true }).click();
    await expect(page.getByRole("button", { name: "Leaf workflow", exact: true })).not.toBeVisible();
    await page.getByRole("button", { name: "Expand Root workflow", exact: true }).click();
    await select(page, "Leaf workflow");
    await expect(description(page)).toContainText("Second line.");
    const edit = page.getByRole("form", { name: "Edit task", exact: true });
    await edit.getByLabel("Task title", { exact: true }).fill("Renamed leaf");
    await edit.getByRole("textbox", { name: "Description", exact: true }).fill("Updated description");
    await edit.getByRole("button", { name: "Save task", exact: true }).click();
    await expect(description(page).getByRole("heading", { name: "Renamed leaf", exact: true })).toBeVisible();
    const owner = page.getByRole("form", { name: "Transfer ownership", exact: true });
    await owner.getByRole("combobox", { name: "New owner", exact: true }).selectOption(f.colleague.id);
    await owner.getByRole("button", { name: "Transfer ownership", exact: true }).click();
    await expect(description(page)).toContainText(`Owner: ${f.colleague.display_name}`);
    await page.getByRole("region", { name: "Tasks", exact: true }).getByRole("checkbox", { name: "Completed", exact: true }).check();
    await page.getByRole("region", { name: "Tasks", exact: true }).getByRole("checkbox", { name: "Postponed", exact: true }).check();
    await expect(page.getByText("1 matching tasks", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Root workflow", exact: true })).not.toBeVisible();
    await page.getByRole("combobox", { name: "Filter project", exact: true }).selectOption(f.other.id);
    await expect(page.getByText("0 matching tasks", { exact: true })).toBeVisible();
    await page.getByRole("combobox", { name: "Filter project", exact: true }).selectOption(f.project.id);
    await page.getByRole("region", { name: "Tasks", exact: true }).getByRole("checkbox", { name: "Completed", exact: true }).uncheck();
    await page.getByRole("region", { name: "Tasks", exact: true }).getByRole("checkbox", { name: "Postponed", exact: true }).uncheck();
    await page.screenshot({ path: testInfo.outputPath("task-workspace.png"), fullPage: true });
    await page.reload();
    await select(page, "Renamed leaf");
    await expect(description(page)).toContainText("Updated description");
    await expect(description(page)).toContainText(`Owner: ${f.colleague.display_name}`);
  } finally { await f.admin.close(); }
});

test("finalization is blocked until descendants finish and reopening previews all ancestors", async ({ page, browser }) => {
  const f = await setup(browser, "statuses");
  try {
    await login(page, f.user.email);
    await create(page, "Status root", f.project.id);
    await create(page, "Status child", f.project.id, "Status root");
    await create(page, "Status leaf", f.project.id, "Status child");
    await select(page, "Status root");
    await status(page, "Completed");
    await expect(page.getByRole("alert")).toContainText("Every descendant must be final");
    for (const title of ["Status leaf", "Status child", "Status root"]) {
      await select(page, title); await status(page, "Completed"); await confirm(page);
      await expect(description(page)).toContainText("In Progress → Completed");
    }
    await select(page, "Status leaf");
    await status(page, "In Progress");
    const preview = page.getByRole("dialog", { name: "Confirm task change", exact: true });
    for (const title of ["Status root", "Status child", "Status leaf"]) await expect(preview).toContainText(title);
    await preview.getByRole("button", { name: "Cancel change" }).click();
    await expect(description(page)).toContainText("Completed");
    await status(page, "In Progress"); await confirm(page);
    for (const title of ["Status root", "Status child", "Status leaf"]) {
      await select(page, title); await expect(description(page)).toContainText("Completed → In Progress");
    }
  } finally { await f.admin.close(); }
});

test("moves reject cycles, move complete subtrees, and deletion protects parents", async ({ page, browser }) => {
  const f = await setup(browser, "moves");
  try {
    await login(page, f.user.email);
    await create(page, "Move root", f.project.id);
    await create(page, "Move child", f.project.id, "Move root");
    await select(page, "Move root");
    await description(page).getByRole("button", { name: "Preview deletion" }).click();
    await expect(page.getByRole("alert")).toContainText("child tasks or recorded time");
    const form = page.getByRole("form", { name: "Move task", exact: true });
    await form.getByRole("combobox", { name: "New parent", exact: true }).selectOption({ label: `Move child (${f.project.name})` });
    await form.getByRole("button", { name: "Preview move" }).click();
    await expect(page.getByRole("alert")).toContainText("descendant");
    await form.getByRole("combobox", { name: "New parent", exact: true }).selectOption("");
    await form.getByRole("combobox", { name: "Destination project", exact: true }).selectOption(f.other.id);
    await form.getByRole("button", { name: "Preview move" }).click();
    await expect(page.getByRole("dialog", { name: "Confirm task change", exact: true })).toContainText("Move child");
    await confirm(page);
    await page.getByRole("combobox", { name: "Filter project", exact: true }).selectOption(f.other.id);
    await expect(page.getByText("2 matching tasks", { exact: true })).toBeVisible();
    await select(page, "Move child");
    await description(page).getByRole("button", { name: "Preview deletion" }).click(); await confirm(page);
    await expect(page.getByRole("button", { name: "Move child", exact: true })).not.toBeVisible();
    await select(page, "Move root");
    await description(page).getByRole("button", { name: "Preview deletion" }).click(); await confirm(page);
    await expect(page.getByText("0 matching tasks", { exact: true })).toBeVisible();
  } finally { await f.admin.close(); }
});

test("stale tabs and stale previews reject changes and require another review", async ({ page, browser }) => {
  const f = await setup(browser, "stale");
  const second = await browser.newContext();
  try {
    await login(page, f.user.email);
    await create(page, "Stale task", f.project.id);
    const other = await second.newPage(); await login(other, f.user.email); await select(other, "Stale task");
    await expect(description(page).getByRole("heading", { name: "Stale task", exact: true })).toBeVisible();
    const edit = page.getByRole("form", { name: "Edit task", exact: true });
    await edit.getByRole("textbox", { name: "Description", exact: true }).fill("First tab saved");
    await edit.getByRole("button", { name: "Save task", exact: true }).click();
    await expect(description(page)).toContainText("First tab saved");
    const stale = other.getByRole("form", { name: "Edit task", exact: true });
    await stale.getByRole("textbox", { name: "Description", exact: true }).fill("Must not overwrite");
    await stale.getByLabel("Add images", { exact: true }).setInputFiles("tests/fixtures/screenshot.png");
    await expect(stale.getByRole("status")).toContainText("1 new image");
    await stale.getByRole("button", { name: "Save task", exact: true }).click();
    await expect(other.getByRole("alert")).toContainText("The task changed");
    await expect(stale.getByRole("textbox", { name: "Description", exact: true })).toHaveValue(/Must not overwrite.*\[image:/);
    await expect(stale.getByRole("status")).toContainText("1 new image");
    await expect(stale.getByRole("button", { name: "Save task", exact: true })).toBeDisabled();
    await expect(other.getByText(/refreshing tasks discards unsaved task drafts and images/)).toBeVisible();
    await other.getByRole("button", { name: "Refresh tasks", exact: true }).click();
    await expect(description(other)).toContainText("First tab saved");
    await expect(stale.getByRole("textbox", { name: "Description", exact: true })).toHaveValue("First tab saved");
    await expect(stale.getByRole("button", { name: "Save task", exact: true })).toBeEnabled();
    await status(page, "Completed");
    await f.write("organizations/", { name: "Invalidate task preview" });
    const dialog = page.getByRole("dialog", { name: "Confirm task change", exact: true });
    await dialog.getByRole("button", { name: "Confirm change", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("preview is out of date");
    await expect(dialog).not.toBeVisible();
    await expect(description(page)).toContainText("Created as In Progress");
    await status(page, "Completed"); await confirm(page);
  } finally { await second.close(); await f.admin.close(); }
});

test("live revocation removes task content and write-only creation returns a safe acknowledgement", async ({ page, browser }) => {
  const f = await setup(browser, "permissions");
  try {
    await login(page, f.user.email);
    await create(page, "Restricted task title", f.project.id);
    await expect(description(page).getByRole("heading", { name: "Restricted task title", exact: true })).toBeVisible();
    await f.write(`users/${f.user.id}/grants/projects/${f.project.id}/`, { task_read: true }, "PUT");
    await page.getByRole("button", { name: "Refresh tasks", exact: true }).click();
    await expect(description(page).getByRole("heading", { name: "Restricted task title", exact: true })).toBeVisible();
    await expect(page.getByRole("form", { name: "Edit task", exact: true })).not.toBeVisible();
    await f.write(`users/${f.user.id}/grants/projects/${f.project.id}/`, { task_write: true }, "PUT");
    await page.getByRole("button", { name: "Refresh tasks", exact: true }).click();
    await expect(page.getByRole("button", { name: "Restricted task title", exact: true })).not.toBeVisible();
    await expect(description(page)).not.toBeVisible();
    await create(page, "Write-only new task", f.project.id);
    await expect(description(page)).not.toBeVisible();
    await expect(page.getByRole("list", { name: "Task list", exact: true })).not.toContainText("Write-only new task");
    await f.write(`users/${f.user.id}/grants/projects/${f.project.id}/`, {}, "PUT");
    const form = page.getByRole("form", { name: "Create task", exact: true });
    await form.getByLabel("Task title", { exact: true }).fill("Revoked creation");
    await form.getByRole("button", { name: "Preview new task" }).click();
    await expect(page.getByRole("alert")).toContainText("Task write access is required");
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await login(page, "admin@example.test", fixturePassword);
    await page.getByRole("navigation", { name: "Management" }).getByRole("button", { name: "Tasks", exact: true }).click();
    await expect(page.getByText("0 matching tasks", { exact: true })).toBeVisible();
    await expect(page.getByRole("form", { name: "Create task", exact: true })).not.toBeVisible();
  } finally { await f.admin.close(); }
});

test("status catalog permits unused changes and protects used statuses", async ({ page, browser }) => {
  const f = await setup(browser, "catalog");
  try {
    await login(page, f.user.email);
    await create(page, "Catalog task", f.project.id, undefined, "Completed");
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await login(page, "admin@example.test", fixturePassword);
    await page.getByRole("button", { name: "Statuses", exact: true }).click();
    const used = page.getByRole("form", { name: "Status Completed", exact: true });
    await expect(used.getByLabel("Status name", { exact: true })).toBeDisabled();
    await expect(used).toContainText("permanently protected");
    const createForm = page.getByRole("form", { name: "Create status", exact: true });
    await createForm.getByLabel("Status name", { exact: true }).fill("Unused browser status");
    await createForm.getByRole("button", { name: "Create status", exact: true }).click();
    const unused = page.getByRole("form", { name: "Status Unused browser status", exact: true });
    await unused.getByLabel("Status name", { exact: true }).fill("Renamed browser status");
    await unused.getByRole("checkbox", { name: "Final status", exact: true }).check();
    await unused.getByRole("button", { name: "Save status", exact: true }).click();
    const renamed = page.getByRole("form", { name: "Status Renamed browser status", exact: true });
    page.once("dialog", dialog => dialog.accept());
    await renamed.getByRole("button", { name: "Delete status", exact: true }).click();
    await expect(renamed).not.toBeVisible();
  } finally { await f.admin.close(); }
});

test("task forms support keyboard use, repeated submission protection, and failed-request recovery", async ({ page, browser }, testInfo) => {
  const f = await setup(browser, "recovery");
  try {
    await login(page, f.user.email);
    const form = page.getByRole("form", { name: "Create task", exact: true });
    await form.getByLabel("Task title", { exact: true }).focus();
    await page.keyboard.type("Keyboard task"); await page.keyboard.press("Tab");
    await expect(form.getByRole("textbox", { name: "Description", exact: true })).toBeFocused();
    await page.keyboard.type("Keyboard description");
    await form.getByRole("combobox", { name: "Task project", exact: true }).selectOption(f.project.id);
    await page.route("**/api/v1/tasks/preview/", route => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "unavailable", message: "Temporary failure. Try again." }) }));
    await form.getByRole("button", { name: "Preview new task" }).click();
    await expect(page.getByRole("alert")).toContainText("Temporary failure");
    await expect(form.getByLabel("Task title", { exact: true })).toHaveValue("Keyboard task");
    await page.unroute("**/api/v1/tasks/preview/");
    await form.getByRole("button", { name: "Preview new task" }).click();
    const button = page.getByRole("dialog", { name: "Confirm task change", exact: true }).getByRole("button", { name: "Confirm change", exact: true });
    await expect(page.getByRole("dialog", { name: "Confirm task change", exact: true })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(button).toBeFocused();
    await button.dblclick();
    await expect(page.getByRole("dialog", { name: "Confirm task change", exact: true })).not.toBeVisible();
    await expect(page.getByRole("list", { name: "Task list", exact: true }).getByRole("button", { name: "Keyboard task", exact: true })).toHaveCount(1);
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole("form", { name: "Create task", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath("tasks-narrow.png"), fullPage: true });
  } finally { await f.admin.close(); }
});
