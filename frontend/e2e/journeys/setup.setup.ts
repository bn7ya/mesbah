import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

import { MesbahApi } from '../harness/api';
import { expect, test } from '../harness/fixtures';
import { PASSWORD, addMember, createProject, pretrainBase, trainVersion, uploadDataset } from '../harness/seed';
import type { UiLocale } from '../harness/copy.types';
import { stateFile, writeWorld } from '../harness/world';
import type { Role, Seeded } from '../harness/world.types';

const USERS: Readonly<Record<Role, string>> = {
  owner: 'owner',
  reviewer: 'rana',
  trainer: 'tariq',
  viewer: 'vera',
};
const ROLES: Readonly<Record<Exclude<Role, 'owner'>, string>> = {
  reviewer: 'reviewers',
  trainer: 'trainers',
  viewer: 'viewers',
};
const NAMES: Readonly<Record<UiLocale, Readonly<Record<keyof Seeded, string>>>> = {
  en: { chat: 'Chat journeys', versions: 'Version journeys', exports: 'Export journeys' },
  ar: { chat: 'رحلات المحادثة', versions: 'رحلات النسخ', exports: 'رحلات التصدير' },
};

test.describe.configure({ mode: 'serial' });

test('a fresh install is set up in Arabic with the code it printed', async ({ page, stack, t, shot }) => {
  await page.goto('/');

  await expect(page).toHaveURL(/\/setup$/);
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await shot('setup');
  await page.getByLabel(t('core', 'auth.setup.code')).fill(stack.setup_code);
  await page.getByLabel(t('core', 'auth.signIn.username')).fill(USERS.owner);
  await page.getByLabel(t('core', 'auth.signIn.password')).fill(PASSWORD);
  await page.getByRole('button', { name: t('core', 'auth.setup.submit') }).click();

  await expect(page).toHaveURL(/\/projects$/);
  await shot('first projects page');
  mkdirSync(dirname(stateFile('owner')), { recursive: true });
  // The session is kept for every project; the language it was made in is not.
  await page.evaluate(() => localStorage.clear());
  await page.context().storageState({ path: stateFile('owner') });
});

test('the journeys get their people, a base model trained here and projects', async ({ stack }) => {
  test.slow();
  const owner = await MesbahApi.signIn(stack.base_url, USERS.owner, PASSWORD);
  for (const [role, group] of Object.entries(ROLES)) {
    await addMember(owner, USERS[role as Exclude<Role, 'owner'>], group);
  }
  for (const role of Object.keys(ROLES) as Exclude<Role, 'owner'>[]) {
    const member = await MesbahApi.signIn(stack.base_url, USERS[role], PASSWORD);
    await member.saveState(stateFile(role));
    await member.dispose();
  }
  const dataset = await uploadDataset(owner, 'Journey conversations');
  const baseModel = await pretrainBase(owner, dataset, 'Journey base');
  const projects: Partial<Record<UiLocale, Seeded>> = {};
  for (const locale of ['en', 'ar'] as const) {
    const names = NAMES[locale];
    const chat = await createProject(owner, names.chat, baseModel);
    const versions = await createProject(owner, names.versions, baseModel);
    const first = await trainVersion(owner, versions, dataset);
    await trainVersion(owner, versions, dataset, first);
    const exports = await createProject(owner, names.exports, baseModel);
    await trainVersion(owner, exports, dataset);
    projects[locale] = { chat, versions, exports };
  }
  await owner.dispose();
  if (!projects.en || !projects.ar) {
    throw new Error('a locale got no projects');
  }
  writeWorld({ password: PASSWORD, users: USERS, baseModel, dataset, projects: { en: projects.en, ar: projects.ar } });
});
