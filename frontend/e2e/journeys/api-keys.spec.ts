import { readJson, withKey } from '../harness/access';
import { field, rows } from '../harness/api';
import { stamp, text } from '../harness/copy';
import { expect, test } from '../harness/fixtures';
import { slugOf } from '../harness/versions';

test.use({ permissions: ['clipboard-read', 'clipboard-write'] });

test('a new API key is shown once, copies, opens the compatible API and stops working when revoked', async ({
  page,
  owner,
  world,
  stack,
  locale,
  t,
  shot,
}) => {
  const name = `journey key ${locale} ${stamp()}`;
  const slug = await slugOf(owner, world.projects[locale].chat);

  await page.goto('/engines');
  await page.getByRole('button', { name: t('serving', 'serving.keys.new') }).click();
  const asking = page.getByRole('dialog', { name: t('serving', 'serving.newKey.title') });
  await asking.getByRole('textbox', { name: t('serving', 'serving.newKey.name') }).fill(name);
  await asking.getByRole('button', { name: t('serving', 'serving.newKey.submit') }).click();

  const shown = page.getByRole('dialog', { name: t('serving', 'serving.newKey.createdTitle') });
  await expect(shown.getByText(t('serving', 'serving.newKey.warning'))).toBeVisible();
  const keyField = shown.getByRole('textbox', { name: t('serving', 'serving.newKey.keyLabel') });
  await expect(keyField).toHaveValue(/^msb_\S{20,}$/);
  const key = await keyField.inputValue();
  await shot('key shown once');

  const what = text('serving', locale, 'serving.newKey.keyLabel');
  await shown.getByRole('button', { name: t('serving', 'serving.copy.for', { what }) }).click();
  await expect(page.getByText(t('serving', 'serving.copy.done'))).toBeVisible();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe(key);
  await shown.getByRole('button', { name: t('serving', 'serving.newKey.done') }).click();
  await expect(shown).toHaveCount(0);

  const row = page.getByRole('row').filter({ hasText: name });
  await expect(row).toContainText(`${key.slice(0, 12)}…`);
  await expect(page.getByText(key)).toHaveCount(0);
  await page.reload();
  await expect(row).toBeVisible();
  await expect(page.getByText(key)).toHaveCount(0);

  const client = await withKey(stack.base_url, key);
  const listed = await client.get('/v1/models');
  expect(listed.status()).toBe(200);
  const models = rows(await readJson(listed), 'data').map((model) => field(model, 'id'));
  expect(models).toContain(slug);
  await shot('key listed');

  await row.getByRole('button', { name: t('serving', 'serving.keys.revokeFor', { name }) }).click();
  const asked = page.getByRole('dialog', { name: t('serving', 'serving.keys.revokeTitle', { name }) });
  await asked.getByRole('button', { name: t('serving', 'serving.keys.revokeConfirm') }).click();
  await expect(page.getByText(t('serving', 'serving.keys.revoked'))).toBeVisible();
  await expect(row).toHaveCount(0);

  const refused = await client.get('/v1/models');
  expect(refused.status()).toBe(401);
  const error = (await readJson(refused))['error'];
  expect(error).toMatchObject({ code: 'invalid_api_key' });
  await client.dispose();
});
