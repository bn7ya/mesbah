import type { Route } from '@playwright/test';

import { startConversation } from '../harness/chat';
import { anyValues, contains, stamp } from '../harness/copy';
import { expect, test } from '../harness/fixtures';

const PROJECT_LIST = /\/api\/projects\/\?/;

test.describe('a list that cannot load', () => {
  test.use({ allowConsoleErrors: true });

  for (const [failure, answer, key] of [
    ['500', (route: Route) => route.fulfill({ status: 500, body: 'Internal Server Error' }), 'errors.generic'],
    ['503', (route: Route) => route.fulfill({ status: 503, body: 'Service Unavailable' }), 'errors.generic'],
    ['a dropped connection', (route: Route) => route.abort('connectionreset'), 'auth.errors.unavailable'],
  ] as const) {
    test(`says so after ${failure} and loads again with Try again`, async ({ page, t, locale, shot }) => {
      await page.route(PROJECT_LIST, answer);
      await page.goto('/projects');
      const retry = page.getByRole('button', { name: t('core', 'actions.retry') });

      await expect(page.getByText(t('core', key))).toBeVisible();
      await expect(retry).toBeVisible();
      await expect(page.getByRole('link', { name: anyValues('projects', locale, 'projects.openFor') })).toHaveCount(0);
      await shot(`projects after ${failure}`);
      await page.unroute(PROJECT_LIST);
      await retry.click();

      await expect(page.getByRole('link', { name: anyValues('projects', locale, 'projects.openFor') }).first()).toBeVisible();
      await expect(page.getByText(t('core', key))).toHaveCount(0);
      await expect(retry).toHaveCount(0);
    });
  }
});

test.describe('a session the server no longer accepts', () => {
  test.use({ allowConsoleErrors: true });

  test('sends the visitor to sign in when the account check answers 401', async ({ page, t }) => {
    await page.route('**/api/auth/me/', (route) => route.fulfill({ status: 401, json: { error: { code: 'not_authenticated', message: 'Sign in.' } } }));
    await page.goto('/projects');

    await expect(page).toHaveURL(/\/sign-in/);
    await expect(page.getByRole('heading', { level: 1, name: t('core', 'auth.signIn.title') })).toBeVisible();
  });

  test('sends the visitor to sign in when a list answers 401', async ({ page, t, shot }) => {
    await page.route(PROJECT_LIST, (route) => route.fulfill({ status: 401, json: { error: { code: 'not_authenticated', message: 'Sign in.' } } }));
    await page.goto('/projects');

    await expect(page).toHaveURL(/\/sign-in/);
    await expect(page.getByRole('heading', { level: 1, name: t('core', 'auth.signIn.title') })).toBeVisible();
    await shot('sent to sign in');
  });
});

test('a reply the model breaks off says why, from the chat bundle', async ({ page, owner, world, locale, t, shot }) => {
  const project = world.projects[locale].chat;
  const conversation = await startConversation(owner, project, `Failure ${stamp()}`);
  await page.goto(`/projects/${project}/chat/${conversation}`);
  const composer = page.getByRole('textbox', { name: t('chat', 'chat.composer.label') });
  const reply = page.getByRole('article', { name: t('chat', 'chat.sender.model') });

  await expect(composer).toBeEnabled();
  await composer.fill('Please [fail] now');
  await composer.press('Enter');

  await expect(reply).toContainText(contains('chat', locale, 'errors.generation_failed'), { timeout: 30_000 });
  await expect(reply).toContainText(contains('chat', locale, 'chat.marks.failed'));
  await expect(page.getByRole('button', { name: t('chat', 'chat.composer.send') })).toBeVisible();
  await shot('failed reply');
  await owner.delete(`/api/chat/${conversation}/`);
});
