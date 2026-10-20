import { isJson, rows } from '../harness/api';
import { expect, test } from '../harness/fixtures';

const TRAINING_PARTS: readonly string[] = ['torch', 'transformers', 'peft', 'trl'];

test('the System page shows the data folder, the GPUs and the training parts this install has', async ({
  page,
  owner,
  stack,
  t,
  shot,
}) => {
  const overview = await owner.get('/api/system/');
  const machine = isJson(overview['machine']) ? overview['machine'] : {};
  const gpus = Array.isArray(machine['gpus']) ? machine['gpus'] : [];
  const parts = rows(overview, 'parts');

  await page.goto('/system');
  await expect(page.getByRole('heading', { level: 1, name: t('system', 'system.title') })).toBeVisible();
  const gpuSection = page.getByRole('region', { name: t('system', 'system.gpus.title') });
  if (gpus.length === 0) {
    await expect(gpuSection.getByText(t('system', 'system.gpus.none'))).toBeVisible();
    await expect(gpuSection.getByText(t('system', 'system.gpus.noneBody'))).toBeVisible();
  } else {
    await expect(gpuSection.getByText(t('system', 'system.gpus.none'))).toHaveCount(0);
  }
  await shot('system in simple mode');

  await page.getByRole('radio', { name: t('core', 'mode.expert') }).click();
  const memory = page.getByRole('region', { name: t('system', 'system.memory.title') });
  await expect(memory.getByText(stack.data_dir, { exact: true })).toBeVisible();

  const partsSection = page.getByRole('region', { name: t('system', 'system.parts.title') });
  const ready = TRAINING_PARTS.every((name) =>
    parts.some((part) => part['name'] === name && typeof part['version'] === 'string'),
  );
  await expect(
    partsSection.getByText(t('system', ready ? 'system.parts.ready' : 'system.parts.missing')),
  ).toBeVisible();
  expect(parts.length).toBeGreaterThan(0);
  for (const part of parts) {
    const name = String(part['name']);
    const version = part['version'];
    const row = partsSection.locator('dl > div').filter({ has: page.getByText(name, { exact: true }) });
    await expect(
      row.getByText(
        typeof version === 'string'
          ? t('system', 'system.parts.installed', { version })
          : t('system', 'system.parts.notInstalled'),
      ),
    ).toBeVisible();
    await expect(row.getByText(t('system', `system.parts.purpose.${String(part['purpose'])}`))).toBeVisible();
  }
  await shot('system in expert mode');
});

test('saving a HuggingFace token checks it with HuggingFace, and offline says it can not reach it', async ({
  page,
  owner,
  t,
  shot,
}) => {
  const hf = page.getByRole('region', { name: t('system', 'system.hf.title') });

  await page.goto('/system');
  await expect(hf.getByText(t('system', 'system.hf.missing'))).toBeVisible();
  await hf.getByLabel(t('system', 'system.hf.token')).fill('hf_journeyTokenThatIsNeverSent');
  await hf.getByRole('button', { name: t('system', 'system.hf.save') }).click();

  await expect(page.getByRole('alert')).toHaveText(t('core', 'errors.hf_unreachable'));
  await expect(hf.getByText(t('system', 'system.hf.missing'))).toBeVisible();
  const huggingface = (await owner.get('/api/system/'))['huggingface'];
  expect(isJson(huggingface) ? huggingface['configured'] : null).toBe(false);
  await shot('token not saved offline');
});

test('the System page names the version of Mesbah it runs', async ({ page, stack, t }) => {
  await page.goto('/system');

  await expect(page.getByText(t('system', 'system.release', { version: stack.version }))).toBeVisible();
});
