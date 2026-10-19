import { expect, test } from '../harness/fixtures';

const PAGES = [
  { link: 'nav.projects', bundle: 'projects', title: 'projects.title', path: /\/projects$/ },
  { link: 'nav.models', bundle: 'models', title: 'models.title', path: /\/models$/ },
  { link: 'nav.datasets', bundle: 'datasets', title: 'datasets.title', path: /\/datasets$/ },
  { link: 'nav.architect', bundle: 'architect', title: 'architect.title', path: /\/architect$/ },
  { link: 'nav.engines', bundle: 'serving', title: 'serving.title', path: /\/engines$/ },
  { link: 'nav.system', bundle: 'system', title: 'system.title', path: /\/system$/ },
  { link: 'nav.members', bundle: 'members', title: 'members.title', path: /\/members$/ },
] as const;

test('the document is in the language the reader chose', async ({ page, locale }) => {
  await page.goto('/projects');

  await expect(page.locator('html')).toHaveAttribute('lang', locale);
  await expect(page.locator('html')).toHaveAttribute('dir', locale === 'ar' ? 'rtl' : 'ltr');
});

test('the side menu reaches every page the owner may see', async ({ page, t, shot }) => {
  await page.goto('/projects');
  const menu = page.getByRole('navigation', { name: t('core', 'nav.label') });
  await expect(menu.getByRole('link')).toHaveCount(PAGES.length);

  for (const item of PAGES) {
    const link = menu.getByRole('link', { name: t('core', item.link) });
    await link.click();

    await expect(page).toHaveURL(item.path);
    await expect(page.getByRole('heading', { level: 1, name: t(item.bundle, item.title) })).toBeVisible();
    await expect(link).toHaveAttribute('aria-current', 'page');
    if (item.link === 'nav.projects') {
      await shot('the menu beside Projects');
    }
  }
});

test('Expert shows the technical details and stays chosen after a reload', async ({ page, t, shot }) => {
  await page.goto('/system');
  const level = page.getByRole('radiogroup', { name: t('core', 'mode.label') });
  const software = page.getByText(t('system', 'system.memory.software'));
  await expect(page.getByRole('heading', { level: 1, name: t('system', 'system.title') })).toBeVisible();
  await expect(level.getByRole('radio', { name: t('core', 'mode.simple') })).toBeChecked();
  await expect(page.getByRole('heading', { level: 2, name: t('system', 'system.memory.title') })).toBeVisible();
  await expect(software).toHaveCount(0);
  await shot('system in Simple');

  await level.getByRole('radio', { name: t('core', 'mode.expert') }).click();
  await expect(software).toBeVisible();
  await page.reload();

  await expect(level.getByRole('radio', { name: t('core', 'mode.expert') })).toBeChecked();
  await expect(software).toBeVisible();
  await shot('system in Expert');
  await level.getByRole('radio', { name: t('core', 'mode.simple') }).click();
  await expect(software).toHaveCount(0);
});
