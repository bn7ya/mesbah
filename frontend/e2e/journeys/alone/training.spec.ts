import { field } from '../../harness/api';
import { anyValues, stamp, startsWith } from '../../harness/copy';
import { expect, test } from '../../harness/fixtures';
import { createProject } from '../../harness/seed';

test('a run started from the Training tab is watched live and becomes the active version', async ({
  page,
  owner,
  world,
  locale,
  t,
  shot,
}) => {
  test.slow();
  const name = `${locale === 'en' ? 'Training journey' : 'رحلة تدريب'} ${stamp()}`;
  const project = await createProject(owner, name, world.baseModel);
  const dataset = field(await owner.get(`/api/datasets/${world.dataset}/`), 'name');
  await page.goto(`/projects/${project}/training`);

  await expect(page.getByRole('heading', { name: t('training', 'training.form.title') })).toBeVisible();
  await expect(page.getByRole('list', { name: t('training', 'training.runs.list') }).getByRole('listitem')).toHaveCount(0);
  await page.getByRole('combobox', { name: t('training', 'training.form.datasets.label') }).click();
  await page.getByRole('option', { name: startsWith(dataset) }).click();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('list', { name: t('training', 'training.form.datasets.chosen') })).toContainText(dataset);
  await expect(page.getByRole('switch', { name: t('training', 'training.form.activate') })).toBeChecked();
  await shot('new run');
  await page.getByRole('button', { name: t('training', 'training.form.start') }).click();

  await expect(page).toHaveURL(new RegExp(`/projects/${project}/training/[0-9a-f-]{36}$`));
  const status = page.locator('app-run-status').first();
  const seen = new Set<string>();
  await expect(status).toBeVisible();
  await expect
    .poll(
      async () => {
        const now = (await status.innerText()).trim();
        seen.add(now);
        return now;
      },
      { timeout: 90_000, intervals: [100, 250, 500] },
    )
    .toMatch(t('training', 'training.status.completed'));
  test.info().annotations.push({ type: 'stages seen', description: [...seen].join(' → ') });
  expect(seen.size, 'a stage in words before the result').toBeGreaterThan(1);

  await expect(page.getByRole('img', { name: anyValues('training', locale, 'training.loss.done.too_early') })).toBeVisible();
  await expect(page.getByText(t('training', 'training.result.done'))).toBeVisible();
  await expect(page.getByText(t('training', 'training.result.activeYes'))).toBeVisible();
  await expect(page.getByText(t('training', 'training.result.loss'))).toBeVisible();
  await expect(page.getByRole('progressbar', { name: t('training', 'training.runs.progress') })).toHaveAttribute('aria-valuenow', '100');
  await shot('finished run');

  await page.getByRole('tab', { name: t('projects', 'projects.tabs.versions') }).click();
  const active = page.locator('app-version-row').filter({ has: page.getByText(t('versions', 'versions.active')) });
  await expect(active).toHaveCount(1);
  await expect(active.getByText('v1', { exact: true }).first()).toBeVisible();
  await shot('versions');
  expect(await owner.get(`/api/projects/${project}/`)).toMatchObject({ active_version: { number: 1 } });
});
