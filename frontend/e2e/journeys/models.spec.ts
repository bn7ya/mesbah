import type { Locator } from '@playwright/test';

import { text } from '../harness/copy';
import { expect, test } from '../harness/fixtures';
import { repoOf } from '../harness/versions';

const GIB = 1024 ** 3;
const fit = (verdict: string, required: number | null) => ({ verdict, required_bytes: required, available_bytes: 0 });
const FOUND = [
  {
    repo_id: 'e2e-lab/lamp-0.5b-chat',
    downloads: 90_500,
    likes: 410,
    pipeline_tag: 'text-generation',
    parameters: 494_000_000,
    license: 'apache-2.0',
    gated: false,
    model_type: 'qwen2',
    supports_thinking: false,
    fit: { chat: fit('cpu_only', GIB), chat_full: fit('cpu_only', 2 * GIB), training: fit('cpu_only', 3 * GIB) },
    in_library: null,
  },
  {
    repo_id: 'e2e-lab/lamp-70b-think',
    downloads: 12_300,
    likes: 980,
    pipeline_tag: 'text-generation',
    parameters: 70_600_000_000,
    license: 'llama3.3',
    gated: true,
    model_type: 'llama',
    supports_thinking: true,
    fit: { chat: fit('too_large', 40 * GIB), chat_full: fit('too_large', 140 * GIB), training: fit('too_large', 48 * GIB) },
    in_library: null,
  },
  {
    repo_id: 'e2e-lab/lamp-t5',
    downloads: 3_100,
    likes: 25,
    pipeline_tag: 'text2text-generation',
    parameters: null,
    license: '',
    gated: false,
    model_type: 't5',
    supports_thinking: false,
    fit: { chat: fit('unknown', null), chat_full: fit('unknown', null), training: fit('unknown', null) },
    in_library: null,
  },
] as const;

test('the library lists the model trained here as ready', async ({ page, t, owner, world, shot }) => {
  const repo = await repoOf(owner, world.baseModel);
  expect(repo).toMatch(/^local\//);
  await page.goto('/models');

  const card = page
    .getByRole('region', { name: t('models', 'models.library.title') })
    .getByRole('listitem')
    .filter({ has: page.getByRole('heading', { level: 3, name: repo, exact: true }) });
  await expect(card.getByText(t('models', 'models.library.ready'))).toBeVisible();
  await expect(card.getByRole('button', { name: t('models', 'models.library.removeFor', { name: repo }) })).toBeVisible();
  await shot('the library');
});

test("a search says when HuggingFace can't be reached and tries again", async ({ page, t, shot }) => {
  await page.goto('/models');
  const find = page.getByRole('region', { name: t('models', 'models.find.title') });
  const unreachable = find.getByRole('alert');

  await expect(unreachable).toHaveText(t('core', 'errors.hf_unreachable'));
  await shot("HuggingFace can't be reached");
  const again = page.waitForRequest((request) => new URL(request.url()).pathname === '/api/models/hub/');
  await find.getByRole('button', { name: t('core', 'actions.retry') }).click();
  await again;
  await expect(unreachable).toHaveText(t('core', 'errors.hf_unreachable'));

  const field = find.getByLabel(t('models', 'models.find.label'));
  await field.fill('qwen');
  await field.press('Enter');
  await expect(find.getByRole('status')).toContainText('qwen');
  await expect(unreachable).toHaveText(t('core', 'errors.hf_unreachable'));
  await expect(find.getByRole('button', { name: t('core', 'actions.retry') })).toBeVisible();
});

test('search results say how each model would fit this machine', async ({ page, t, locale, shot }) => {
  const asked: URLSearchParams[] = [];
  await page.route(
    (url) => url.pathname === '/api/models/hub/',
    async (route) => {
      const query = new URL(route.request().url()).searchParams;
      asked.push(query);
      const search = query.get('search') ?? '';
      const task = query.get('task') ?? 'text-generation';
      const results = FOUND.filter((found) => found.repo_id.includes(search) && (search === '' || found.pipeline_tag === task));
      await route.fulfill({ json: { count: results.length, next: null, previous: null, results } });
    },
  );
  await page.goto('/models');
  const find = page.getByRole('region', { name: t('models', 'models.find.title') });
  const card = (repo: string): Locator =>
    find.getByRole('listitem').filter({ has: page.getByRole('heading', { level: 3, name: repo, exact: true }) });
  const verdict = (key: string): string =>
    `${text('models', locale, 'models.find.chat')}: ${text('models', locale, `models.fit.verdict.${key}`)}`;

  await expect(find.getByRole('status')).toHaveText(t('models', 'models.find.popular'));
  await expect(card(FOUND[0].repo_id)).toContainText(verdict('cpu_only'));
  await expect(card(FOUND[1].repo_id)).toContainText(verdict('too_large'));
  await expect(card(FOUND[2].repo_id)).toContainText(verdict('unknown'));
  await expect(card(FOUND[1].repo_id).getByText(t('models', 'models.find.gated'))).toBeVisible();
  await expect(card(FOUND[1].repo_id).getByText(t('models', 'models.thinking'))).toBeVisible();
  await expect(card(FOUND[0].repo_id).getByText(t('models', 'models.find.gated'))).toHaveCount(0);
  await expect(find.getByRole('radio', { name: t('models', 'models.find.tasks.text2text-generation') })).toBeDisabled();
  await shot('popular models and how they fit');

  const field = find.getByLabel(t('models', 'models.find.label'));
  await field.fill('lamp');
  await field.press('Enter');
  await expect(find.getByRole('status')).toContainText('lamp');
  await expect(find.getByRole('heading', { level: 3 })).toHaveCount(2);
  await find.getByRole('radio', { name: t('models', 'models.find.tasks.text2text-generation') }).click();

  await expect(find.getByRole('heading', { level: 3 })).toHaveCount(1);
  await expect(card(FOUND[2].repo_id)).toContainText(verdict('unknown'));
  expect(asked.some((query) => query.get('task') === 'text2text-generation')).toBe(true);
});
