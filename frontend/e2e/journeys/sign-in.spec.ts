import { expect, test } from '../harness/fixtures';

test.use({ storageState: { cookies: [], origins: [] } });

test('a signed-out visitor is sent to sign in', async ({ page, t }) => {
  await page.goto('/projects');

  await expect(page).toHaveURL(/\/sign-in/);
  await expect(page.getByRole('heading', { level: 1, name: t('core', 'auth.signIn.title') })).toBeVisible();
});

test('wrong credentials say so without saying which part was wrong', async ({ page, t }) => {
  await page.goto('/sign-in');

  await page.getByLabel(t('core', 'auth.signIn.username')).fill('nobody');
  await page.getByRole('textbox', { name: t('core', 'auth.signIn.password') }).fill('wrong-password');
  await page.getByRole('button', { name: t('core', 'auth.signIn.submit') }).click();

  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL(/\/sign-in/);
});

test('the form reports each missing field', async ({ page, t }) => {
  await page.goto('/sign-in');

  await page.getByRole('button', { name: t('core', 'auth.signIn.submit') }).click();

  await expect(page.getByText(t('core', 'auth.errors.usernameRequired'))).toBeVisible();
  await expect(page.getByText(t('core', 'auth.errors.passwordRequired'))).toBeVisible();
});

test('the page is reachable by keyboard alone', async ({ page, t }) => {
  await page.goto('/sign-in');
  await expect(page.getByLabel(t('core', 'auth.signIn.username'))).toBeVisible();

  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');

  await expect(page.getByLabel(t('core', 'auth.signIn.username'))).toBeFocused();
});

test('switching the language flips the document and stays after a reload', async ({ page, locale }) => {
  const other = locale === 'en' ? { name: 'العربية', lang: 'ar', dir: 'rtl' } : { name: 'English', lang: 'en', dir: 'ltr' };
  await page.goto('/sign-in');

  await page.getByRole('radio', { name: other.name }).click();
  await page.reload();

  await expect(page.locator('html')).toHaveAttribute('dir', other.dir);
  await expect(page.locator('html')).toHaveAttribute('lang', other.lang);
});

test('a member signs in, lands on Projects and signs out again', async ({ page, t, world, shot }) => {
  await page.goto('/sign-in');

  await page.getByLabel(t('core', 'auth.signIn.username')).fill(world.users.viewer);
  await page.getByRole('textbox', { name: t('core', 'auth.signIn.password') }).fill(world.password);
  await page.getByRole('button', { name: t('core', 'auth.signIn.submit') }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await shot('signed in');
  await page.getByRole('button', { name: new RegExp(world.users.viewer) }).click();
  await page.getByRole('menuitem', { name: t('core', 'auth.signOut') }).click();

  await expect(page).toHaveURL(/\/sign-in/);
  expect((await page.request.get('/api/projects/')).status()).toBe(403);
});

test.describe('a first visit', () => {
  test.use({ uiLocale: null });

  test('is in Arabic', async ({ page }) => {
    await page.goto('/sign-in');

    await expect(page.locator('html')).toHaveAttribute('lang', 'ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  });
});
