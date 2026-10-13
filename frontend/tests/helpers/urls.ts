const configured = new URL(process.env.BASE_URL ?? 'http://frontend:5173/');
export const origin = configured.origin;
export const baseURL = configured.href.replace(/\/$/, '');
export const appURL = `${baseURL}/`;
export function absoluteUrl(path: string | null) {
  if (path === null) throw new Error('Expected an application URL.');
  return new URL(path, origin).href;
}
export const newTestContext = (browser: import('@playwright/test').Browser) =>
  browser.newContext({ ignoreHTTPSErrors: process.env.PREFIX_TESTS === 'true' });
