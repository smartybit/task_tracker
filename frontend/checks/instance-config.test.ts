import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildApiUrl, instanceConfig } from '../instance-config.ts';

test('root, sibling and nested instance mounts produce bounded API paths', () => {
  for (const base of ['/', '/time-tracker-test', '/time-tracker-prod/', '/team/work/']) {
    const config = instanceConfig({ APP_BASE_PATH: base, INSTANCE_ID: 'prefix-test' });
    assert.equal(config.basePath, base.endsWith('/') ? base : `${base}/`);
    assert.equal(buildApiUrl(config.basePath, 'search/?q=English%20русский&page=2'),
      `${config.basePath}api/v1/search/?q=English%20русский&page=2`);
  }
  assert.deepEqual(instanceConfig({}), { basePath: '/', instanceId: 'task-tracker-dev' });
});

test('invalid mounts, identifiers and endpoint escapes fail before requests', () => {
  for (const path of ['', 'relative/', '//other/', '/a//b', '/./', '/../', '/a\\b', '/a%2fb', '/a?b', '/a#b', '/a b', '/a/\n', 'https://other/']) {
    assert.throws(() => instanceConfig({ APP_BASE_PATH: path }), /APP_BASE_PATH/);
  }
  for (const id of ['', '-leading', 'Upper', 'a_b', 'a'.repeat(64), 'a\n']) {
    assert.throws(() => instanceConfig({ INSTANCE_ID: id }), /INSTANCE_ID/);
  }
  for (const endpoint of ['', '/auth/me/', '//other/', 'https://other/', '../auth/', 'a/../b', 'a//b', 'a#b', 'a%2fb']) {
    assert.throws(() => buildApiUrl('/test/', endpoint), /relative paths/);
  }
});
