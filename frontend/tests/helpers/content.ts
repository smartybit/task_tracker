import { expect, type APIRequestContext, type Browser, type Page } from "@playwright/test";

import { baseURL, origin, appURL, newTestContext } from "./urls";
export { baseURL } from "./urls";
const password = "browser-stage-eight-long-password";
export const flags = { task_read: true, task_write: true, remark_read: true, remark_write: true };

export async function login(page: Page, email: string) {
  await page.goto(appURL);
  const form = page.getByRole("form", { name: "Sign in", exact: true });
  await form.getByLabel("Email", { exact: true }).fill(email);
  await form.getByLabel("Password", { exact: true }).fill(password);
  await form.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Signed in as", { exact: false })).toBeVisible();
}

async function apiLogin(request: APIRequestContext, email: string, secret: string) {
  const csrf = await (await request.get(`${baseURL}/api/v1/auth/csrf/`)).json();
  const response = await request.post(`${baseURL}/api/v1/auth/login/`, {
    headers: { "X-CSRFToken": csrf.csrf_token, Origin: origin }, data: { email, password: secret },
  });
  expect(response.status()).toBe(200);
  return (await response.json()).csrf_token as string;
}

export async function setup(browser: Browser, name: string) {
  const key = `${name}-${Date.now()}`;
  const admin = await newTestContext(browser);
  const token = await apiLogin(admin.request, "admin@example.test", "synthetic-test-only-password");
  async function write(path: string, data: unknown, method = "POST") {
    const response = await admin.request.fetch(`${baseURL}/api/v1/${path}`, {
      method, headers: { "X-CSRFToken": token, Origin: origin }, data,
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
  for (const user of users) await write(`users/${user.id}/grants/projects/${project.id}/`, flags, "PUT");
  const content = await newTestContext(browser);
  const contentToken = await apiLogin(content.request, users[1].email, password);
  async function contentWrite(path: string, data: unknown, method = "POST") {
    const response = await content.request.fetch(`${baseURL}/api/v1/${path}`, {
      method, headers: { "X-CSRFToken": contentToken, Origin: origin }, data,
    });
    expect(response.ok()).toBeTruthy();
    return response.json();
  }
  const statuses = await (await content.request.get(`${baseURL}/api/v1/statuses/`)).json();
  const payload = { title: `Discussion ${name}`, description: "Task with remarks", project: project.id,
    status: statuses.results.find((row: { name: string }) => row.name === "In Progress").id };
  const preview = await contentWrite("tasks/preview/", payload);
  const task = await contentWrite("tasks/", { ...payload, confirm: true, expected_domain_revision: preview.domain_revision });
  return { admin, content, write, contentWrite, alice: users[0], bob: users[1], project, task };
}

