import { expect, horizontalOverflow, test } from '../harness/fixtures';
import { settled } from '../harness/pages';

test.use({ viewport: { width: 390, height: 844 } });

const PAGES = [
  { path: '/projects', bundle: 'projects', title: 'projects.title' },
  { path: '/models', bundle: 'models', title: 'models.title' },
  { path: '/datasets', bundle: 'datasets', title: 'datasets.title' },
  { path: '/architect', bundle: 'architect', title: 'architect.title' },
  { path: '/engines', bundle: 'serving', title: 'serving.title' },
  { path: '/system', bundle: 'system', title: 'system.title' },
  { path: '/members', bundle: 'members', title: 'members.title' },
] as const;

const TABS = [
  { path: '', bundle: 'projects', heading: 'projects.overview.about.title' },
  { path: '/chat', bundle: 'chat', heading: 'chat.choose.title' },
  { path: '/training', bundle: 'training', heading: 'training.learns.title' },
  { path: '/versions', bundle: 'versions', heading: 'versions.title' },
] as const;

for (const { path, bundle, title } of PAGES) {
  test(`${path} fits a phone without sideways scrolling`, async ({ page, t, shot }) => {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1, name: t(bundle, title) })).toBeVisible();
    await settled(page);

    expect(await horizontalOverflow(page), 'pixels wider than the screen').toBeLessThanOrEqual(1);
    await shot(path.slice(1));
  });
}

for (const { path, bundle, heading } of TABS) {
  test(`the project tab ${path || '/'} fits a phone without sideways scrolling`, async ({ page, world, locale, t, shot }) => {
    await page.goto(`/projects/${world.projects[locale].versions}${path}`);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByText(t(bundle, heading)).first()).toBeVisible();
    await settled(page);

    expect(await horizontalOverflow(page), 'pixels wider than the screen').toBeLessThanOrEqual(1);
    await shot(`project ${path.slice(1) || 'overview'}`);
  });
}

test('the menu button opens the navigation and a link closes it again', async ({ page, t, shot }) => {
  await page.goto('/projects');
  const models = page.getByRole('link', { name: t('core', 'nav.models') });
  await expect(page.getByRole('heading', { level: 1, name: t('projects', 'projects.title') })).toBeVisible();
  await expect(models).toBeHidden();

  await page.getByRole('button', { name: t('core', 'nav.open') }).click();
  await expect(models).toBeVisible();
  await expect(page.getByRole('link', { name: t('core', 'nav.projects') })).toHaveAttribute('aria-current', 'page');
  await shot('navigation open');
  await models.click();

  await expect(page).toHaveURL(/\/models$/);
  await expect(page.getByRole('heading', { level: 1, name: t('models', 'models.title') })).toBeVisible();
  await expect(models).toBeHidden();
});
