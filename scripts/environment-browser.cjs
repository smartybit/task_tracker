// Real deployment smoke check: no Vite server and no production/evaluation data.
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { readFileSync, writeFileSync, mkdirSync } = require('node:fs');
const { chromium } = require('/work/node_modules/playwright');

(async () => {
  const options = JSON.parse(readFileSync(0, 'utf8'));
  mkdirSync('/work/.artifacts', { recursive: true });
  const browser = await chromium.launch();
  const statePath = `/work/.artifacts/${options.label}-deployment-state.json`;
  const identitiesPath = `/work/.artifacts/${options.label}-deployment-identities.json`;
  const snapshot = readFileSync('/work/tests/fixtures/screenshot.png');
  const context = await browser.newContext(options.phase === 'after' ? { storageState: statePath } : {});
  context.setDefaultTimeout(15000);
  await context.tracing.start({ screenshots: true, snapshots: true });
  const url = (instance, path) => `${instance.url}api/v1/${path}`;
  const write = async (instance, token, path, data, method = 'POST') => {
    const response = await context.request.fetch(url(instance, path), {
      method, headers: { 'X-CSRFToken': token, Origin: new URL(instance.url).origin }, data,
    });
    assert.equal(response.ok(), true, await response.text());
    return response.json();
  };
  try {
    if (options.phase === 'before') {
      const identities = [];
      for (const [index, instance] of options.instances.entries()) {
        const origin = new URL(instance.url).origin;
        const mount = new URL(instance.url).pathname;
        const htmlResponse = await context.request.get(instance.url);
        assert.equal(htmlResponse.status(), 200);
        const html = await htmlResponse.text();
        assert.ok(html.includes('<title>Task Tracker</title>'));
        assert.ok(!html.includes('/@vite/'));
        for (const match of html.matchAll(/(?:src|href)="([^\"]+)"/g)) {
          if (!match[1].startsWith('/')) continue;
          assert.ok(match[1].startsWith(`${mount}assets/`));
          const asset = await context.request.get(`${origin}${match[1]}`);
          assert.equal(asset.status(), 200);
          assert.ok(asset.headers()['cache-control'].includes('immutable'));
        }
        const metadata = await (await context.request.get(`${instance.url}instance.json`)).json();
        assert.deepEqual(metadata, { basePath: mount, instanceId: instance.id });
        assert.equal((await context.request.get(instance.url, { headers: { Host: 'unexpected.invalid' } })).status(), 400);
        for (const path of [`${instance.url}assets/missing.js`, `${instance.url}src/main.tsx`,
                            `${instance.url}uploads/private.png`, `${origin}/api/v1/health/`, url(instance, 'missing/')]) {
          assert.equal((await context.request.get(path)).status(), 404);
        }
        const redirect = await context.request.get(`${instance.url.slice(0, -1)}?keep=yes`, { maxRedirects: 0 });
        assert.equal(redirect.status(), 308);
        assert.equal(redirect.headers().location, `${mount}?keep=yes`);
        const apiRedirect = await context.request.get(url(instance, 'health?keep=yes'), { maxRedirects: 0 });
        assert.equal(apiRedirect.status(), 301);
        assert.equal(apiRedirect.headers().location, `${mount}api/v1/health/?keep=yes`);
        const token = (await (await context.request.get(url(instance, 'auth/csrf/'))).json()).csrf_token;
        const denied = await context.request.post(url(instance, 'auth/login/'), {
          headers: { 'X-CSRFToken': token, Origin: 'http://unexpected.invalid' },
          data: { email: instance.email, password: instance.password },
        });
        assert.equal(denied.status(), 403);
        // With no Origin or Referer, forged HTTPS forwarding would make Django
        // require a secure Referer. Our frontend must overwrite that header.
        const signedIn = await context.request.post(url(instance, 'auth/login/'), {
          headers: { 'X-CSRFToken': token, 'X-Forwarded-Proto': 'https' },
          data: { email: instance.email, password: instance.password },
        });
        assert.equal(signedIn.status(), 200, await signedIn.text());
        const login = await signedIn.json();
        const csrf = login.csrf_token;
        const organization = await write(instance, csrf, 'organizations/', { name: `Deployment ${index}` });
        const project = await write(instance, csrf, 'projects/', { name: `Private project ${index}`, organization: organization.id });
        await write(instance, csrf, `users/${login.user.id}/grants/projects/${project.id}/`, {
          task_read: true, task_write: true, remark_read: true, remark_write: true,
        }, 'PUT');
        const statuses = (await (await context.request.get(url(instance, 'statuses/'))).json()).results;
        const image = randomUUID();
        const title = `Deployment private work ${index}`;
        const payload = { title, project: project.id, status: statuses.find(status => status.name === 'In Progress').id,
          description: `Private image [image:${image}]`, images: [{ id: image, data: snapshot.toString('base64') }] };
        const preview = await write(instance, csrf, 'tasks/preview/', payload);
        const task = await write(instance, csrf, 'tasks/', { ...payload, confirm: true, expected_domain_revision: preview.domain_revision });
        await write(instance, csrf, `tasks/${task.id}/remarks/`, { body: `Deployment remark ${index} [task:${task.id}]` });
        const dayPath = `timesheets/${login.user.id}/days/2020-10-09/`;
        let day = await (await context.request.get(url(instance, dayPath))).json();
        await write(instance, csrf, `timesheets/${login.user.id}/commands/`, {
          command: 'start', date: '2020-10-09', at: '2020-10-09T09:00:00Z', task: task.id, expected_revision: day.revision,
        });
        day = await (await context.request.get(url(instance, dayPath))).json();
        await write(instance, csrf, `timesheets/${login.user.id}/commands/`, {
          command: 'end_day', date: '2020-10-09', at: `2020-10-09T${String(10 + index).padStart(2, '0')}:00:00Z`,
          session: day.sessions.at(-1).id, expected_revision: day.revision,
        });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(String(error)));
        await page.goto(instance.url);
        await page.getByText('Signed in as', { exact: false }).waitFor();
        await page.getByRole('button', { name: 'Tasks', exact: true }).click();
        await page.getByRole('list', { name: 'Task list', exact: true }).getByRole('button', { name: title, exact: true }).click();
        const attached = page.getByRole('img', { name: 'Attached image', exact: true });
        await attached.scrollIntoViewIfNeeded();
        await page.waitForFunction(image => image.complete && image.naturalWidth === 128, await attached.elementHandle());
        await page.reload();
        await page.getByRole('button', { name: 'Close details', exact: true }).click();
        await page.getByRole('button', { name: 'Reports', exact: true }).click();
        const reports = page.getByRole('region', { name: 'Reports', exact: true });
        await reports.getByRole('table').waitFor();
        await reports.getByLabel('From date', { exact: true }).fill('2020-10-09');
        await reports.getByLabel('To date', { exact: true }).fill('2020-10-09');
        await page.waitForFunction(expected => document.body.textContent.includes(`Total recorded work: ${expected}.00`), index + 1);
        const download = page.waitForEvent('download');
        await reports.getByRole('button', { name: 'Download CSV', exact: true }).click();
        assert.ok(readFileSync(await (await download).path(), 'utf8').includes(title));
        assert.deepEqual(errors, []);
        await page.screenshot({ path: `/work/.artifacts/${options.label}-deployment-${index}.png`, fullPage: true });
        await page.close();
        identities.push({ task: task.id, image, title, user: login.user.id });
      }
      for (const [index, instance] of options.instances.entries()) {
        const cookies = await context.cookies(instance.url);
        for (const suffix of ['session', 'csrf']) {
          const cookie = cookies.find(cookie => cookie.name === `task_tracker_${instance.id}_${suffix}`);
          assert.ok(cookie);
          assert.equal(cookie.path, new URL(instance.url).pathname);
          assert.equal(cookie.secure, false);
          if (suffix === 'session') assert.equal(cookie.httpOnly, true);
        }
        const other = identities[(index + 1) % identities.length];
        assert.equal((await context.request.get(url(instance, `tasks/${other.task}/`))).status(), 404);
        assert.equal((await context.request.get(url(instance, `images/${other.image}/`))).status(), 404);
      }
      mkdirSync('/work/.artifacts', { recursive: true });
      writeFileSync(identitiesPath, JSON.stringify(identities));
      await context.storageState({ path: statePath });
      console.log('Three static/Gunicorn environments: assets, routing, host/CSRF, same-browser sessions, private images, distinct data/totals and actual CSV downloads passed.');
    } else {
      const identities = JSON.parse(readFileSync(identitiesPath, 'utf8'));
      for (const [index, instance] of options.instances.entries()) {
        const task = await context.request.get(url(instance, `tasks/${identities[index].task}/`));
        assert.equal(task.status(), 200);
        assert.equal((await task.json()).title, identities[index].title);
        assert.deepEqual(await (await context.request.get(url(instance, `images/${identities[index].image}/`))).body(), snapshot);
        const report = await (await context.request.get(url(instance, 'reports/projects/?from=2020-10-09&to=2020-10-09'))).json();
        assert.equal(report.total_hours, `${index + 1}.00`);
      }
      console.log('Existing sessions, data, private images and independent totals survived targeted agent replacement/restart.');
    }
  } catch (error) {
    for (const [index, page] of context.pages().entries()) {
      await page.screenshot({ path: `/work/.artifacts/${options.label}-${options.phase}-failure-${index}.png`, fullPage: true }).catch(() => {});
      console.error('Failed page:', page.url());
      console.error(await page.getByRole('region', { name: 'Reports', exact: true }).innerText().catch(() => 'Report region not available.'));
    }
    await context.tracing.stop({ path: `/work/.artifacts/${options.label}-${options.phase}-failure.zip` });
    throw error;
  } finally {
    await context.tracing.stop().catch(() => {});
    await context.close();
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
