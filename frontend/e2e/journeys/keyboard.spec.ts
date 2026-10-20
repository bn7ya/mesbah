import type { Page } from '@playwright/test';

import { startConversation } from '../harness/chat';
import { anyValues, stamp, startsWith } from '../harness/copy';
import { expect, test } from '../harness/fixtures';

async function focusInDialog(page: Page): Promise<boolean> {
  return page.evaluate(() => (document.activeElement?.closest('mat-dialog-container') ?? null) !== null);
}

test('the skip link moves focus to the page content', async ({ page, t }) => {
  await page.goto('/projects');
  await expect(page.getByRole('heading', { level: 1, name: t('projects', 'projects.title') })).toBeVisible();

  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: t('core', 'app.skipToContent') })).toBeFocused();
  await page.keyboard.press('Enter');

  await expect(page.locator('main#main')).toBeFocused();
  await expect(page).toHaveURL(/\/projects$/);
});

test('the account menu opens with Enter, keeps arrows inside and closes with Escape', async ({ page, world, t, shot }) => {
  await page.goto('/projects');
  const account = page.getByRole('button', { name: world.users.owner, exact: true });
  const signOut = page.getByRole('menuitem', { name: t('core', 'auth.signOut') });

  await account.focus();
  await page.keyboard.press('Enter');
  await expect(signOut).toBeFocused();
  await shot('account menu');
  await page.keyboard.press('ArrowDown');
  await expect(signOut).toBeFocused();
  await page.keyboard.press('Escape');

  await expect(page.getByRole('menu')).toHaveCount(0);
  await expect(account).toBeFocused();
  await expect(page).toHaveURL(/\/projects$/);
});

test('a version menu moves between its items with the arrow keys', async ({ page, world, locale, t }) => {
  await page.goto(`/projects/${world.projects[locale].versions}/versions`);
  const actions = page.getByRole('button', { name: anyValues('versions', locale, 'versions.row.actionsFor') }).first();
  const menu = page.getByRole('menu');

  await actions.focus();
  await page.keyboard.press('Enter');
  await expect(menu.getByRole('menuitem', { name: t('versions', 'versions.menu.activate') })).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(menu.getByRole('menuitem', { name: t('versions', 'versions.menu.rename') })).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(menu.getByRole('menuitem', { name: t('versions', 'versions.menu.changes') })).toBeFocused();
  await page.keyboard.press('ArrowUp');
  await expect(menu.getByRole('menuitem', { name: t('versions', 'versions.menu.rename') })).toBeFocused();
  // Escape on Make active would close its tooltip first, so the menu is closed from Rename.
  await page.keyboard.press('Escape');

  await expect(menu).toHaveCount(0);
  await expect(actions).toBeFocused();
});

test('a question in a dialog keeps focus inside it and closes with Escape', async ({ page, owner, world, locale, t, shot }) => {
  const project = world.projects[locale].chat;
  const title = `Keyboard ${stamp()}`;
  const conversation = await startConversation(owner, project, title);
  await page.goto(`/projects/${project}/chat`);
  const remove = page.getByRole('button', { name: t('chat', 'chat.list.remove', { title }) });
  const dialog = page.getByRole('dialog');

  await remove.focus();
  await page.keyboard.press('Enter');
  await expect(dialog.getByRole('heading', { name: t('chat', 'chat.remove.title', { title }) })).toBeVisible();
  await expect.poll(() => focusInDialog(page)).toBe(true);
  await shot('remove question');
  for (let step = 0; step < 4; step += 1) {
    await page.keyboard.press('Tab');
    expect(await focusInDialog(page), `focus after Tab ${step + 1}`).toBe(true);
  }
  await page.keyboard.press('Shift+Tab');
  expect(await focusInDialog(page), 'focus after Shift+Tab').toBe(true);
  await page.keyboard.press('Escape');

  await expect(dialog).toHaveCount(0);
  await expect(remove).toBeFocused();
  await expect(page.getByRole('link', { name: startsWith(title) })).toBeVisible();
  await owner.delete(`/api/chat/${conversation}/`);
});

test('in chat, Enter sends and Shift with Enter adds a line', async ({ page, owner, world, locale, t, shot }) => {
  const project = world.projects[locale].chat;
  const conversation = await startConversation(owner, project, `Composer ${stamp()}`);
  await page.goto(`/projects/${project}/chat/${conversation}`);
  const composer = page.getByRole('textbox', { name: t('chat', 'chat.composer.label') });

  await expect(composer).toBeEnabled();
  await composer.click();
  await page.keyboard.type('First line');
  await page.keyboard.press('Shift+Enter');
  await page.keyboard.type('second line');
  await expect(composer).toHaveValue('First line\nsecond line');
  await expect(page.getByRole('article', { name: t('chat', 'chat.sender.you') })).toHaveCount(0);
  await page.keyboard.press('Enter');

  await expect(composer).toHaveValue('');
  await expect(page.getByRole('article', { name: t('chat', 'chat.sender.you') })).toContainText('First line\nsecond line');
  await expect(page.getByRole('article', { name: t('chat', 'chat.sender.model') })).toContainText(
    'Reply from base: First line',
    { timeout: 30_000 },
  );
  await expect(page.getByRole('button', { name: t('chat', 'chat.composer.send') })).toBeVisible();
  await shot('sent with the keyboard');
  await owner.delete(`/api/chat/${conversation}/`);
});
