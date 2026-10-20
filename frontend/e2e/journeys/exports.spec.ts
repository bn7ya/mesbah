import { readFileSync } from 'node:fs';

import type { Locator, Page } from '@playwright/test';

import { rows } from '../harness/api';
import { expect, test } from '../harness/fixtures';
import type { Copy } from '../harness/copy.types';
import { numbered, slugOf, versionTitle, versionsOf } from '../harness/versions';

const OFFLINE_GGUF_FAILURES: readonly string[] = ['training_parts_missing', 'converter_unavailable'];

async function startExport(page: Page, t: Copy, title: string, format: 'lora' | 'gguf'): Promise<Locator> {
  await page.getByRole('button', { name: t('versions', 'versions.row.actionsFor', { name: title }) }).click();
  await page.getByRole('menuitem', { name: t('versions', 'versions.menu.export') }).click();
  const dialog = page.getByRole('dialog', { name: t('versions', 'versions.export.title', { name: title }) });
  await dialog.getByRole('radio', { name: t('versions', `versions.export.${format}.name`) }).check();
  await dialog.getByRole('button', { name: t('versions', 'versions.export.start') }).click();
  await expect(dialog).toHaveCount(0);

  const exports = page.getByRole('dialog', { name: t('versions', 'versions.exports.title', { name: title }) });
  return exports
    .getByRole('list', { name: t('versions', 'versions.exports.list') })
    .getByRole('listitem')
    .filter({ has: page.getByRole('heading', { name: t('versions', `versions.export.${format}.name`) }) })
    .first();
}

test('v1 exported as a LoRA adapter becomes ready and downloads as a zip', async ({
  page,
  owner,
  world,
  locale,
  t,
  shot,
}) => {
  const project = world.projects[locale].exports;
  const first = numbered(await versionsOf(owner, project), 1);
  const title = versionTitle(first, locale);
  const slug = await slugOf(owner, project);

  await page.goto(`/projects/${project}/versions`);
  const newest = await startExport(page, t, title, 'lora');

  await expect(page.getByText(t('versions', 'versions.export.started'))).toBeVisible();
  await expect(newest.getByRole('status')).toHaveText(t('versions', 'versions.exports.status.ready'), {
    timeout: 60_000,
  });
  await shot('lora export ready');

  const downloading = page.waitForEvent('download');
  await newest.getByRole('link', { name: t('versions', 'versions.exports.download') }).click();
  const download = await downloading;

  expect(download.suggestedFilename()).toBe(`${slug}-v1-lora.zip`);
  const zip = readFileSync(await download.path());
  expect(zip.length).toBeGreaterThan(0);
  expect(zip.subarray(0, 2).toString('latin1')).toBe('PK');
});

test('a GGUF export that cannot be made here fails and says why', async ({ page, owner, world, locale, t, shot }) => {
  const project = world.projects[locale].exports;
  const first = numbered(await versionsOf(owner, project), 1);
  const title = versionTitle(first, locale);

  await page.goto(`/projects/${project}/versions`);
  const newest = await startExport(page, t, title, 'gguf');

  await expect(newest.getByRole('status')).toHaveText(t('versions', 'versions.exports.status.failed'), {
    timeout: 60_000,
  });
  const failed = rows(await owner.get(`/api/versions/${first.id}/exports/`)).find(
    (row) => row['format'] === 'gguf' && row['status'] === 'failed',
  );
  const code = String(failed?.['error_code']);
  expect(OFFLINE_GGUF_FAILURES).toContain(code);
  await expect(newest.getByText(t('versions', `versions.exports.failure.${code}`))).toBeVisible();
  await expect(newest.getByRole('link', { name: t('versions', 'versions.exports.download') })).toHaveCount(0);
  await shot('gguf export failed');
});
