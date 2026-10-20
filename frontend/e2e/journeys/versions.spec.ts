import type { Locator, Page } from '@playwright/test';

import { rows } from '../harness/api';
import { anyValues } from '../harness/copy';
import type { Copy } from '../harness/copy.types';
import { expect, test } from '../harness/fixtures';
import { numbered, versionTitle, versionsOf } from '../harness/versions';

function cardOf(page: Page, t: Copy, title: string): Locator {
  return page
    .locator('mat-card')
    .filter({ has: page.getByRole('button', { name: t('versions', 'versions.row.actionsFor', { name: title }) }) });
}

test('the tree shows each version with its size, and the version made active answers the chat', async ({
  page,
  owner,
  world,
  locale,
  t,
  shot,
}) => {
  const project = world.projects[locale].versions;
  const before = await versionsOf(owner, project);
  const [root, first, second] = [0, 1, 2].map((number) => numbered(before, number));
  if (first.isActive) {
    await owner.post(`/api/versions/${second.id}/activate/`);
  }
  const [rootTitle, firstTitle, secondTitle] = [root, first, second].map((version) => versionTitle(version, locale));
  const active = t('versions', 'versions.active');

  await page.goto(`/projects/${project}/versions`);

  const tree = page.getByRole('list', { name: t('versions', 'versions.tree') });
  await expect(cardOf(page, t, rootTitle)).toBeVisible();
  await expect(cardOf(page, t, rootTitle).getByText(anyValues('versions', locale, 'versions.size.root'))).toBeVisible();
  for (const title of [firstTitle, secondTitle]) {
    await expect(
      cardOf(page, t, title).getByText(anyValues('versions', locale, 'versions.size.change', 'versions.size.sliver')),
    ).toBeVisible();
  }
  const firstBranch = tree
    .getByRole('listitem')
    .filter({ has: page.getByRole('button', { name: t('versions', 'versions.row.actionsFor', { name: firstTitle }) }) })
    .filter({ hasNot: page.getByRole('button', { name: t('versions', 'versions.row.actionsFor', { name: rootTitle }) }) });
  await expect(firstBranch).toHaveCount(1);
  await expect(
    firstBranch.getByRole('button', { name: t('versions', 'versions.row.actionsFor', { name: secondTitle }) }),
  ).toBeVisible();
  await expect(cardOf(page, t, secondTitle).getByText(active)).toBeVisible();
  await expect(cardOf(page, t, firstTitle).getByText(active)).toHaveCount(0);
  await shot('version tree');

  await page.getByRole('button', { name: t('versions', 'versions.row.actionsFor', { name: firstTitle }) }).click();
  await page.getByRole('menuitem', { name: t('versions', 'versions.menu.activate') }).click();

  await expect(page.getByText(t('versions', 'versions.activated', { name: firstTitle }))).toBeVisible();
  await expect(cardOf(page, t, firstTitle).getByText(active)).toBeVisible();
  await expect(cardOf(page, t, secondTitle).getByText(active)).toHaveCount(0);
  await shot('v1 made active');

  const question = `Which version answers in ${locale}?`;
  await page.getByRole('tab', { name: t('projects', 'projects.tabs.chat') }).click();
  await page.getByRole('button', { name: t('chat', 'chat.list.new') }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${project}/chat/[0-9a-f-]{36}$`));
  const composer = page.getByRole('textbox', { name: t('chat', 'chat.composer.label') });
  await composer.fill(question);
  await composer.press('Enter');

  const reply = page.getByRole('article', { name: t('chat', 'chat.sender.model') });
  await expect(reply).toContainText(`Reply from ${first.id}: ${question}`, { timeout: 30_000 });
  await expect(reply.getByText('v1', { exact: true }).first()).toBeVisible();
  await shot('reply from v1');
});

test('what changed in v2 is drawn as a map of its layers and modules', async ({ page, owner, world, locale, t, shot }) => {
  const project = world.projects[locale].versions;
  const second = numbered(await versionsOf(owner, project), 2);
  const title = versionTitle(second, locale);
  const changes = await owner.get(`/api/versions/${second.id}/changes/`);
  const layers = rows(changes, 'layers').length;
  const modules = Array.isArray(changes['modules']) ? changes['modules'].length : 0;
  expect(layers * modules).toBeGreaterThan(0);

  await page.goto(`/projects/${project}/versions`);
  await page.getByRole('button', { name: t('versions', 'versions.row.actionsFor', { name: title }) }).click();
  await page.getByRole('menuitem', { name: t('versions', 'versions.menu.changes') }).click();

  const dialog = page.getByRole('dialog', { name: t('versions', 'versions.changes.title', { name: title }) });
  const map = dialog.getByRole('table', { name: t('versions', 'versions.changes.caption') });
  await expect(map).toBeVisible();
  await expect(map.getByRole('rowheader')).toHaveCount(layers);
  await expect(map.getByRole('cell', { name: anyValues('versions', locale, 'versions.changes.cell') })).toHaveCount(
    layers * modules,
  );
  await expect(dialog.getByRole('heading', { name: t('versions', 'versions.changes.mapTitle') })).toBeVisible();
  await shot('change map');

  await dialog.getByRole('button', { name: t('versions', 'versions.close') }).click();
  await expect(dialog).toHaveCount(0);
});
