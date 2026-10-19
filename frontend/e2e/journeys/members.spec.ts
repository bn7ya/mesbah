import { readJson } from '../harness/access';
import { isJson, rows } from '../harness/api';
import { stamp, text } from '../harness/copy';
import { expect, test } from '../harness/fixtures';
import { signedOut } from '../harness/pages';

test('a member added as a viewer sees only what a viewer may, until the role changes', async ({
  page,
  browser,
  stack,
  world,
  locale,
  t,
  shot,
}) => {
  const username = `journey.${locale}.${stamp()}`;

  await page.goto('/members');
  await page.getByRole('button', { name: t('members', 'members.add.open') }).click();
  const form = page.getByRole('dialog', { name: t('members', 'members.add.title') });
  await form.getByRole('textbox', { name: t('members', 'members.add.username') }).fill(username);
  await form.getByLabel(t('members', 'members.add.password')).fill(world.password);
  await form.getByRole('combobox', { name: t('members', 'members.role') }).click();
  await page.getByRole('option', { name: t('members', 'members.roles.viewers.name') }).click();
  await form.getByRole('button', { name: t('members', 'members.add.submit') }).click();

  await expect(page.getByText(t('members', 'members.added'))).toBeVisible();
  const role = page.getByRole('button', { name: t('members', 'members.changeRole', { name: username }) });
  await expect(role).toHaveText(t('members', 'members.roles.viewers.name'));
  await shot('viewer added');

  const member = await signedOut(browser, stack.base_url, locale);
  const seen = member.page;
  await seen.goto('/sign-in');
  await seen.getByLabel(t('core', 'auth.signIn.username')).fill(username);
  await seen.getByRole('textbox', { name: t('core', 'auth.signIn.password') }).fill(world.password);
  await seen.getByRole('button', { name: t('core', 'auth.signIn.submit') }).click();
  await expect(seen).toHaveURL(/\/projects$/);

  const menu = seen.getByRole('navigation', { name: t('core', 'nav.label') });
  await expect(menu.getByRole('link', { name: t('core', 'nav.projects') })).toBeVisible();
  await expect(menu.getByRole('link', { name: t('core', 'nav.members') })).toHaveCount(0);
  await expect(seen.getByRole('button', { name: t('projects', 'projects.new.open') })).toHaveCount(0);
  await seen.goto('/members');
  await expect(seen).toHaveURL(/\/forbidden$/);
  await expect(seen.getByRole('heading', { level: 1, name: t('core', 'errors.forbidden') })).toBeVisible();
  expect((await seen.request.get('/api/members/')).status()).toBe(403);

  await role.click();
  await page
    .getByRole('menuitem')
    .filter({ has: page.getByText(t('members', 'members.roles.admins.name')) })
    .click();
  await expect(page.getByText(t('members', 'members.roleChanged'))).toBeVisible();
  await expect(role).toHaveText(t('members', 'members.roles.admins.name'));
  await shot('made an administrator');

  await seen.goto('/members');
  await expect(seen).toHaveURL(/\/members$/);
  await expect(menu.getByRole('link', { name: t('core', 'nav.members') })).toBeVisible();
  await expect(seen.getByRole('heading', { level: 1, name: t('members', 'members.title') })).toBeVisible();
  expect((await seen.request.get('/api/members/')).status()).toBe(200);
  await member.context.close();
  expect(member.problems, 'the member page logged errors').toEqual([]);
});

test('the owner stays an active administrator, and the page says it is the owner', async ({
  page,
  owner,
  world,
  locale,
  t,
  shot,
}) => {
  const ownerName = world.users.owner;

  await page.goto('/members');
  const row = page.getByRole('row').filter({ has: page.getByText(ownerName, { exact: true }) });
  const marked = `${text('members', locale, 'members.roles.admins.name')} · ${text('members', locale, 'members.owner')}`;
  await expect(row.getByText(marked, { exact: true })).toBeVisible();
  await expect(row.getByText(t('members', 'members.you'))).toBeVisible();
  await expect(row.getByText(t('members', 'members.active'))).toBeVisible();
  await expect(row.getByRole('button')).toHaveCount(0);
  await expect(page.getByRole('button', { name: t('members', 'members.changeRole', { name: ownerName }) })).toHaveCount(0);
  await expect(page.getByRole('button', { name: t('members', 'members.deactivate.for', { name: ownerName }) })).toHaveCount(
    0,
  );
  await shot('the owner');

  const listed = rows(await owner.get('/api/members/?page_size=100')).find((member) => member['username'] === ownerName);
  const id = String(listed?.['id']);
  for (const change of [{ role: 'viewers' }, { is_active: false }]) {
    const refused = await owner.send('PATCH', `/api/members/${id}/`, change);
    expect(refused.status()).toBe(409);
    const error = (await readJson(refused))['error'];
    expect(isJson(error) ? error['code'] : null).toBe('owner_locked');
  }
});
