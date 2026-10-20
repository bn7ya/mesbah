import { literal, stamp, text } from '../harness/copy';
import { expect, test } from '../harness/fixtures';
import { repoOf } from '../harness/versions';

const NAMES = {
  en: { made: 'Support replies', renamed: 'Support replies, renamed' },
  ar: { made: 'ردود الدعم', renamed: 'ردود الدعم بعد التغيير' },
} as const;

test('a project is started on the base model, renamed and removed', async ({ page, t, locale, owner, world, shot }) => {
  const repo = await repoOf(owner, world.baseModel);
  const made = `${NAMES[locale].made} ${stamp()}`;
  const renamed = `${NAMES[locale].renamed} ${stamp()}`;
  await page.goto('/projects');
  await expect(page.getByRole('heading', { level: 1, name: t('projects', 'projects.title') })).toBeVisible();

  await page.getByRole('button', { name: t('projects', 'projects.new.open') }).click();
  const dialog = page.getByRole('dialog', { name: t('projects', 'projects.new.title') });
  await dialog.getByLabel(t('projects', 'projects.new.name')).fill(made);
  await dialog.getByRole('combobox', { name: t('projects', 'projects.new.model') }).click();
  await page.getByRole('option', { name: literal(repo) }).click();
  await expect(dialog.getByRole('combobox', { name: t('projects', 'projects.new.model') })).toContainText(repo);
  await shot('new project');
  await dialog.getByRole('button', { name: t('projects', 'projects.new.submit') }).click();

  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]{36}$/);
  const id = page.url().split('/').pop() ?? '';
  await expect(page.getByRole('heading', { level: 1, name: made })).toBeVisible();
  const about = page.getByRole('region', { name: t('projects', 'projects.overview.about.title') });
  await expect(about.getByText(repo, { exact: true })).toBeVisible();
  const active = page.getByText(t('projects', 'projects.activeVersion')).locator('..');
  await expect(active).toContainText('v0');
  await expect(active).toContainText(text('core', locale, 'version.baseName'));
  await shot('overview of the new project');

  await about.getByLabel(t('projects', 'projects.overview.about.name')).fill(renamed);
  await about.getByRole('button', { name: t('core', 'actions.save') }).click();
  await expect(page.getByText(t('projects', 'projects.overview.saved'))).toBeVisible();
  await expect(page.getByRole('heading', { level: 1, name: renamed })).toBeVisible();

  const removal = page.getByRole('region', { name: t('projects', 'projects.overview.remove.title') });
  const asking = page.getByRole('dialog', { name: t('projects', 'projects.overview.remove.confirmTitle', { name: renamed }) });
  await removal.getByRole('button', { name: t('projects', 'projects.overview.remove.open') }).click();
  await asking.getByRole('button', { name: t('core', 'actions.cancel') }).click();
  await expect(asking).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1, name: renamed })).toBeVisible();
  await removal.getByRole('button', { name: t('projects', 'projects.overview.remove.open') }).click();
  await expect(asking).toBeVisible();
  await shot('asked before removing');
  await asking.getByRole('button', { name: t('projects', 'projects.overview.remove.confirm') }).click();

  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByText(t('projects', 'projects.overview.remove.done'))).toBeVisible();
  await expect(page.getByRole('heading', { level: 2 }).first()).toBeVisible();
  await expect(page.getByRole('heading', { level: 2, name: renamed })).toHaveCount(0);
  expect((await owner.send('GET', `/api/projects/${id}/`)).status()).toBe(404);
});
