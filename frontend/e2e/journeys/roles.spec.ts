import { SavedSession, answer, writeOperations } from '../harness/access';
import { MesbahApi } from '../harness/api';
import { anyValues } from '../harness/copy';
import { expect, test } from '../harness/fixtures';
import { settled } from '../harness/pages';
import { VIEWER_WRITES } from '../harness/roles.data';

test('every change the API offers is refused to a viewer', async ({ owner, stack, world, locale }) => {
  test.skip(locale === 'ar', 'the API answers the same in either language, so it is checked once');
  const operations = writeOperations(await owner.get('/api/schema/?format=json'));
  const listed = new Set(operations.map((operation) => operation.id));
  const uncovered = operations.filter((operation) => !(operation.id in VIEWER_WRITES));

  expect(operations.length).toBeGreaterThan(0);
  expect(
    uncovered.map((operation) => `${operation.method} ${operation.path} (${operation.id})`),
    'operations harness/roles.data.ts does not cover',
  ).toEqual([]);
  expect(
    Object.keys(VIEWER_WRITES).filter((id) => !listed.has(id)),
    'entries in harness/roles.data.ts the schema no longer has',
  ).toEqual([]);

  const viewer = await SavedSession.open(stack.base_url, 'viewer');
  const me: unknown = await (await viewer.send('GET', '/api/auth/me/')).json();
  expect(me).toMatchObject({ username: world.users.viewer, groups: ['viewers'] });

  const wrong: string[] = [];
  for (const operation of operations) {
    const expected = VIEWER_WRITES[operation.id];
    if (expected === undefined) {
      continue;
    }
    const own = expected.ownSession ? await MesbahApi.signIn(stack.base_url, world.users.viewer, world.password) : null;
    const got = await answer(
      own
        ? await own.send(operation.method, operation.url, expected.body ?? {})
        : await viewer.send(operation.method, operation.url, expected.body, operation.multipart),
    );
    await own?.dispose();
    if (got.status !== expected.status || got.code !== expected.code || /CSRF/i.test(got.message)) {
      wrong.push(
        `${operation.method} ${operation.url} (${operation.id}): expected ${expected.status} ${String(expected.code)}, ` +
          `got ${got.status} ${String(got.code)} ${got.message}`,
      );
    }
  }
  expect(wrong, 'answers that differ from harness/roles.data.ts').toEqual([]);

  expect((await viewer.send('GET', '/api/auth/me/')).status(), 'the saved session still works').toBe(200);
  await viewer.dispose();
});

test('a viewer reads every page of a project and finds nothing that changes it', async ({ page, as, t, world, locale, shot }) => {
  const project = world.projects[locale].versions;
  await page.goto('/projects');
  await expect(page.getByRole('button', { name: t('projects', 'projects.new.open') })).toBeVisible();
  await expect(page.getByRole('link', { name: t('core', 'nav.members') })).toBeVisible();
  await shot('owner projects');

  const viewer = await as('viewer');
  await viewer.goto('/projects');
  await expect(viewer.getByRole('heading', { level: 1, name: t('projects', 'projects.title') })).toBeVisible();
  await expect(viewer.getByRole('link', { name: anyValues('projects', locale, 'projects.openFor') }).first()).toBeVisible();
  await settled(viewer);
  await expect(viewer.getByRole('button', { name: t('projects', 'projects.new.open') })).toHaveCount(0);
  await expect(viewer.getByRole('link', { name: t('core', 'nav.members') })).toHaveCount(0);
  await shot('viewer projects', viewer);

  await viewer.goto(`/projects/${project}`);
  await expect(viewer.getByText(t('projects', 'projects.reply.readOnly'))).toBeVisible();
  await expect(viewer.getByRole('heading', { name: t('projects', 'projects.overview.remove.title') })).toHaveCount(0);
  await expect(viewer.getByRole('button', { name: t('projects', 'projects.overview.remove.open') })).toHaveCount(0);
  await expect(viewer.getByRole('textbox', { name: t('projects', 'projects.overview.about.name') })).toHaveCount(0);
  await shot('viewer overview', viewer);

  await viewer.getByRole('tab', { name: t('projects', 'projects.tabs.training') }).click();
  const runs = viewer.getByRole('list', { name: t('training', 'training.runs.list') });
  await expect(runs.getByRole('link', { name: t('training', 'training.runs.open') }).first()).toBeVisible();
  await settled(viewer);
  await expect(viewer.getByRole('heading', { name: t('training', 'training.form.title') })).toHaveCount(0);
  await expect(viewer.getByRole('button', { name: t('training', 'training.form.start') })).toHaveCount(0);
  await expect(runs.getByRole('button', { name: t('training', 'training.runs.stop.open') })).toHaveCount(0);
  await expect(runs.getByRole('button', { name: t('training', 'training.runs.remove.open') })).toHaveCount(0);
  await shot('viewer training', viewer);

  await viewer.getByRole('tab', { name: t('projects', 'projects.tabs.versions') }).click();
  await viewer.getByRole('button', { name: anyValues('versions', locale, 'versions.row.actionsFor') }).first().click();
  const menu = viewer.getByRole('menu');
  await expect(menu.getByRole('menuitem', { name: t('versions', 'versions.menu.exports') })).toBeVisible();
  await expect(menu.getByRole('menuitem', { name: t('versions', 'versions.menu.export') })).toHaveCount(0);
  await expect(menu.getByRole('menuitem', { name: t('versions', 'versions.menu.activate') })).toHaveCount(0);
  await expect(menu.getByRole('menuitem', { name: t('versions', 'versions.menu.rename') })).toHaveCount(0);
  await expect(menu.getByRole('menuitem', { name: t('versions', 'versions.menu.remove') })).toHaveCount(0);
  await shot('viewer version menu', viewer);
  await viewer.keyboard.press('Escape');
  await expect(menu).toHaveCount(0);

  await viewer.getByRole('tab', { name: t('projects', 'projects.tabs.chat') }).click();
  await expect(viewer.getByRole('heading', { name: t('chat', 'chat.list.title') })).toBeVisible();
  await settled(viewer);
  await expect(viewer.getByRole('button', { name: t('chat', 'chat.list.new') })).toHaveCount(0);
  await shot('viewer chat', viewer);
});

test('a viewer can open System but not change it, and is kept out of Members', async ({ as, t, shot }) => {
  const viewer = await as('viewer');
  await viewer.goto('/projects');
  await viewer.getByRole('link', { name: t('core', 'nav.system') }).click();

  await expect(viewer.getByRole('heading', { level: 1, name: t('system', 'system.title') })).toBeVisible();
  await expect(viewer.getByText(t('system', 'system.hf.adminOnly'))).toBeVisible();
  await expect(viewer.getByRole('button', { name: t('system', 'system.hf.save') })).toHaveCount(0);
  await expect(viewer.getByRole('textbox', { name: t('system', 'system.hf.token') })).toHaveCount(0);
  await shot('viewer system', viewer);

  await viewer.goto('/members');
  await expect(viewer).toHaveURL(/\/forbidden$/);
  await expect(viewer.getByRole('heading', { level: 1, name: t('core', 'errors.forbidden') })).toBeVisible();
});
