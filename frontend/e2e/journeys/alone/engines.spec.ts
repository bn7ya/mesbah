import { ask, startConversation } from '../../harness/chat';
import { stamp } from '../../harness/copy';
import { expect, test } from '../../harness/fixtures';
import { repoOf } from '../../harness/versions';

test('the built-in engine runs, shows the model a chat loaded and frees its memory', async ({
  page,
  owner,
  world,
  locale,
  t,
  shot,
}) => {
  test.slow();
  const repoId = await repoOf(owner, world.baseModel);

  await page.goto('/engines');
  const builtin = page.getByRole('region', { name: t('serving', 'serving.builtin.title') });
  await expect(builtin.getByText(t('serving', 'serving.state.running'))).toBeVisible();
  await expect(builtin.getByText(t('serving', 'serving.state.default'))).toBeVisible();

  // The engine is shared with the other language's journeys, which may free it in between.
  await expect(async () => {
    await ask(owner, await startConversation(owner, world.projects[locale].chat), `Load the model for ${locale}`);
    await page.reload();
    await expect(builtin.getByText(repoId, { exact: true })).toBeVisible({ timeout: 5_000 });
  }).toPass({ timeout: 60_000 });
  await expect(builtin.getByText(t('serving', 'serving.builtin.baseModel'))).toBeVisible();
  await expect(builtin.getByText(t('serving', 'serving.builtin.deviceCpu'))).toBeVisible();
  await shot('model loaded');

  const free = builtin.getByRole('button', { name: t('serving', 'serving.builtin.free.open') });
  const asked = page.getByRole('dialog', { name: t('serving', 'serving.builtin.free.title') });
  await expect(async () => {
    if (await free.isVisible()) {
      await free.click();
      await asked.getByRole('button', { name: t('serving', 'serving.builtin.free.confirm') }).click();
      await expect(page.getByText(t('serving', 'serving.builtin.free.done'))).toBeVisible({ timeout: 5_000 });
    }
    await expect(builtin.getByText(t('serving', 'serving.builtin.idle'))).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 30_000 });
  await expect(builtin.getByText(repoId, { exact: true })).toHaveCount(0);
  await expect(free).toHaveCount(0);
  await shot('nothing loaded');
});

test('an OpenAI-compatible engine is connected, listed and disconnected', async ({ page, stack, locale, t, shot }) => {
  const name = `Journey engine ${locale} ${stamp()}`;

  await page.goto('/engines');
  const others = page.getByRole('region', { name: t('serving', 'serving.others.title') });
  await others.getByRole('button', { name: t('serving', 'serving.others.connect') }).click();

  const form = page.getByRole('dialog', { name: t('serving', 'serving.form.connectTitle') });
  await form.getByRole('textbox', { name: t('serving', 'serving.form.name') }).fill(name);
  await form.getByRole('combobox', { name: t('serving', 'serving.form.kind') }).click();
  await page.getByRole('option', { name: t('serving', 'serving.kinds.openai.name') }).click();
  await form.getByRole('textbox', { name: t('serving', 'serving.form.address') }).fill(stack.engine_url);
  await form.getByRole('button', { name: t('serving', 'serving.form.connect') }).click();

  await expect(page.getByText(t('serving', 'serving.others.connected'))).toBeVisible();
  const card = others.getByRole('listitem').filter({ hasText: name });
  await expect(card.getByText(t('serving', 'serving.state.running'))).toBeVisible();
  await expect(card.getByText(t('serving', 'serving.kinds.openai.name'))).toBeVisible();
  await expect(card.getByText(stack.engine_url, { exact: true })).toBeVisible();
  await expect(card.getByText(t('serving', 'serving.state.default'))).toHaveCount(0);
  await shot('engine connected');

  await card.getByRole('button', { name: t('serving', 'serving.others.disconnectFor', { name }) }).click();
  const asked = page.getByRole('dialog', { name: t('serving', 'serving.others.disconnectTitle', { name }) });
  await expect(asked.getByText(t('serving', 'serving.others.disconnectBody'))).toBeVisible();
  await asked.getByRole('button', { name: t('serving', 'serving.others.disconnectConfirm') }).click();

  await expect(page.getByText(t('serving', 'serving.others.disconnected'))).toBeVisible();
  await expect(others.getByText(name)).toHaveCount(0);
});
