import { field, isJson } from '../../harness/api';
import { anyValues, stamp, startsWith, text } from '../../harness/copy';
import { expect, test } from '../../harness/fixtures';
import { estimated } from '../../harness/pages';

test('a model designed here trains from nothing, joins the library and answers in chat', async ({
  page,
  owner,
  world,
  locale,
  t,
  shot,
}) => {
  test.slow();
  const design = `${locale === 'en' ? 'Designer journey' : 'رحلة المصمم'} ${stamp()}`;
  const projectName = `${locale === 'en' ? 'Designed model' : 'نموذج مصمم'} ${stamp()}`;
  const dataset = field(await owner.get(`/api/datasets/${world.dataset}/`), 'name');
  const layers = page.getByRole('spinbutton', { name: t('architect', 'architect.field.layers.label') });
  const breakdown = page.getByRole('img', { name: anyValues('architect', locale, 'architect.breakdown.where') });
  const weights = page.getByText(anyValues('architect', locale, 'architect.memory.weights'));
  const save = page.getByRole('button', { name: t('architect', 'architect.actions.save') });
  await page.goto('/architect');
  await expect(page.getByRole('heading', { level: 1, name: t('architect', 'architect.title') })).toBeVisible();

  const tiny = estimated(page, 2);
  await page
    .getByRole('button', { name: t('architect', 'architect.preset.useFor', { name: text('architect', locale, 'architect.preset.tiny') }) })
    .click();
  await tiny;
  await expect(page.getByText(t('architect', 'architect.preset.loaded'))).toBeVisible();
  await expect(layers).toHaveValue('2');
  const split = await breakdown.getAttribute('aria-label');
  const size = await weights.innerText();

  const deeper = estimated(page, 6);
  await layers.fill('6');
  await deeper;
  await expect(breakdown).not.toHaveAttribute('aria-label', split ?? '');
  await expect(weights).not.toHaveText(size);
  await shot('estimate for six layers');

  await layers.fill('300');
  await expect(page.getByText(anyValues('architect', locale, 'architect.error.range'))).toBeVisible();
  await expect(layers).toHaveAttribute('aria-invalid', 'true');
  await expect(save).toBeDisabled();
  await shot('layers out of range');

  const fixed = estimated(page, 3);
  await layers.fill('3');
  await fixed;
  await expect(layers).toHaveAttribute('aria-invalid', 'false');
  await page.getByRole('textbox', { name: t('architect', 'architect.field.tokenizer.label') }).fill('e2e/tokenizer');
  await expect(save).toBeEnabled();
  await save.click();
  const saving = page.getByRole('dialog');
  await saving.getByRole('textbox', { name: t('architect', 'architect.save.name') }).fill(design);
  await saving.getByRole('button', { name: t('architect', 'architect.save.submit') }).click();

  await expect(saving).toHaveCount(0);
  await expect(page.getByText(t('architect', 'architect.design.fromDraft'))).toBeVisible();
  await expect(page.getByRole('heading', { name: startsWith(design) })).toBeVisible();
  await page.getByRole('button', { name: t('architect', 'architect.actions.train') }).click();
  const training = page.getByRole('dialog');
  await expect(training.getByRole('heading', { name: t('architect', 'architect.train.title') })).toBeVisible();
  await training.getByRole('textbox', { name: t('architect', 'architect.train.name') }).fill(projectName);
  await training.getByRole('option', { name: startsWith(dataset) }).click();
  await shot('train from nothing');
  await training.getByRole('button', { name: t('architect', 'architect.train.submit') }).click();

  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]{36}\/training\/[0-9a-f-]{36}$/);
  await expect(page.getByText(t('training', 'training.result.pretrainDone'))).toBeVisible({ timeout: 90_000 });
  await expect(page.getByRole('heading', { level: 1, name: startsWith(projectName) })).toBeVisible();
  await shot('new model trained');
  const project = new URL(page.url()).pathname.split('/')[2] ?? '';
  const base = (await owner.get(`/api/projects/${project}/`))['base_model'];
  const repo = isJson(base) ? field(base, 'repo_id') : '';
  expect(repo).toMatch(/^local\//);

  await page.getByRole('link', { name: t('training', 'training.result.toModels') }).click();
  const card = page.getByRole('listitem').filter({ has: page.getByRole('heading', { name: repo, exact: true }) });
  await expect(card).toBeVisible();
  await expect(card.getByText(t('models', 'models.library.ready'))).toBeVisible();
  await shot('in the library');

  await page.goto(`/projects/${project}/chat`);
  await page.getByRole('button', { name: t('chat', 'chat.list.new') }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${project}/chat/[0-9a-f-]{36}$`));
  const composer = page.getByRole('textbox', { name: t('chat', 'chat.composer.label') });
  await expect(composer).toBeEnabled();
  await composer.fill('What were you trained on?');
  await composer.press('Enter');

  await expect(page.getByRole('article', { name: t('chat', 'chat.sender.model') })).toContainText(
    'Reply from base: What were you trained on?',
    { timeout: 60_000 },
  );
  await expect(page.getByRole('button', { name: t('chat', 'chat.composer.send') })).toBeVisible();
  await shot('first answer');
});
