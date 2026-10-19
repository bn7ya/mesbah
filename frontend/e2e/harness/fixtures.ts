import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

import { test as base, expect, type BrowserContext, type Page } from '@playwright/test';

import { MesbahApi } from './api';
import { label } from './copy';
import type { UiLocale } from './copy.types';
import type { Fixtures, WorkerFixtures } from './fixtures.types';
import { RESULTS, readStack } from './stack';
import { readWorld, stateFile } from './world';

const IGNORED_CONSOLE: readonly RegExp[] = [/^Failed to load resource/];

async function startIn(page: Page, locale: UiLocale | null): Promise<void> {
  if (locale) {
    await page.addInitScript((chosen) => {
      if (!localStorage.getItem('locale')) {
        localStorage.setItem('locale', chosen);
      }
    }, locale);
  }
}

function fileName(text: string): string {
  return text.replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '').toLowerCase();
}

export const test = base.extend<Fixtures, WorkerFixtures>({
  uiLocale: ['en', { option: true }],
  allowConsoleErrors: [false, { option: true }],
  // eslint-disable-next-line no-empty-pattern -- Playwright reads a fixture's dependencies from this pattern
  stack: [async ({}, use) => use(readStack()), { scope: 'worker' }],
  // eslint-disable-next-line no-empty-pattern -- as above
  world: [async ({}, use) => use(readWorld()), { scope: 'worker' }],
  locale: async ({ uiLocale }, use) => use(uiLocale ?? 'ar'),
  page: async ({ page, uiLocale }, use) => {
    await startIn(page, uiLocale);
    await use(page);
  },
  t: async ({ locale }, use) => use((bundle, key, values) => label(bundle, locale, key, values)),
  owner: async ({ stack, world }, use) => {
    const api = await MesbahApi.signIn(stack.base_url, world.users.owner, world.password);
    await use(api);
    await api.dispose();
  },
  as: async ({ browser, uiLocale, baseURL }, use) => {
    const opened: BrowserContext[] = [];
    await use(async (role) => {
      const context = await browser.newContext({ storageState: stateFile(role), baseURL });
      opened.push(context);
      const page = await context.newPage();
      await startIn(page, uiLocale);
      return page;
    });
    for (const context of opened) {
      await context.close();
    }
  },
  shot: async ({ page }, use, testInfo) => {
    let taken = 0;
    const folder = join(RESULTS, 'screens', testInfo.project.name, fileName(testInfo.titlePath.slice(1).join(' ')));
    await use(async (name) => {
      taken += 1;
      mkdirSync(folder, { recursive: true });
      const path = join(folder, `${String(taken).padStart(2, '0')}-${fileName(name)}.png`);
      await page.screenshot({ path, fullPage: true, animations: 'disabled', caret: 'hide' });
      await testInfo.attach(name, { path, contentType: 'image/png' });
    });
  },
  consoleGuard: [
    async ({ page, allowConsoleErrors }, use) => {
      const problems: string[] = [];
      page.on('pageerror', (error) => problems.push(`page error: ${error.message}`));
      page.on('console', (message) => {
        const text = message.text();
        if (message.type() === 'error' && !IGNORED_CONSOLE.some((ignored) => ignored.test(text))) {
          problems.push(`console error: ${text}`);
        }
      });
      await use(undefined);
      if (!allowConsoleErrors) {
        expect(problems, 'the page logged errors').toEqual([]);
      }
    },
    { auto: true },
  ],
});

export { expect };
