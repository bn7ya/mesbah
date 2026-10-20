import type { Locator } from '@playwright/test';

import { stamp, text } from '../harness/copy';
import { expect, test } from '../harness/fixtures';
import { pickFile } from '../harness/pages';
import { CHAT_ROWS, jsonl } from '../harness/seed';

const NAMES = { en: 'Lamp questions', ar: 'أسئلة المصباح' } as const;
const FOUND = [
  {
    repo_id: 'e2e-lab/lamp-dialogues',
    downloads: 48_200,
    likes: 310,
    license: 'apache-2.0',
    gated: false,
    size_category: '10K<n<100K',
    languages: ['ar', 'en'],
    description: 'Conversations about oil lamps, in Arabic and English.',
    in_library: false,
  },
  {
    repo_id: 'e2e-lab/private-wicks',
    downloads: 1_200,
    likes: 12,
    license: 'cc-by-4.0',
    gated: true,
    size_category: 'n<1K',
    languages: ['en'],
    description: 'Questions and answers about wicks.',
    in_library: true,
  },
] as const;

test('an uploaded JSONL file becomes a dataset whose rows can be read', async ({ page, t, locale, shot }) => {
  const name = `${NAMES[locale]} ${stamp()}`;
  await page.goto('/datasets');
  const upload = page.getByRole('region', { name: t('datasets', 'datasets.upload.title') });

  await upload.getByLabel(t('datasets', 'datasets.upload.name')).fill(name);
  await pickFile(page, upload.getByRole('button', { name: t('datasets', 'datasets.upload.choose') }), {
    name: 'lamp-questions.jsonl',
    mimeType: 'application/x-ndjson',
    buffer: jsonl(CHAT_ROWS),
  });

  await expect(page.getByText(t('datasets', 'datasets.uploaded'))).toBeVisible();
  const card = page
    .getByRole('region', { name: t('datasets', 'datasets.library.title') })
    .getByRole('listitem')
    .filter({ has: page.getByRole('heading', { level: 3, name, exact: true }) });
  await expect(card.getByText(t('datasets', 'datasets.library.ready'))).toBeVisible();
  await expect(card.getByText(t('datasets', 'datasets.rowsCount', { count: 12 }))).toBeVisible();
  await expect(card.getByText('lamp-questions.jsonl', { exact: true })).toBeVisible();
  await shot('an uploaded dataset in the library');

  await card.getByRole('link', { name: t('datasets', 'datasets.library.openFor', { name }) }).click();
  await expect(page.getByRole('heading', { level: 1, name, exact: true })).toBeVisible();
  const rows = page.getByRole('region', { name: t('datasets', 'datasets.detail.rowsTitle') });
  const first = rows.getByRole('listitem').filter({ hasText: 'Question 1?' }).first();
  await expect(first.getByText(t('datasets', 'datasets.conversation.number', { number: 1 }))).toBeVisible();
  await expect(first.getByText('Answer 1.', { exact: true })).toBeVisible();
  await first.getByRole('button', { name: t('datasets', 'datasets.conversation.thinking') }).click();
  await expect(first.getByText('Think about 1.', { exact: true })).toBeVisible();
  await expect(rows.getByText(t('datasets', 'datasets.conversation.number', { number: 11 }))).toHaveCount(0);
  await shot('the rows of the dataset');

  await rows.getByRole('button', { name: t('core', 'paginator.next') }).click();
  await expect(rows.getByText(t('datasets', 'datasets.conversation.number', { number: 11 }))).toBeVisible();
  await expect(rows.getByText('Question 12?', { exact: true })).toBeVisible();
});

test('a file that holds no dataset is refused with the reason', async ({ page, t, shot }) => {
  await page.goto('/datasets');
  const upload = page.getByRole('region', { name: t('datasets', 'datasets.upload.title') });
  const choose = upload.getByRole('button', { name: t('datasets', 'datasets.upload.choose') });

  await pickFile(page, choose, { name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('Notes about lamps.\n') });
  await expect(upload.getByRole('alert')).toHaveText(t('datasets', 'errors.unsupported_file'));
  await shot('a text file refused');

  await pickFile(page, choose, {
    name: 'lamp-weights.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('colour,weight\nred,3\nblue,4\n'),
  });
  await expect(upload.getByRole('alert')).toHaveText(t('datasets', 'errors.unsupported_format'));
  await expect(page.getByText('lamp-weights.csv', { exact: true })).toHaveCount(0);
  await expect(page.getByText('notes.txt', { exact: true })).toHaveCount(0);
});

test('a HuggingFace search shows what each dataset holds', async ({ page, t, locale, shot }) => {
  const asked: string[] = [];
  await page.route(
    (url) => url.pathname === '/api/datasets/hub/',
    async (route) => {
      const search = new URL(route.request().url()).searchParams.get('search') ?? '';
      asked.push(search);
      const results = FOUND.filter((found) => found.repo_id.includes(search));
      await route.fulfill({ json: { count: results.length, next: null, previous: null, results } });
    },
  );
  await page.goto('/datasets');
  const find = page.getByRole('region', { name: t('datasets', 'datasets.find.title') });
  const card = (repo: string): Locator =>
    find.getByRole('listitem').filter({ has: page.getByRole('heading', { level: 3, name: repo, exact: true }) });

  await expect(find.getByRole('status')).toHaveText(t('datasets', 'datasets.find.popular'));
  await expect(card(FOUND[0].repo_id).getByText(FOUND[0].description)).toBeVisible();
  await expect(card(FOUND[0].repo_id)).toContainText(FOUND[0].license);
  await expect(card(FOUND[0].repo_id).getByText(t('datasets', 'datasets.find.gated'))).toHaveCount(0);
  await expect(card(FOUND[1].repo_id).getByText(t('datasets', 'datasets.find.gated'))).toBeVisible();
  await expect(card(FOUND[1].repo_id).getByText(t('datasets', 'datasets.find.inLibrary'))).toBeVisible();
  await expect(
    card(FOUND[0].repo_id).getByRole('button', { name: t('datasets', 'datasets.find.previewFor', { name: FOUND[0].repo_id }) }),
  ).toBeVisible();
  await shot('popular datasets');

  const field = find.getByLabel(t('datasets', 'datasets.find.label'));
  await field.fill('wicks');
  await field.press('Enter');

  await expect(find.getByRole('status')).toContainText(text('datasets', locale, 'datasets.find.resultsFor'));
  await expect(find.getByRole('status')).toContainText('wicks');
  await expect(find.getByRole('heading', { level: 3 })).toHaveCount(1);
  await expect(card(FOUND[1].repo_id)).toBeVisible();
  expect(asked).toContain('wicks');
});
